# ui/view_schedule.py
import datetime
import streamlit as st
from core import data_access, map_visualizer


def render():
    st.subheader("View Schedule")

    # 記住是否已經搜尋過，用來控制首次自動載入
    if "view_schedule_searched" not in st.session_state:
        st.session_state.view_schedule_searched = False

    # ---------- Filters ----------
    st.markdown("### Search filters")

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        date_val = st.date_input(
            "Date",
            value=datetime.date.today(),
            help="Filter by schedule date.",
            key="view_date",
        )
        use_date = st.checkbox("Use date filter", value=True, key="view_use_date")

    with col2:
        shop_id = st.text_input(
            "Shop ID",
            help="Exact shop ID match",
            key="view_shop_id",
        ).strip()

    with col3:
        region = st.selectbox(
            "Region",
            ["All", "HK", "KN", "NT", "IS", "MO"],
            index=0,
            help="HK=Hong Kong Island, KN=Kowloon, NT=New Territories, IS=Islands, MO=Macau.",
            key="view_region",
        )

    with col4:
        district = st.text_input(
            "District (partial match)",
            help="Enter partial district name",
            key="view_district",
        ).strip()

    status = st.multiselect(
        "Status",
        options=["Planned", "Done", "Closed", "Rescheduled"],
        default=["Planned", "Done", "Closed", "Rescheduled"],
        key="view_status",
    )

    col_btn1, col_btn2, _ = st.columns([1, 1, 3])
    with col_btn1:
        search_clicked = st.button(
            "🔍 Search",
            type="primary",
            use_container_width=True,
            key="view_search_btn",
        )
    with col_btn2:
        clear_clicked = st.button(
            "🔄 Clear filters",
            use_container_width=True,
            key="view_clear_btn",
        )

    # Clear filters → 直接重載頁面
    if clear_clicked:
        st.session_state.view_schedule_searched = False
        st.rerun()

    # ---------- Perform search ----------
    # 首次進入畫面時，自動用當日 + 全部狀態做一次查詢
    if search_clicked or not st.session_state.view_schedule_searched:
        st.session_state.view_schedule_searched = True

        with st.spinner("Searching schedule..."):
            date_str = date_val.isoformat() if use_date else None

            try:
                # ✅ 修正：使用 search_shops 而不是 search_schedule
                # 準備參數
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
                    st.warning("No schedule records found for the selected filters.")
                    return

                # ---------- Map + Table 佈局 ----------
                col_map, col_table = st.columns([2, 3])

                with col_map:
                    st.markdown("#### 📍 Map (filtered shops)")
                    deck = map_visualizer.create_route_map(
                        rows,
                        date_str or "Schedule",
                        show_route_lines=False,   # View 頁只顯示點
                        show_labels=False,
                        selected_groups=None,
                        map_style="light",
                    )
                    st.pydeck_chart(deck, use_container_width=True)

                # ---------- 準備表格資料 ----------
                display_rows: list[dict] = []
                for r in rows:
                    display_rows.append(
                        {
                            "Date": r.get("schedule_date") or r.get("date", ""),
                            "Shop ID": r.get("shop_id", ""),
                            "Shop Name": r.get("shop_name", ""),
                            "Status": r.get("status", "Planned"),
                            "Region": r.get("region") or r.get("region_code", ""),
                            "District": r.get("district") or r.get("district_en", ""),
                            "Brand": r.get("brand", "Unknown"),  # ✅ 加入 Brand
                            "Address": r.get("address") or r.get("address_zh", ""),
                            "Status Reason": r.get("status_reason", "") or "",
                        }
                    )

                with col_table:
                    # Show count
                    st.success(f"✓ Found {len(display_rows)} schedule record(s)")

                    # Dataframe
                    st.dataframe(
                        display_rows,
                        use_container_width=True,
                        column_config={
                            "Status": st.column_config.TextColumn(
                                "Status",
                                help="Current status of the shop visit",
                            ),
                            "Date": st.column_config.DateColumn(
                                "Date",
                                help="Scheduled date",
                            ),
                        },
                    )

                    # Download CSV
                    col_dl1, _ = st.columns([1, 3])
                    with col_dl1:
                        st.download_button(
                            "📥 Download CSV",
                            _rows_to_csv(display_rows),
                            file_name=f"schedule_export_{date_str or 'all'}.csv",
                            mime="text/csv",
                            use_container_width=True,
                        )

                    # Quick statistics
                    with st.expander("📊 Quick statistics", expanded=True):
                        status_counts: dict[str, int] = {}
                        region_counts: dict[str, int] = {}
                        brand_counts: dict[str, int] = {}

                        for row in display_rows:
                            # Handle None values
                            s = row["Status"] if row["Status"] else "Unknown"
                            rgn = row["Region"] if row["Region"] else "Unknown"
                            brand = row.get("Brand", "Unknown") or "Unknown"
                            
                            status_counts[s] = status_counts.get(s, 0) + 1
                            region_counts[rgn] = region_counts.get(rgn, 0) + 1
                            brand_counts[brand] = brand_counts.get(brand, 0) + 1

                        col_s1, col_s2, col_s3 = st.columns(3)
                        
                        with col_s1:
                            st.markdown("**By Status:**")
                            for s, cnt in sorted(status_counts.items(), key=lambda x: (x[0] is None, x[0])):
                                st.metric(s or "Unknown", cnt)
                        
                        with col_s2:
                            st.markdown("**By Region:**")
                            for rgn, cnt in sorted(region_counts.items(), key=lambda x: (x[0] is None, x[0])):
                                st.metric(rgn or "Unknown", cnt)
                        
                        with col_s3:
                            st.markdown("**By Brand:**")
                            # 只顯示前 5 個品牌
                            for brand, cnt in sorted(brand_counts.items(), key=lambda x: -x[1])[:5]:
                                st.metric(brand or "Unknown", cnt)
                            
                            if len(brand_counts) > 5:
                                st.caption(f"...and {len(brand_counts) - 5} more brands")

            except Exception as e:
                st.error(f"Error searching schedule: {str(e)}")
                import traceback
                with st.expander("Show error details"):
                    st.code(traceback.format_exc())


def _rows_to_csv(rows: list[dict]) -> str:
    """Convert list of dicts to CSV string."""
    import csv
    import io

    if not rows:
        return ""

    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=rows[0].keys())
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue()
