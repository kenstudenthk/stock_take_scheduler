# ui/view_schedule.py
import datetime
import streamlit as st
from core import data_access
from core import folium_map
from streamlit_folium import st_folium


def render():
    st.subheader("🔍 View Schedule")

    if "view_schedule_searched" not in st.session_state:
        st.session_state.view_schedule_searched = False

    # ========== Filters ==========
    st.markdown("### 🔍 Search filters")

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        date_val = st.date_input(
            "Date",
            value=datetime.date.today(),
            key="view_date",
        )
        use_date = st.checkbox("Use date filter", value=True, key="view_use_date")

    with col2:
        shop_id = st.text_input("Shop ID", key="view_shop_id").strip()

    with col3:
        region = st.selectbox(
            "Region",
            ["All", "HK", "KN", "NT", "IS", "MO"],
            index=0,
            key="view_region",
        )

    with col4:
        district = st.text_input("District", key="view_district").strip()

    status = st.multiselect(
        "Status",
        options=["Planned", "Done", "Closed", "Rescheduled"],
        default=["Planned", "Done", "Closed", "Rescheduled"],
        key="view_status",
    )

    col_btn1, col_btn2, _ = st.columns([1, 1, 3])
    with col_btn1:
        search_clicked = st.button("🔍 Search", type="primary", use_container_width=True)
    with col_btn2:
        if st.button("🔄 Clear", use_container_width=True):
            st.session_state.view_schedule_searched = False
            st.rerun()

    # ========== Perform search ==========
    if search_clicked or st.session_state.view_schedule_searched:
        st.session_state.view_schedule_searched = True

        with st.spinner("Searching..."):
            date_str = date_val.isoformat() if use_date else None

            try:
                regions_param = [region] if region and region != "All" else None
                districts_param = [district] if district else None
                
                rows = data_access.search_shops(
                    date=date_str,
                    shop_id=shop_id or None,
                    regions=regions_param,
                    districts=districts_param,
                    status=status or None,
                )

                if not rows:
                    st.warning("No records found")
                    return

                st.success(f"✅ Found {len(rows)} records")

                # ========== Map Display (使用 Folium) ==========
                st.markdown("### 📍 Shop Locations")
                
                # Prepare map data
                map_data = []
                for r in rows:
                    if r.get('lat') and r.get('lng'):
                        map_data.append({
                            'shop_id': r.get('shop_id', ''),
                            'shop_name': r.get('shop_name', ''),
                            'brand': r.get('brand', ''),
                            'brand_icon_url': r.get('brand_icon_url', ''),
                            'region': r.get('region', ''),
                            'district': r.get('district', ''),
                            'address': r.get('address', ''),
                            'lat': float(r.get('lat')),
                            'lng': float(r.get('lng')),
                            'group_number': 1,  # Single group for search results
                            'status': r.get('status', 'Planned'),
                            'schedule_date': r.get('schedule_date', '')
                        })
                
                if map_data:
                    try:
                        folium_map_obj = folium_map.create_route_map_folium(
                            schedule_data=map_data,
                            date_str=date_str or "Search Results",
                            show_route_lines=False,  # No routes for search results
                            selected_groups=None
                        )
                        
                        st_folium(
                            folium_map_obj,
                            width=None,
                            height=500,
                            returned_objects=[]
                        )
                    except Exception as e:
                        st.error(f"Map error: {e}")
                        import traceback
                        st.code(traceback.format_exc())

                st.markdown("---")

                # ========== Data Table ==========
                st.markdown("### 📋 Shop List")
                
                display_rows = []
                for r in rows:
                    display_rows.append({
                        "Logo": r.get("brand_icon_url", ""),
                        "Date": r.get("schedule_date") or r.get("date", ""),
                        "Shop ID": r.get("shop_id", ""),
                        "Shop Name": r.get("shop_name", ""),
                        "Brand": r.get("brand", "Unknown"),
                        "Status": r.get("status", "Planned"),
                        "Region": r.get("region") or "",
                        "District": r.get("district") or "",
                        "Address": r.get("address") or "",
                    })

                st.dataframe(
                    display_rows,
                    use_container_width=True,
                    column_config={
                        "Logo": st.column_config.ImageColumn(
                            "Logo",
                            width="small"
                        ),
                        "Status": st.column_config.TextColumn("Status"),
                        "Date": st.column_config.TextColumn("Date"),
                    },
                    hide_index=True
                )

                st.download_button(
                    "📥 Download CSV",
                    _rows_to_csv(display_rows),
                    file_name=f"schedule_{date_str or 'all'}.csv",
                    mime="text/csv",
                    use_container_width=True,
                )

                # ========== Statistics ==========
                with st.expander("📊 Statistics", expanded=True):
                    status_counts = {}
                    region_counts = {}
                    brand_counts = {}

                    for row in display_rows:
                        s = row["Status"] or "Unknown"
                        rgn = row["Region"] or "Unknown"
                        brand = row.get("Brand", "Unknown") or "Unknown"
                        
                        status_counts[s] = status_counts.get(s, 0) + 1
                        region_counts[rgn] = region_counts.get(rgn, 0) + 1
                        brand_counts[brand] = brand_counts.get(brand, 0) + 1

                    col_s1, col_s2, col_s3 = st.columns(3)
                    
                    with col_s1:
                        st.markdown("**By Status:**")
                        for s, cnt in sorted(status_counts.items()):
                            st.metric(s, cnt)
                    
                    with col_s2:
                        st.markdown("**By Region:**")
                        for rgn, cnt in sorted(region_counts.items()):
                            st.metric(rgn, cnt)
                    
                    with col_s3:
                        st.markdown("**By Brand (Top 5):**")
                        for brand, cnt in sorted(brand_counts.items(), key=lambda x: -x[1])[:5]:
                            st.metric(brand, cnt)
                        
                        if len(brand_counts) > 5:
                            st.caption(f"...and {len(brand_counts) - 5} more")

            except Exception as e:
                st.error(f"Error: {str(e)}")
                import traceback
                with st.expander("Details"):
                    st.code(traceback.format_exc())


def _rows_to_csv(rows: list[dict]) -> str:
    import csv
    import io

    if not rows:
        return ""

    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=rows[0].keys())
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue()
