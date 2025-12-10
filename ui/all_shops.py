# ui/all_shops.py
import datetime
import streamlit as st
from core import data_access, map_visualizer


def render():
    st.subheader("All Shops with Map")

    
    # ---------- Filters ----------
# ---------- Filters ----------
    st.markdown("### Search filters")

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        date_val = st.date_input(
            "Date",
            value=datetime.date.today(),
            help="Filter by schedule date.",
            key="allshops_date",
        )
        use_date = st.checkbox("Use date filter", value=False, key="allshops_use_date")

    with col2:
        shop_id = st.text_input(
            "Shop ID",
            help="Exact shop ID match",
            key="allshops_shop_id",
        ).strip()

    with col3:
        # Multi-select for regions
        regions = st.multiselect(
            "Region (multiple)",
            options=["HK", "KN", "NT", "Islands", "MO"],
            default=["HK", "KN", "NT", "Islands", "MO"],
            help="HK=Hong Kong Island, KN=Kowloon, NT=New Territories, Islands=Islands District, MO=Macau.",
            key="allshops_regions",
        )

    with col4:
        # ✅ NEW: Get unique districts from database
        with data_access.get_db_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT DISTINCT district_en FROM shop_master WHERE district_en IS NOT NULL ORDER BY district_en;")
            all_districts = [row[0] for row in cur.fetchall() if row[0]]
        
        districts = st.multiselect(
            "District (multiple)",
            options=all_districts,
            default=[],  # Empty by default = all districts
            help="Select specific districts. Leave empty to include all.",
            key="allshops_districts",
        )

    brand = st.text_input(
        "Brand (partial match)",
        key="allshops_brand",
    ).strip()

    status = st.multiselect(
        "Status",
        options=["Planned", "Done", "Closed", "Rescheduled"],
        default=["Planned", "Done", "Closed", "Rescheduled"],
        key="allshops_status",
    )


    col_btn1, col_btn2, _ = st.columns([1, 1, 3])
    with col_btn1:
            search_clicked = st.button(
                "🔍 Search",
                type="primary",
                use_container_width=True,
                key="allshops_search_btn",
            )
    with col_btn2:
            clear_clicked = st.button(
                "🔄 Clear filters",
                use_container_width=True,
                key="allshops_clear_btn",
            )

    if clear_clicked:
            st.rerun()

    if not search_clicked:
            st.info("Use filters above and click Search to load shops.")
            return

# ---------- Perform search ----------
    with st.spinner("Loading shops..."):
        date_str = date_val.isoformat() if use_date else None
        rows = data_access.search_shops(
            date=date_str,
            shop_id=shop_id or None,
            regions=regions if regions else None,
            districts=districts if districts else None,  # ✅ CHANGED: pass list
            status=status or None,
            brand=brand or None,
        )



    if not rows:
            st.warning("No shops found for the selected filters.")
            return

        # ---------- Map + Table ----------
    col_map, col_table = st.columns([2, 3])

    with col_map:
            st.markdown("#### Map (filtered shops)")
            deck = map_visualizer.create_route_map(
                rows,
                date_str or "All shops",
                show_route_lines=False,
                show_labels=False,
                selected_groups=None,
                map_style="light",
            )
            # 固定高度，讓地圖和表格視覺上差不多高
            st.pydeck_chart(deck, use_container_width=True, height=500)

        # 準備表格資料
    display_rows: list[dict] = []
    for r in rows:
            display_rows.append(
                {
                    "Date": r["date"],
                    "Shop ID": r["shop_id"],
                    "Shop Name": r["shop_name"],
                    "Region": r["region_code"],
                    "District": r["district_en"],
                }
            )

    with col_table:
            st.success(f"✓ Found {len(display_rows)} shop record(s)")

            st.dataframe(
                display_rows,
                use_container_width=True,
                column_config={
                    "Date": st.column_config.DateColumn("Date"),
                    "Region": st.column_config.TextColumn("Region"),
                    "District": st.column_config.TextColumn("District"),
                },
            )
    # ===== 📥 EXPORT SECTION =====
    st.markdown("---")
    st.markdown("#### 📥 Export Options")

    # Toggle for route vs markers
    show_route = st.checkbox(
        "Show route between shops (if unchecked, shows markers only)",
        value=False,
        key="show_route_toggle",
    )

    col_exp1, col_exp2, col_exp3 = st.columns(3)

    with col_exp1:
        # CSV Export
        csv_data = _export_to_csv(rows)
        st.download_button(
            label="📄 Download CSV",
            data=csv_data,
            file_name=f"shops_{datetime.date.today().isoformat()}.csv",
            mime="text/csv; charset=utf-8",
            use_container_width=True,
        )

    with col_exp2:
        # Google Maps Export
        google_url = _export_to_google_maps(rows, show_route=show_route)
        if google_url:
            st.link_button(
                "🗺️ Open in Google Maps",
                google_url,
                use_container_width=True,
            )
        else:
            st.button("🗺️ Open in Google Maps", disabled=True, use_container_width=True)
            st.caption("⚠️ No valid coordinates")

    with col_exp3:
        # AMap Export
        amap_url = _export_to_amap(rows, show_route=show_route)
        if amap_url:
            st.link_button(
                "🧭 Open in AMap",
                amap_url,
                use_container_width=True,
            )
        else:
            st.button("🧭 Open in AMap", disabled=True, use_container_width=True)
            st.caption("⚠️ No valid coordinates")
    # ===== END EXPORT SECTION =====


        # ---------- Brand / Region statistics (full width) ----------
    with st.expander("📊 Quick statistics", expanded=True):
            brand_counts: dict[str, int] = {}
            region_counts: dict[str, int] = {}

            for r in rows:
                b = r.get("brand", "") or ""
                rgn = r.get("region_code", "") or ""
                brand_counts[b] = brand_counts.get(b, 0) + 1
                region_counts[rgn] = region_counts.get(rgn, 0) + 1

            # 先把 Region / Brand 轉成排序過的列表
            regions = sorted(region_counts.items())
            brands = sorted(brand_counts.items())

            col_r, col_b = st.columns(2)

            
            # ===== By Region: 一行多個 metric =====
            st.markdown("### By Region")

            # Define all possible regions
            ALL_REGIONS = ["HK", "KN", "NT", "Islands", "MO"]
            region_display = {
                "HK": "Hong Kong Island",
                "KN": "Kowloon", 
                "NT": "New Territories",
                "Islands": "Islands",
                "MO": "Macau"
            }

            # Build counts for all regions
            region_counts = {rgn: 0 for rgn in ALL_REGIONS}
            for r in rows:
                rgn = r.get("region_code", "")
                if rgn in region_counts:
                    region_counts[rgn] += 1

            # Display all regions
            region_cols = st.columns(5)
            for col, rgn in zip(region_cols, ALL_REGIONS):
                with col:
                    st.metric(
                        region_display.get(rgn, rgn), 
                        region_counts[rgn]
                    )


            st.markdown("---")

            # ===== By Brand: 多行，每行固定顯示 N 個品牌 =====
            st.markdown("**By Brand:**")
            if brands:
                MAX_PER_ROW = 6  # 每行顯示幾個品牌，可以依你螢幕寬度調整

                # 切成多個 chunk，每個 chunk 是一行
                for i in range(0, len(brands), MAX_PER_ROW):
                    chunk = brands[i : i + MAX_PER_ROW]
                    cols = st.columns(len(chunk))
                    for col, (b, cnt) in zip(cols, chunk):
                        with col:
                            st.metric(b or "(Unknown)", cnt)
                            
def _export_to_csv(rows: list[dict]) -> bytes:
    """Convert rows to CSV format with UTF-8 BOM for Excel compatibility."""
    import io
    
    if not rows:
        return b""
    
    output = io.StringIO()
    
    # Define columns to export
    columns = [
        "shop_id", "shop_name", "region_code", "district_en", 
        "address_zh", "brand", "lat", "lng", "status", "date"
    ]
    
    # Write header
    output.write(",".join(columns) + "\n")
    
    # Write data rows
    for row in rows:
        values = []
        for col in columns:
            value = row.get(col, "")
            if value is None:
                value = ""
            
            # Convert to string and escape for CSV
            value_str = str(value)
            
            # Escape quotes
            value_str = value_str.replace('"', '""')
            
            # Wrap in quotes if contains comma, quote, or newline
            if ',' in value_str or '"' in value_str or '\n' in value_str:
                value_str = f'"{value_str}"'
            
            values.append(value_str)
        
        output.write(",".join(values) + "\n")
    
    # ✅ FIX: Add UTF-8 BOM for Excel compatibility with Chinese characters
    csv_string = output.getvalue()
    return '\ufeff'.encode('utf-8') + csv_string.encode('utf-8')


def _export_to_google_maps(rows: list[dict], show_route: bool = False) -> str | None:
    """Generate Google Maps URL with markers or route."""
    if not rows:
        return None
    
    # Filter rows with valid coordinates
    valid_shops = [
        r for r in rows 
        if r.get("lat") and r.get("lng") 
        and isinstance(r["lat"], (int, float))
        and isinstance(r["lng"], (int, float))
        and r["lat"] not in (0, 1) 
        and r["lng"] not in (0, 2)
        and -90 <= r["lat"] <= 90
        and -180 <= r["lng"] <= 180
    ]
    
    if not valid_shops:
        return None
    
    if show_route:
        # ✅ ROUTE MODE: Show directions between shops
        # Google Maps supports up to 10 waypoints
        limited_shops = valid_shops[:10]
        coords = [f"{shop['lat']},{shop['lng']}" for shop in limited_shops]
        url = "https://www.google.com/maps/dir/" + "/".join(coords)
        
        if len(valid_shops) > 10:
            st.caption(f"⚠️ Route limited to first 10 of {len(valid_shops)} shops")
    else:
        # ✅ MARKERS MODE: Show all shops as markers (no route)
        # Use Google Maps search with multiple markers
        # Format: https://www.google.com/maps/search/?api=1&query=lat1,lng1&query=lat2,lng2
        
        if len(valid_shops) == 1:
            # Single marker
            shop = valid_shops[0]
            url = f"https://www.google.com/maps/search/?api=1&query={shop['lat']},{shop['lng']}"
        else:
            # Multiple markers using My Maps style URL
            # Center on average position
            avg_lat = sum(s['lat'] for s in valid_shops) / len(valid_shops)
            avg_lng = sum(s['lng'] for s in valid_shops) / len(valid_shops)
            
            # Create markers string
            markers = "&".join([
                f"markers={s['lat']},{s['lng']}" 
                for s in valid_shops[:50]  # Google Maps can show more markers
            ])
            
            url = f"https://www.google.com/maps/search/?api=1&query={avg_lat},{avg_lng}&{markers}"
            
            if len(valid_shops) > 50:
                st.caption(f"ℹ️ Showing first 50 of {len(valid_shops)} shops as markers")
    
    return url



def _export_to_amap(rows: list[dict], show_route: bool = False) -> str | None:
    """Generate AMap URL with markers or route."""
    if not rows:
        return None
    
    # Filter rows with valid coordinates
    valid_shops = [
        r for r in rows 
        if r.get("lat") and r.get("lng") 
        and isinstance(r["lat"], (int, float))
        and isinstance(r["lng"], (int, float))
        and r["lat"] not in (0, 1) 
        and r["lng"] not in (0, 2)
        and -90 <= r["lat"] <= 90
        and -180 <= r["lng"] <= 180
    ]
    
    if not valid_shops:
        return None
    
    if show_route:
        # ✅ ROUTE MODE: Show navigation from first to last shop
        if len(valid_shops) == 1:
            shop = valid_shops[0]
            shop_name = shop.get('shop_name', 'Shop')
            url = f"https://uri.amap.com/marker?position={shop['lng']},{shop['lat']}&name={shop_name}"
        else:
            start = valid_shops[0]
            end = valid_shops[-1]
            
            start_name = start.get('shop_name', 'Start')
            end_name = end.get('shop_name', 'End')
            
            url = (f"https://uri.amap.com/navigation?"
                   f"from={start['lng']},{start['lat']},{start_name}&"
                   f"to={end['lng']},{end['lat']},{end_name}&"
                   f"mode=car&"
                   f"policy=1&"
                   f"coordinate=gaode")
            
            if len(valid_shops) > 2:
                st.caption(f"ℹ️ Route from first to last ({len(valid_shops)} shops total)")
    else:
        # ✅ MARKERS MODE: Show all shops as markers
        if len(valid_shops) == 1:
            shop = valid_shops[0]
            shop_name = shop.get('shop_name', 'Shop')
            url = f"https://uri.amap.com/marker?position={shop['lng']},{shop['lat']}&name={shop_name}"
        else:
            # Multiple markers - center on average position
            avg_lat = sum(s['lat'] for s in valid_shops) / len(valid_shops)
            avg_lng = sum(s['lng'] for s in valid_shops) / len(valid_shops)
            
            # AMap format for multiple markers
            # Use coordinate and center map
            url = f"https://uri.amap.com/marker?position={avg_lng},{avg_lat}&coordinate=gaode&callnative=0"
            
            st.caption(f"ℹ️ Centered on {len(valid_shops)} shops (open in AMap app for all markers)")
    
    return url


                            