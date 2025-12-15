
import streamlit as st
from datetime import date, timedelta
from core import data_access, holidays, scheduler_engine


def render():
    """Render the Generate Schedule page."""
    st.subheader("🗓️ Generate Schedule")
    
    # ========== Date & Duration Selection ==========
    col1, col2 = st.columns(2)
    
    with col1:
        start_date = st.date_input(
            "📅 Start Date",
            value=date.today(),
            key="gen_start_date",
            help="排程開始日期"
        )
    
    with col2:
        duration_type = st.selectbox(
            "⏱️ Duration Type",
            options=["Weeks", "Months"],
            index=0,
            key="duration_type"
        )
        
        if duration_type == "Weeks":
            duration = st.number_input(
                "Number of Weeks",
                min_value=1,
                max_value=52,
                value=4,
                key="duration_weeks",
                help="排程持續週數"
            )
            # 計算結束日期
            end_date = start_date + timedelta(weeks=duration)
        else:  # Months
            duration = st.number_input(
                "Number of Months",
                min_value=1,
                max_value=12,
                value=1,
                key="duration_months",
                help="排程持續月數"
            )
            # 計算結束日期 (約略計算,每月30天)
            end_date = start_date + timedelta(days=duration * 30)
    
    # 顯示計算出的結束日期
    st.info(f"📆 計算出的結束日期: **{end_date.strftime('%Y-%m-%d')}** ({duration} {duration_type.lower()})")
    
    # ========== Schedule Parameters ==========
    st.markdown("### 📊 Schedule Parameters")
    
    col_param1, col_param2 = st.columns(2)
    
    with col_param1:
        shops_per_day = st.number_input(
            "🏪 Shops per Day",
            min_value=1,
            max_value=100,
            value=int(data_access.get_setting("shops_per_day", "20")),
            key="gen_shops_per_day",
            help="每天排程的店舖數量"
        )
    
    with col_param2:
        groups_per_day = st.number_input(
            "👥 Groups per Day",
            min_value=1,
            max_value=10,
            value=int(data_access.get_setting("groups_per_day", "3")),
            key="gen_groups_per_day",
            help="每天分配的組別數量"
        )
    
    # 計算預估資訊
    business_days = _count_business_days(start_date, end_date)
    estimated_shops = business_days * shops_per_day
    
    col_est1, col_est2, col_est3 = st.columns(3)
    with col_est1:
        st.metric("⏳ Business Days", business_days)
    with col_est2:
        st.metric("🎯 Estimated Shops", estimated_shops)
    with col_est3:
        active_shops = data_access.count_active_shops()
        coverage = min(100, (estimated_shops / active_shops * 100) if active_shops > 0 else 0)
        st.metric("📈 Coverage", f"{coverage:.0f}%")
    
    # ========== Filters ==========
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
            help="留空則包含所有地區"
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
            help="留空則包含所有區域"
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
            help="篩選特定品牌"
        )
    
    # ========== Advanced Options ==========
    with st.expander("⚙️ Advanced Options", expanded=False):
        skip_weekends = st.checkbox(
            "Skip Weekends",
            value=True,
            help="自動跳過週末"
        )
        
        skip_holidays = st.checkbox(
            "Skip Public Holidays",
            value=True,
            help="自動跳過公眾假期"
        )
        
        clear_existing = st.checkbox(
            "Clear Existing Schedule",
            value=True,
            help="生成前清除現有排程"
        )
    
    # ========== Generate Button ==========
    st.markdown("---")
    
    if st.button("🚀 Generate Schedule", type="primary", use_container_width=True):
        
        # Validate
        if end_date < start_date:
            st.error("❌ End date must be after start date")
            return
        
        if business_days == 0:
            st.error("❌ No business days in selected period")
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
                
                # Clear existing schedules if requested
                if clear_existing:
                    data_access.delete_all_schedules()
                    st.info("✓ Cleared existing schedules")
                
                # Generate schedule
                schedule_result = scheduler_engine.generate_schedule(
                    start_date=start_date.isoformat(),
                    end_date=end_date.isoformat(),
                    shops_per_day=shops_per_day,
                    groups_per_day=groups_per_day,
                    filters=filters,
                    skip_weekends=skip_weekends,
                    skip_holidays=skip_holidays
                )
                
                # Save to database
                if schedule_result and len(schedule_result) > 0:
                    success = data_access.save_schedule_batch(schedule_result)
                    
                    if success:
                        st.success(f"✅ Generated {len(schedule_result)} schedule records!")
                        
                        # Show summary
                        st.markdown("### 📊 Generation Summary")
                        
                        col_sum1, col_sum2, col_sum3, col_sum4 = st.columns(4)
                        
                        with col_sum1:
                            st.metric("Total Shops", len(schedule_result))
                        
                        with col_sum2:
                            unique_dates = len(set([s['schedule_date'] for s in schedule_result]))
                            st.metric("Days Used", unique_dates)
                        
                        with col_sum3:
                            st.metric("Groups/Day", groups_per_day)
                        
                        with col_sum4:
                            avg_per_day = len(schedule_result) / unique_dates if unique_dates > 0 else 0
                            st.metric("Avg Shops/Day", f"{avg_per_day:.1f}")
                        
                        # Show date range
                        dates = sorted(set([s['schedule_date'] for s in schedule_result]))
                        if dates:
                            st.info(f"📅 Schedule period: {dates[0]} to {dates[-1]}")
                        
                        # Show region breakdown
                        region_counts = {}
                        for item in schedule_result:
                            region = item.get('region', 'Unknown')
                            region_counts[region] = region_counts.get(region, 0) + 1
                        
                        if region_counts:
                            st.markdown("**Region Breakdown:**")
                            cols = st.columns(len(region_counts))
                            for idx, (region, count) in enumerate(sorted(region_counts.items())):
                                with cols[idx]:
                                    st.metric(region, count)
                        
                        st.success("💡 Go to 'Today Schedule' to view the schedule")
                        
                        # Save parameters as default
                        data_access.set_setting("shops_per_day", str(shops_per_day))
                        data_access.set_setting("groups_per_day", str(groups_per_day))
                        
                    else:
                        st.error("❌ Failed to save schedule to database")
                else:
                    st.warning("⚠️ No schedule generated (no shops match filters?)")
                    
            except Exception as e:
                st.error(f"❌ Error generating schedule: {str(e)}")
                with st.expander("Show error details"):
                    import traceback
                    st.code(traceback.format_exc())


def _count_business_days(start: date, end: date) -> int:
    """Count business days between start and end dates."""
    count = 0
    current = start
    
    while current <= end:
        if holidays.is_business_day(current):
            count += 1
        current += timedelta(days=1)
    
    return count
