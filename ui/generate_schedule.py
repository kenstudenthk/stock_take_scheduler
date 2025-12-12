# ui/generate_schedule.py
import streamlit as st
from core import data_access, scheduler_engine


def render():
    st.subheader("Generate Schedule")

    # Read default capacity from settings
    cap_str = data_access.get_setting("shops_per_day", "20")
    try:
        default_cap = int(cap_str)
    except (TypeError, ValueError):
        default_cap = 20

    shops_per_day = st.number_input(
        "Daily shops to schedule",
        min_value=1,
        max_value=60,
        value=default_cap,
        step=1,
    )

    start_date = st.date_input("Start date (business days only)")

    # Summary box
    total_shops = data_access.count_active_shops()
    required_days = scheduler_engine.estimate_required_business_days(
        total_shops,
        shops_per_day,
    )
    est_finish = scheduler_engine.estimate_finish_date(
        start_date,
        required_days,
    )

    with st.container():
        st.markdown(
            f"""
            > **Summary**
            > • Total shops to stock-take: **{total_shops}**
            > • Required business days (Mon–Fri, exclude holidays): **{required_days}**
            > • Estimated finish date: **{est_finish}**
            """
        )

    st.caption(
        "Scheduling uses weekdays only. Saturdays, Sundays and Hong Kong public "
        "holidays are skipped."
    )

    st.markdown("---")
    st.markdown("### Filters")

    col1, col2 = st.columns(2)
    
    with col1:
        mtr_option = st.radio(
            "Include MTR station shops?",
            ["Yes", "No", "Separate plan"],
            index=0,
        )

    with col2:
        cross_region = st.radio(
            "Cross-region scheduling?",
            ["Allow", "Limit to same region"],
            index=0,
        )

    st.markdown("#### Regions")
    regions = st.multiselect(
        "Select regions",
        options=["Hong Kong Island", "Kowloon", "New Territories", "Islands", "Macau"],
        default=["Hong Kong Island", "Kowloon", "New Territories", "Islands", "Macau"],
    )

    # ✅ Dynamic districts from database
    st.markdown("#### Specific districts (based on selected regions)")
    
    # Get unique districts from database
    with data_access.get_db_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT DISTINCT district_en FROM shop_master WHERE district_en IS NOT NULL ORDER BY district_en;")
        all_districts = [row[0] for row in cur.fetchall() if row[0]]
    
    districts = st.multiselect(
        "Specific districts (leave empty for all)",
        options=all_districts,
        help="Select specific districts to filter shops. Leave empty to include all districts.",
    )

    st.markdown("---")
    
    include_distance = st.checkbox(
        "Include distance / time calculation (AMap)",
        value=False,
        help=(
            "If checked, the app will call AMap for each route segment to "
            "estimate distance and travel time. This takes longer."
        ),
    )

    generate = st.button("Generate schedule", type="primary")

    if generate:
        # ✅ Validate inputs
        if not regions:
            st.error("Please select at least one region.")
            return
        
        with st.spinner("Calculating schedule (business days only)..."):
            try:
                result = scheduler_engine.generate_schedule(
                    shops_per_day=shops_per_day,
                    start_date=start_date,
                    regions=regions,
                    districts=districts if districts else None,
                    include_mtr=mtr_option,
                    cross_region=cross_region,
                    include_distance=include_distance,
                )

                st.success(
                    f"✓ Schedule generated with {result.total_shops} shops "
                    f"over {result.business_days} business days. "
                    f"Finish date: {result.finish_date}"
                )

                # ✅ Show distance/time if calculated
                if include_distance:
                    with data_access.get_db_connection() as conn:
                        cur = conn.cursor()
                        cur.execute(
                            "SELECT SUM(day_total_distance_km), SUM(day_total_travel_time_min) "
                            "FROM schedule;"
                        )
                        total_dist_km, total_time_min = cur.fetchone()

                    if total_dist_km is not None and total_time_min is not None:
                        st.info(
                            f"📍 Approx. total driving distance: {total_dist_km:.1f} km\n\n"
                            f"⏱️ Approx. total travel time: {total_time_min/60:.1f} hours"
                        )

                _render_stats(result)

                # 🔄 ✅ 新增：產生成功後，寫回 SharePoint
                with st.spinner("Syncing schedule back to SharePoint Lists..."):
                    ok = data_access.sync_schedule_back_to_sharepoint(
                        start_date=start_date.isoformat()
                    )
                    if ok:
                        st.success("✅ Schedule has been synced back to SharePoint Lists.")
                    else:
                        st.warning("⚠️ Schedule generated, but failed to sync to SharePoint.")

            except Exception as e:
                st.error(f"Error generating schedule: {str(e)}")
                import traceback
                with st.expander("Show error details"):
                    st.code(traceback.format_exc())



def _render_stats(result: scheduler_engine.ScheduleResult):
    """Render statistics about the generated schedule."""
    
    st.markdown("### Schedule statistics")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Total shops scheduled", result.total_shops)
    
    with col2:
        st.metric("Business days in schedule", result.business_days)
    
    with col3:
        st.metric("Avg daily distance (km)", round(result.avg_daily_distance_km, 1))
    
    with col4:
        st.metric(
            "Avg public transport time / day (h)",
            round(result.avg_public_transport_hours, 1),
        )

    st.markdown("### Status & region breakdown")
    
    region_counts = result.region_counts or {}
    
    c1, c2, c3, c4 = st.columns(4)
    
    with c1:
        st.metric("Shops closed", result.shops_closed)
    
    with c2:
        st.metric("Shops finished", result.shops_finished)
    
    with c3:
        st.metric("HK Island shops", region_counts.get("HK", 0))
    
    with c4:
        st.metric("Kowloon shops", region_counts.get("KN", 0))

    c5, c6, c7 = st.columns(3)
    
    with c5:
        st.metric("New Territories shops", region_counts.get("NT", 0))
    
    with c6:
        st.metric("Islands shops", region_counts.get("IS", 0))
    
    with c7:
        st.metric("Macau shops", region_counts.get("MO", 0))
