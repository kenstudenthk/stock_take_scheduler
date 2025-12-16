# core/map_visualizer.py
"""
Map visualization module using PyDeck for beautiful interactive maps.
"""
import pydeck as pdk
import pandas as pd
from typing import List, Dict, Optional
from urllib.parse import quote


# Group 顏色配置 (RGB 格式)
GROUP_COLORS = [
    [255, 107, 107],  # Group 1 - 紅色
    [78, 205, 196],   # Group 2 - 青色
    [69, 183, 209],   # Group 3 - 藍色
    [255, 160, 122],  # Group 4 - 橙色
    [152, 216, 200],  # Group 5 - 綠色
    [247, 220, 111],  # Group 6 - 黃色
    [187, 143, 206],  # Group 7 - 紫色
    [133, 193, 226],  # Group 8 - 淺藍
    [248, 184, 139],  # Group 9 - 淺橙
    [169, 223, 191],  # Group 10 - 淺綠
]

# 狀態顏色配置
STATUS_COLORS = {
    "Planned": [100, 149, 237],  # 藍色
    "Done": [50, 205, 50],       # 綠色
    "Closed": [220, 20, 60],     # 紅色
    "Rescheduled": [255, 140, 0], # 橙色
}


def create_route_map(
    schedule_data: List[Dict],
    date_str: str,
    show_route_lines: bool = True,
    show_labels: bool = True,
    selected_groups: Optional[List[int]] = None,
    map_style: str = "light",
) -> Optional[pdk.Deck]:
    """
    Create an interactive 3D route map using PyDeck with brand logos.
    """
    if not schedule_data:
        return None

    # Filter by selected groups
    if selected_groups:
        schedule_data = [s for s in schedule_data if s.get("group_number") in selected_groups]

    # ---------- Prepare marker data ----------
    markers_data: List[Dict] = []
    
    # ✅ 調試: 列印所有品牌 Logo URL
    print("🔍 DEBUG: Checking brand logos in schedule_data:")
    for shop in schedule_data:
        brand = shop.get("brand", "Unknown")
        logo_url = shop.get("brand_icon_url", "")
        print(f"   - {brand}: {logo_url}")
    
    for shop in schedule_data:
        lat = shop.get("lat")
        lng = shop.get("lng")

        if lat is None or lng is None:
            continue

        group_no = shop.get("group_number", 1)
        status = shop.get("status", "Planned")
        color = GROUP_COLORS[(group_no - 1) % len(GROUP_COLORS)]
        
        # ✅ 正確取得 brand_icon_url
        brand_icon = shop.get("brand_icon_url", "")
        if not brand_icon:
            brand_icon = ""
        else:
            brand_icon = str(brand_icon).strip()

        markers_data.append({
            "lat": float(lat),
            "lng": float(lng),
            "group_number": int(group_no),
            "shop_name": str(shop.get("shop_name", "")),
            "shop_id": str(shop.get("shop_id", "")),
            "brand": str(shop.get("brand", "")),
            "brand_icon_url": brand_icon,
            "address": str(shop.get("address", "")),
            "district": str(shop.get("district", "")),
            "region": str(shop.get("region", "")),
            "status": str(status),
            "color": color,
        })

    if not markers_data:
        return None

    df_markers = pd.DataFrame(markers_data)
    
    # ✅ 調試: 檢查 DataFrame
    print(f"\n📊 DataFrame has {len(df_markers)} markers")
    print(f"📊 Brand icon URLs:\n{df_markers[['brand', 'brand_icon_url']].head(10)}")

    # ---------- Prepare route lines ----------
    line_data: List[Dict] = []
    if show_route_lines:
        groups = df_markers.groupby("group_number")
        for group_no, group_df in groups:
            coords_list = group_df[["lng", "lat"]].values.tolist()

            if len(coords_list) > 1:
                color_base = GROUP_COLORS[(int(group_no) - 1) % len(GROUP_COLORS)]
                color_with_alpha = list(color_base) + [200]
                line_data.append({
                    "path": coords_list,
                    "group_number": int(group_no),
                    "color": color_with_alpha,
                })

    # ---------- Create layers ----------
    layers: List[pdk.Layer] = []

    # 1. Route lines layer
    if line_data:
        df_lines = pd.DataFrame(line_data)
        line_layer = pdk.Layer(
            "PathLayer",
            df_lines,
            get_path="path",
            get_color="color",
            width_scale=20,
            width_min_pixels=2,
            get_width=5,
            pickable=True,
            auto_highlight=True,
        )
        layers.append(line_layer)

    # 2. IconLayer for brand logos
    # ✅ 使用品牌 Logo (如果有效),否則使用顏色圓點
    def _build_icon(row):
        url = row.get("brand_icon_url", "")
        
        # ✅ 檢查 URL 是否有效
        if url and isinstance(url, str) and url.strip() and url.startswith('http'):
            print(f"✅ Using logo for {row['brand']}: {url}")
            return {
                "url": url.strip(),
                "width": 64,   # ✅ 較小的解析度
                "height": 64,
                "anchorY": 64,
            }
        else:
            # ✅ 使用簡單的顏色圓點 (預設圖示)
            print(f"⚠️ No valid logo for {row['brand']}, using default icon")
            return {
                "url": "https://raw.githubusercontent.com/visgl/deck.gl-data/master/website/icon-atlas.png",
                "width": 128,
                "height": 128,
                "x": 0,
                "y": 0,
                "mask": True,
                "anchorY": 128,
            }

    df_markers["icon_data"] = df_markers.apply(_build_icon, axis=1)

    # ✅ 縮小圖示尺寸 (讓地圖更易閱讀)
    df_markers["icon_size"] = 4  # ✅ 統一使用較小尺寸
    
    icon_layer = pdk.Layer(
        "IconLayer",
        df_markers,
        get_position=["lng", "lat"],
        get_icon="icon_data",
        size_scale=8,  # ✅ 從 25 降到 8 (大幅縮小)
        get_size="icon_size",
        get_color="color",  # ✅ 如果沒有 Logo,使用顏色
        pickable=True,
        auto_highlight=True,
    )
    layers.append(icon_layer)
    
    # 3. Text labels layer (optional)
    if show_labels:
        text_layer = pdk.Layer(
            "TextLayer",
            df_markers,
            get_position=["lng", "lat"],
            get_text="shop_id",
            get_size=12,  # ✅ 縮小文字
            get_color=[0, 0, 0, 255],  # ✅ 改為黑色,更易閱讀
            get_alignment_baseline="'bottom'",
            get_text_anchor="'middle'",
            pickable=False,
        )
        layers.append(text_layer)

    # ---------- View state ----------
    try:
        center_lat = float(df_markers["lat"].mean())
        center_lng = float(df_markers["lng"].mean())

        lat_range = float(df_markers["lat"].max() - df_markers["lat"].min())
        lng_range = float(df_markers["lng"].max() - df_markers["lng"].min())
        max_range = max(lat_range, lng_range)

        if max_range > 0.5:
            zoom = 10
        elif max_range > 0.2:
            zoom = 11
        elif max_range > 0.1:
            zoom = 12
        else:
            zoom = 13

        # 香港範圍檢查
        if not (22.0 < center_lat < 22.6 and 113.8 < center_lng < 114.5):
            center_lat = 22.3193
            center_lng = 114.1694
            zoom = 11

    except Exception:
        center_lat = 22.3193
        center_lng = 114.1694
        zoom = 11

    view_state = pdk.ViewState(
        latitude=center_lat,
        longitude=center_lng,
        zoom=zoom,
        pitch=0,
        bearing=0,
    )

    # ---------- Basemap styles ----------
    map_styles = {
        "light": "https://basemaps.cartocdn.com/gl/positron-gl-style/style.json",
        "dark": "https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json",
        "streets": "https://basemaps.cartocdn.com/gl/voyager-gl-style/style.json",
    }

    # ---------- Deck ----------
    deck = pdk.Deck(
        layers=layers,
        initial_view_state=view_state,
        tooltip={
            "html": "<b>{shop_name}</b><br/>🏢 {brand}<br/>📍 {address}<br/>ID: {shop_id}<br/>Group {group_number}",
            "style": {
                "backgroundColor": "white",
                "color": "black",
                "fontSize": "12px",
                "padding": "10px"
            }
        },
        map_style=map_styles.get(map_style, map_styles["light"]),
    )

    return deck


def export_to_google_maps_url(shops: List[Dict]) -> str:
    """
    Generate a Google Maps URL with waypoints for navigation.
    Maximum 10 waypoints supported.
    
    Args:
        shops: List of shops in route order
    
    Returns:
        Google Maps URL string
    """
    if not shops:
        return ""
    
    # Sort by route order
    shops_sorted = sorted(shops, key=lambda x: x.get("day_route_order", 0))
    
    # Google Maps supports up to 10 waypoints (9 intermediate + 1 destination)
    coords = []
    for shop in shops_sorted[:10]:
        lat = shop.get("lat")
        lng = shop.get("lng")
        if lat and lng:
            coords.append(f"{lat},{lng}")
    
    if not coords:
        return ""
    
    # Build URL
    base_url = "https://www.google.com/maps/dir/"
    url = base_url + "/".join(coords)
    
    return url


def export_to_amap_url(shops: List[Dict], mode: str = "driving") -> str:
    """
    Generate an AMap URL for navigation.
    Note: AMap mobile app supports better navigation than web.
    
    Args:
        shops: List of shops in route order
        mode: Navigation mode ('driving', 'walking', 'transit')
    
    Returns:
        AMap URL string
    """
    if not shops:
        return ""
    
    # Sort by route order
    shops_sorted = sorted(shops, key=lambda x: x.get("day_route_order", 0))
    
    # Get first shop (start point)
    first_shop = shops_sorted[0]
    lat = first_shop.get("lat")
    lng = first_shop.get("lng")
    name = first_shop.get("shop_name", "起點")
    
    if not lat or not lng:
        return ""
    
    # For single destination
    if len(shops_sorted) == 1:
        url = f"https://uri.amap.com/marker?position={lng},{lat}&name={quote(name)}"
        return url
    
    # For route (start to end)
    last_shop = shops_sorted[-1]
    end_lat = last_shop.get("lat")
    end_lng = last_shop.get("lng")
    end_name = last_shop.get("shop_name", "終點")
    
    if not end_lat or not end_lng:
        return ""
    
    # AMap navigation URI
    url = (
        f"https://uri.amap.com/navigation?"
        f"from={lng},{lat}&fromname={quote(name)}&"
        f"to={end_lng},{end_lat}&toname={quote(end_name)}&"
        f"mode={mode}&"
        f"policy=1&"  # 1=fastest, 2=shortest, 3=avoid tolls
        f"coordinate=wgs84"
    )
    
    return url


def create_route_summary_dataframe(schedule_data: List[Dict]) -> pd.DataFrame:
    """
    Create a summary DataFrame for route export/printing.
    
    Args:
        schedule_data: List of schedule records
    
    Returns:
        Pandas DataFrame with route summary
    """
    summary = []
    
    for shop in sorted(schedule_data, key=lambda x: (x.get("group_no", 1), x.get("day_route_order", 0))):
        summary.append({
            "Group": shop.get("group_no", ""),
            "Order": shop.get("day_route_order", ""),
            "Shop ID": shop.get("shop_id", ""),
            "Shop Name": shop.get("shop_name", ""),
            "Brand": shop.get("brand", ""),
            "Region": shop.get("region_code", ""),
            "District": shop.get("district_en", ""),
            "Address": shop.get("address_zh", ""),
            "Phone": shop.get("phone", ""),
            "Contact": shop.get("contact_name", ""),
            "Status": shop.get("status", ""),
            "Latitude": shop.get("lat", ""),
            "Longitude": shop.get("lng", ""),
            "Google Maps": f"https://www.google.com/maps/search/?api=1&query={shop.get('lat')},{shop.get('lng')}" if shop.get('lat') and shop.get('lng') else "",
        })
    
    return pd.DataFrame(summary)


def get_group_statistics(schedule_data: List[Dict]) -> Dict:
    """
    Calculate statistics for each group.
    
    Args:
        schedule_data: List of schedule records
    
    Returns:
        Dictionary with group statistics
    """
    stats = {}
    
    for shop in schedule_data:
        group_no = shop.get("group_no", 1)
        if group_no not in stats:
            stats[group_no] = {
                "total_shops": 0,
                "planned": 0,
                "done": 0,
                "closed": 0,
                "rescheduled": 0,
                "shops": [],
            }
        
        stats[group_no]["total_shops"] += 1
        status = shop.get("status", "Planned")
        
        if status == "Planned":
            stats[group_no]["planned"] += 1
        elif status == "Done":
            stats[group_no]["done"] += 1
        elif status == "Closed":
            stats[group_no]["closed"] += 1
        elif status == "Rescheduled":
            stats[group_no]["rescheduled"] += 1
        
        stats[group_no]["shops"].append(shop)
    
    return stats
