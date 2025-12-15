# ui/generate_schedule.py
import streamlit as st
from core import data_access, scheduler_engine


# ui/generate_schedule.py

import streamlit as st
from datetime import date, timedelta
from core import data_access, holidays, scheduler_engine

def render():
    """Render the Generate Schedule page."""
    st.subheader("🗓️ Generate Schedule")
    
    # ========== Date Range Selection ==========
    col1, col2 = st.columns(2)
    
    with col1:
        start_date = st.date_input(
            "Start Date",
            value=date.today(),
            key="gen_start_date"
        )
    
    with col2:
        end_date = st.date_input(
            "End Date",
            value=date.today() + timedelta(days=30),
            key="gen_end_date"
        )
    
    # ========== Schedule Parameters ==========
    col_param1, col_param2 = st.columns(2)
    
    with col_param1:
        shops_per_day = st.number_input(
            "Shops per day",
            min_value=1,
            max_value=60,
            value=int(data_access.get_setting("shops_per_day", "20")),
            key="gen_shops_per_day"
        )
    
    with col_param2:
        groups_per_day = st.number_input(
            "Groups per day",
            min_value=1,
            max_value=10,
            value=int(data_access.get_setting("groups_per_day", "3")),
            key="gen_groups_per_day"
        )
    
    # ========== Region & District Filters ==========
    with st.expander("🗺️ Region & District Filters", expanded=False):
        # Get unique regions
        with data_access.get_db_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                SELECT DISTINCT region 
                FROM shop_master 
                WHERE region IS NOT NULL AND is_active = 'Y'
                ORDER BY region
            """)
            regions = [row[0] for row in cur.fetchall()]
        
        selected_regions = st.multiselect(
            "Select Regions",
            options=regions,
            default=None,
            help="Leave empty to include all regions"
        )
        
        # Get unique districts (filtered by selected regions)
        with data_access.get_db_connection() as conn:
            cur = conn.cursor()
            
            if selected_regions:
                placeholders = ','.join('?' * len(selected_regions))
                cur.execute(f"""
                    SELECT DISTINCT district 
                    FROM shop_master 
                    WHERE region IN ({placeholders}) 
                    AND district IS NOT NULL 
                    AND is_active = 'Y'
                    ORDER BY district
                """, selected_regions)
            else:
                cur.execute("""
                    SELECT DISTINCT district 
                    FROM shop_master 
                    WHERE district IS NOT NULL AND is_active = 'Y'
                    ORDER BY district
                """)
            
            districts = [row[0] for row in cur.fetchall()]
        
        selected_districts = st.multiselect(
            "Select Districts",
            options=districts,
            default=None,
            help="Leave empty to include all districts"
        )
    
    # ========== Brand Filter ==========
    with st.expander("🏢 Brand Filter", expanded=False):
        with data_access.get_db_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                SELECT DISTINCT brand 
                FROM shop_master 
                WHERE brand IS NOT NULL AND is_active = 'Y'
                ORDER BY brand
            """)
            brands = [row[0] for row in cur.fetchall()]
        
        selected_brand = st.selectbox(
            "Select Brand",
            options=["All"] + brands,
            index=0,
            help="Filter by specific brand"
        )
    
    # ========== Generate Button ==========
    st.markdown("---")
    
    if st.button("🚀 Generate Schedule", type="primary", use_container_width=True):
        
        # Validate date range
        if end_date < start_date:
            st.error("❌ End date must be after start date")
            return
        
        with st.spinner("Generating schedule..."):
            try:
                # Build filters
                filters = {}
                
                if selected_regions:
                    filters['regions'] = selected_regions
                
                if selected_districts:
                    filters['districts'] = selected_districts
                
                if selected_brand and selected_brand != "All":
                    filters['brand'] = selected_brand
                
                # Generate schedule
                schedule_result = scheduler_engine.generate_schedule(
                    start_date=start_date.isoformat(),
                    end_date=end_date.isoformat(),
                    shops_per_day=shops_per_day,
                    groups_per_day=groups_per_day,
                    filters=filters
                )
                
                # Save to database
                if schedule_result and len(schedule_result) > 0:
                    # Clear existing schedules first
                    data_access.delete_all_schedules()
                    
                    # Save new schedule
                    success = data_access.save_schedule_batch(schedule_result)
                    
                    if success:
                        st.success(f"✅ Generated {len(schedule_result)} schedule records!")
                        
                        # Show summary
                        col_sum1, col_sum2, col_sum3 = st.columns(3)
                        
                        with col_sum1:
                            st.metric("Total Shops", len(schedule_result))
                        
                        with col_sum2:
                            unique_dates = len(set([s['schedule_date'] for s in schedule_result]))
                            st.metric("Days", unique_dates)
                        
                        with col_sum3:
                            st.metric("Groups/Day", groups_per_day)
                        
                        st.info("💡 Go to 'Today Schedule' to view the schedule")
                    else:
                        st.error("❌ Failed to save schedule to database")
                else:
                    st.warning("⚠️ No schedule generated (no shops match filters?)")
                    
            except Exception as e:
                st.error(f"❌ Error generating schedule: {str(e)}")
                with st.expander("Show error details"):
                    import traceback
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
