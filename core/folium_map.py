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
    "#4ECDC4",  # Group 2 - 青色
    "#45B7D1",  # Group 3 - 藍色
    "#FFA07A",  # Group 4 - 橙色
    "#98D8C8",  # Group 5 - 綠色
    "#F7DC6F",  # Group 6 - 黃色
    "#BB8FCE",  # Group 7 - 紫色
    "#85C1E2",  # Group 8 - 淺藍
    "#F8B88B",  # Group 9 - 淺橙
    "#A9DFB",   # Group 10 - 淺綠
]


def create_route_map_folium(
    schedule_data: List[Dict],
    date_str: str,
    show_route_lines: bool = True,
    selected_groups: Optional[List[int]] = None,
) -> folium.Map:
    """
    Create an interactive map using Folium with brand logos.
    
    Args:
        schedule_data: List of shop dictionaries
        date_str: Date string for title
        show_route_lines: Whether to draw route lines
        selected_groups: List of group numbers to display
        
    Returns:
        Folium Map object
    """
    
    # Filter by selected groups
    if selected_groups:
        schedule_data = [s for s in schedule_data if s.get("group_number") in selected_groups]
    
    if not schedule_data:
        # Return empty map centered on Hong Kong
        return folium.Map(
            location=[22.3193, 114.1694],
            zoom_start=11,
            tiles="OpenStreetMap"
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
    
    # Create base map
    m = folium.Map(
        location=center,
        zoom_start=zoom,
        tiles="CartoDB positron",  # Clean light style
        control_scale=True
    )
    
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
    
    # core/folium_map.py (在 return m 之前添加)

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
    
    # Create popup HTML with brand logo
    popup_html = f"""
    <div style="font-family: Arial, sans-serif; width: 280px;">
        <div style="background-color: {color}; color: white; padding: 10px; margin: -10px -10px 10px -10px; border-radius: 5px 5px 0 0;">
            <h4 style="margin: 0; font-size: 16px;">🏪 {shop_name}</h4>
            <small>Shop ID: {shop_id}</small>
        </div>
        
        <div style="padding: 10px 0;">
            {_get_logo_html(logo_url, brand)}
            
            <div style="margin-top: 10px;">
                <strong>🏢 Brand:</strong> {brand}<br>
                <strong>📍 Address:</strong> {address}<br>
                <strong>🏷️ Status:</strong> <span style="color: {_get_status_color(status)};">{status}</span><br>
                <strong>👥 Group:</strong> {group_no}
            </div>
            
            <div style="margin-top: 10px; padding-top: 10px; border-top: 1px solid #ddd;">
                <a href="https://www.google.com/maps/search/?api=1&query={lat},{lng}" target="_blank" 
                   style="color: #4285F4; text-decoration: none;">
                    📍 Open in Google Maps
                </a>
            </div>
        </div>
    </div>
    """
    
    # Determine icon
    if logo_url and logo_url.startswith('http'):
        # Use custom HTML icon with logo
        icon_html = f"""
        <div style="position: relative;">
            <div style="
                width: 40px; 
                height: 40px; 
                background-color: white;
                border: 3px solid {color};
                border-radius: 8px;
                display: flex;
                align-items: center;
                justify-content: center;
                box-shadow: 0 2px 4px rgba(0,0,0,0.3);
            ">
                <img src="{logo_url}" 
                     style="max-width: 34px; max-height: 34px; object-fit: contain;"
                     onerror="this.style.display='none'; this.parentElement.innerHTML='<div style=\\'color:{color};font-weight:bold;font-size:14px;\\'>{brand[:2]}</div>'">
            </div>
            <div style="
                position: absolute;
                bottom: -18px;
                left: 50%;
                transform: translateX(-50%);
                background-color: {color};
                color: white;
                padding: 2px 6px;
                border-radius: 10px;
                font-size: 10px;
                font-weight: bold;
                white-space: nowrap;
                box-shadow: 0 1px 2px rgba(0,0,0,0.3);
            ">{shop_id}</div>
        </div>
        """
        
        icon = folium.DivIcon(html=icon_html)
    else:
        # Fallback to colored circle with brand initial
        brand_initial = brand[:2].upper() if brand else "?"
        icon_html = f"""
        <div style="position: relative;">
            <div style="
                width: 36px;
                height: 36px;
                background-color: {color};
                border: 3px solid white;
                border-radius: 50%;
                display: flex;
                align-items: center;
                justify-content: center;
                box-shadow: 0 2px 4px rgba(0,0,0,0.4);
                color: white;
                font-weight: bold;
                font-size: 14px;
            ">{brand_initial}</div>
            <div style="
                position: absolute;
                bottom: -16px;
                left: 50%;
                transform: translateX(-50%);
                background-color: white;
                color: {color};
                padding: 1px 5px;
                border-radius: 8px;
                font-size: 9px;
                font-weight: bold;
                border: 1px solid {color};
                white-space: nowrap;
            ">{shop_id}</div>
        </div>
        """
        icon = folium.DivIcon(html=icon_html)
    
    # Add marker
    folium.Marker(
        location=[lat, lng],
        popup=folium.Popup(popup_html, max_width=300),
        tooltip=f"{shop_name} ({brand})",
        icon=icon
    ).add_to(feature_group)


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
