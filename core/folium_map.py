# core/folium_map.py
"""
Enhanced map visualization using Folium with brand logos support.
"""
import folium
from folium import plugins
from typing import List, Dict, Optional
import base64
from io import BytesIO
from PIL import Image
import requests

# Group 顏色配置
GROUP_COLORS = [
    "#FF6B6B",  # Group 1 - 紅色
    "#10B981",  # Group 2 - 綠色
    "#FBBF24",  # Group 3 - 黃色 ✅
    "#8B5CF6",  # Group 4 - 紫色
    "#EC4899",  # Group 5 - 粉紅
    "#F59E0B",  # Group 6 - 橙色
    "#6366F1",  # Group 7 - 靛藍
    "#14B8A6",  # Group 8 - 青綠
    "#F97316",  # Group 9 - 深橙
    "#22C55E",  # Group 10 - 淺綠
]

# ✅ 地圖樣式配置
MAP_STYLES = {
    "Light": "CartoDB positron",
    "Dark": "CartoDB dark_matter",
    "Standard": "OpenStreetMap",
    "Terrain": "Stamen Terrain",
    "Toner": "Stamen Toner",
    "Watercolor": "Stamen Watercolor",
}


def create_route_map_folium(
    schedule_data: List[Dict],
    date_str: str,
    show_route_lines: bool = True,
    selected_groups: Optional[List[int]] = None,
    map_style: str = "Light",  # ✅ 新增參數
) -> folium.Map:
    """
    Create an interactive map using Folium with brand logos.
    
    Args:
        schedule_data: List of shop dictionaries
        date_str: Date string for title
        show_route_lines: Whether to draw route lines
        selected_groups: List of group numbers to display
        map_style: Map tile style (Light, Dark, Standard, Terrain, Toner, Watercolor)
        
    Returns:
        Folium Map object
    """
    
    # Filter by selected groups
    if selected_groups:
        schedule_data = [s for s in schedule_data if s.get("group_number") in selected_groups]
    
    # ✅ Get tile layer based on selected style
    tile_layer = MAP_STYLES.get(map_style, "CartoDB positron")
    
    if not schedule_data:
        # Return empty map centered on Hong Kong
        return folium.Map(
            location=[22.3193, 114.1694],
            zoom_start=11,
            tiles=tile_layer
        )
    
    # Calculate map center
    lats = [s["lat"] for s in schedule_data if s.get("lat")]
    lngs = [s["lng"] for s in schedule_data if s.get("lng")]
    
    if not lats or not lngs:
        center = [22.3193, 114.1694]
        zoom = 11
    else:
        center = [sum(lats) / len(lats), sum(lngs) / len(lngs)]
        
        # Calculate zoom level based on span
        lat_span = max(lats) - min(lats)
        lng_span = max(lngs) - min(lngs)
        max_span = max(lat_span, lng_span)
        
        if max_span > 0.5:
            zoom = 10
        elif max_span > 0.2:
            zoom = 11
        elif max_span > 0.1:
            zoom = 12
        else:
            zoom = 13
    
    # ✅ Create base map with selected style
    m = folium.Map(
        location=center,
        zoom_start=zoom,
        tiles=tile_layer,
        control_scale=True
    )
    
    # ✅ 添加替代圖層 (讓用戶可以在地圖上切換)
    for style_name, tile_url in MAP_STYLES.items():
        if style_name != map_style:  # 不添加當前選中的
            folium.TileLayer(
                tiles=tile_url,
                name=style_name,
                overlay=False,
                control=True
            ).add_to(m)
    
    # Group shops by group_number
    groups = {}
    for shop in schedule_data:
        group_no = shop.get("group_number", 1)
        if group_no not in groups:
            groups[group_no] = []
        groups[group_no].append(shop)
    
    # Add markers and routes for each group
    for group_no, shops in groups.items():
        color = GROUP_COLORS[(group_no - 1) % len(GROUP_COLORS)]
        
        # Create feature group for this route
        feature_group = folium.FeatureGroup(name=f"Group {group_no} ({len(shops)} shops)")
        
        # Add route line
        if show_route_lines and len(shops) > 1:
            coords = [[s["lat"], s["lng"]] for s in shops if s.get("lat") and s.get("lng")]
            if len(coords) > 1:
                folium.PolyLine(
                    coords,
                    color=color,
                    weight=3,
                    opacity=0.7,
                    popup=f"Group {group_no} Route"
                ).add_to(feature_group)
        
        # Add markers with brand logos
        for shop in shops:
            if not shop.get("lat") or not shop.get("lng"):
                continue
            
            _add_shop_marker(feature_group, shop, color, group_no)
        
        feature_group.add_to(m)
    
    # Add layer control
    folium.LayerControl(collapsed=False).add_to(m)
    
    # Add fullscreen button
    plugins.Fullscreen(
        position='topright',
        title='Full Screen',
        title_cancel='Exit Full Screen',
        force_separate_button=True
    ).add_to(m)
    
    # Add measure control
    plugins.MeasureControl(
        position='topleft',
        primary_length_unit='kilometers',
        secondary_length_unit='meters',
        primary_area_unit='hectares'
    ).add_to(m)
    
    # Add custom legend
    legend_html = '''
    <div style="position: fixed; 
                bottom: 50px; right: 50px; width: 200px; height: auto;
                background-color: white; z-index:9999; font-size:14px;
                border:2px solid grey; border-radius: 5px; padding: 10px;
                box-shadow: 0 0 15px rgba(0,0,0,0.2);">
        <p style="margin: 0 0 10px 0; font-weight: bold; text-align: center;">
            📍 Legend
        </p>
    '''
    
    for i, (group_no, shops) in enumerate(groups.items()):
        color = GROUP_COLORS[(group_no - 1) % len(GROUP_COLORS)]
        legend_html += f'''
        <p style="margin: 5px 0;">
            <span style="background-color: {color}; 
                         width: 20px; height: 20px; 
                         display: inline-block; 
                         border-radius: 3px;
                         margin-right: 5px;"></span>
            Group {group_no} <span style="color: #666;">({len(shops)})</span>
        </p>
        '''
    
    legend_html += '</div>'
    m.get_root().html.add_child(folium.Element(legend_html))
    
    return m


def _add_shop_marker(feature_group, shop: Dict, color: str, group_no: int):
    """
    Add a marker with brand logo to the map.
    """
    lat = shop.get("lat")
    lng = shop.get("lng")
    shop_id = shop.get("shop_id", "")
    shop_name = shop.get("shop_name", "")
    brand = shop.get("brand", "")
    address = shop.get("address", "")
    status = shop.get("status", "Planned")
    logo_url = shop.get("brand_icon_url", "")
    
    # ✅ 增強的 Popup: 顯示大 Logo + 完整資訊
    popup_html = f"""
    <div style="font-family: Arial, sans-serif; width: 300px;">
        <div style="background-color: {color}; color: white; padding: 12px; margin: -10px -10px 15px -10px; border-radius: 8px 8px 0 0;">
            <h4 style="margin: 0 0 5px 0; font-size: 18px;">🏪 {shop_name}</h4>
            <div style="font-size: 11px; opacity: 0.9;">Shop ID: {shop_id} | Group {group_no}</div>
        </div>
        
        <div style="padding: 0 10px 10px 10px;">
            {_get_logo_html_large(logo_url, brand)}
            
            <div style="margin-top: 15px; line-height: 1.6;">
                <div style="margin-bottom: 8px;">
                    <strong style="color: {color};">🏢 Brand:</strong> 
                    <span style="font-size: 15px; font-weight: 600;">{brand}</span>
                </div>
                <div style="margin-bottom: 8px;">
                    <strong style="color: {color};">📍 Address:</strong><br>
                    <span style="font-size: 13px;">{address}</span>
                </div>
                <div style="margin-bottom: 8px;">
                    <strong style="color: {color};">🏷️ Status:</strong> 
                    <span style="background-color: {_get_status_color(status)}; color: white; padding: 2px 8px; border-radius: 12px; font-size: 12px; font-weight: 600;">
                        {status}
                    </span>
                </div>
            </div>
            
            <div style="margin-top: 15px; padding-top: 12px; border-top: 2px solid #eee; text-align: center;">
                <a href="https://www.google.com/maps/search/?api=1&query={lat},{lng}" 
                   target="_blank" 
                   style="display: inline-block; background-color: #4285F4; color: white; padding: 8px 16px; border-radius: 6px; text-decoration: none; font-weight: 600; font-size: 13px;">
                    📍 Open in Google Maps
                </a>
            </div>
        </div>
    </div>
    """
    
    # ✅ 簡單的彩色圖釘圖示 (帶 Shop ID)
    icon_html = f"""
    <div style="position: relative;">
        <div style="
            width: 18px;
            height: 18px;
            background-color: {color};
            border: 2px solid white;
            border-radius: 50%;
            box-shadow: 0 2px 4px rgba(0,0,0,0.4);
        "></div>
        <div style="
            position: absolute;
            bottom: -12px;
            left: 50%;
            transform: translateX(-50%);
            background-color: white;
            color: {color};
            padding: 1px 4px;
            border-radius: 6px;
            font-size: 8px;
            font-weight: bold;
            border: 1px solid {color};
            white-space: nowrap;
            box-shadow: 0 1px 2px rgba(0,0,0,0.2);
        ">{shop_id}</div>
    </div>
    """
    
    icon = folium.DivIcon(html=icon_html)
    
    # Add marker
    folium.Marker(
        location=[lat, lng],
        popup=folium.Popup(popup_html, max_width=320),
        tooltip=f"🏪 {shop_name} | {brand}",
        icon=icon
    ).add_to(feature_group)


def _get_logo_html_large(logo_url: str, brand: str) -> str:
    """Generate HTML for large brand logo display in popup."""
    if logo_url and logo_url.startswith('http'):
        return f"""
        <div style="text-align: center; padding: 15px; background-color: #f9f9f9; border-radius: 8px; margin-bottom: 5px;">
            <img src="{logo_url}" 
                 style="max-width: 160px; max-height: 80px; object-fit: contain;"
                 alt="{brand}"
                 onerror="this.parentElement.innerHTML='<div style=\\'color:#999;font-size:16px;font-weight:600;\\'>{brand}</div>'">
        </div>
        """
    else:
        return f"""
        <div style="text-align: center; padding: 15px; background-color: #f9f9f9; border-radius: 8px; margin-bottom: 5px;">
            <div style="color: #666; font-size: 18px; font-weight: 600;">{brand}</div>
        </div>
        """


def _get_logo_html(logo_url: str, brand: str) -> str:
    """Generate HTML for brand logo display in popup."""
    if logo_url and logo_url.startswith('http'):
        return f"""
        <div style="text-align: center; margin-bottom: 10px;">
            <img src="{logo_url}" 
                 style="max-width: 120px; max-height: 60px; object-fit: contain;"
                 alt="{brand}">
        </div>
        """
    else:
        return f"""
        <div style="text-align: center; margin-bottom: 10px; color: #999;">
            <strong>{brand}</strong>
        </div>
        """


def _get_status_color(status: str) -> str:
    """Get color for status badge."""
    colors = {
        "Planned": "#3498db",
        "Done": "#2ecc71",
        "Closed": "#e74c3c",
        "Rescheduled": "#f39c12"
    }
    return colors.get(status, "#95a5a6")
