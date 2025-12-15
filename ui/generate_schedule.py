# ui/generate_schedule.py

import streamlit as st
from datetime import date, timedelta
from core import data_access, holidays, scheduler_engine


def render():
    """Render the Generate Schedule page."""
    st.subheader("🗓️ Generate Schedule")
    
    # ========== Basic Parameters ==========
    col1, col2, col3 = st.columns(3)
    
    with col1:
        start_date = st.date_input(
            "📅 Start Date",
            value=date.today(),
            key="gen_start_date"
        )
    
    with col2:
        shops_per_day = st.number_input(
            "🏪 Shops / Day",
            min_value=1,
            max_value=100,
            value=int(data_access.get_setting("shops_per_day", "20")),
            key="gen_shops_per_day"
        )
    
    with col3:
        groups_per_day = st.number_input(
            "👥 Groups / Day",
            min_value=1,
            max_value=10,
            value=int(data_access.get_setting("groups_per_day", "3")),
            key="gen_groups_per_day"
        )
    
    # ========== Region & District Filters ==========
    st.markdown("### 🗺️ Filters")
    
    col_filter1, col_filter2 = st.columns(2)
    
    with col_filter1:
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
            "Regions",
            options=regions,
            default=None,
            placeholder="All regions",
            help="留空則包含所有地區"
        )
    
    with col_filter2:
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
            "Districts",
            options=districts,
            default=None,
            placeholder="All districts",
            help="留空則包含所有區域"
        )
    
    # ========== Brand Filter (Optional) ==========
    with st.expander("🏢 Brand Filter (Optional)"):
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
            index=0
        )
    
    # ========== Generate Button ==========
    st.markdown("---")
    
    col_btn1, col_btn2 = st.columns([3, 1])
    
    with col_btn1:
        if st.button("🚀 Generate Schedule", type="primary", use_container_width=True):
            
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
                    
                    # Clear existing schedules first
                    with data_access.get_db_connection() as conn:
                        cur = conn.cursor()
                        cur.execute("DELETE FROM schedule;")
                        conn.commit()
                    
                    st.info("✓ Cleared existing schedules")
                    
                    # Generate schedule
                    # 自動計算結束日期 (開始日期 + 60天)
                    end_date = start_date + timedelta(days=60)
                    
                    schedule_result = scheduler_engine.generate_schedule(
                        start_date=start_date.isoformat(),
                        end_date=end_date.isoformat(),
                        shops_per_day=shops_per_day,
                        groups_per_day=groups_per_day,
                        filters=filters
                    )
                    
                    # Save to database
                    if schedule_result and len(schedule_result) > 0:
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
                            
                            # Save parameters as default
                            data_access.set_setting("shops_per_day", str(shops_per_day))
                            data_access.set_setting("groups_per_day", str(groups_per_day))
                        else:
                            st.error("❌ Failed to save schedule to database")
                    else:
                        st.warning("⚠️ No schedule generated. Check your filters.")
                        
                except Exception as e:
                    st.error(f"❌ Error: {str(e)}")
                    with st.expander("Show error details"):
                        import traceback
                        st.code(traceback.format_exc())
    
    with col_btn2:
        if st.button("🗑️ Clear All", use_container_width=True):
            try:
                with data_access.get_db_connection() as conn:
                    cur = conn.cursor()
                    cur.execute("DELETE FROM schedule;")
                    conn.commit()
                st.success("✓ All schedules cleared")
            except Exception as e:
                st.error(f"❌ Error: {e}")
