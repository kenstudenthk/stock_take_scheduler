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
        
        # Map region codes to full names for display
        region_map = {
            "HK": "Hong Kong Island",
            "KN": "Kowloon",
            "NT": "New Territories",
            "IS": "Islands",
            "MO": "Macau"
        }
        
        region_display = [region_map.get(r, r) for r in regions]
        
        selected_regions_display = st.multiselect(
            "Regions",
            options=region_display,
            default=None,
            placeholder="All regions",
            help="留空則包含所有地區"
        )
        
        # Convert back to codes
        reverse_map = {v: k for k, v in region_map.items()}
        selected_regions = [reverse_map.get(r, r) for r in selected_regions_display]
    
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
    
    # ========== Advanced Options ==========
    with st.expander("⚙️ Advanced Options"):
        col_adv1, col_adv2 = st.columns(2)
        
        with col_adv1:
            include_mtr = st.selectbox(
                "Include MTR Shops",
                options=["Yes", "No"],
                index=0
            )
            
            use_clustering = st.checkbox(
                "Use Proximity Clustering",
                value=True,
                help="自動將鄰近的店舖分組"
            )
        
        with col_adv2:
            cross_region = st.selectbox(
                "Cross Region Assignment",
                options=["Allow", "Limit to same region"],
                index=0
            )
            
            include_distance = st.checkbox(
                "Calculate Distances (slower)",
                value=False,
                help="使用 AMap API 計算實際距離"
            )
        
        # Brand filter
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
            "Brand Filter",
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
                    # ✅ 修正: 使用代碼而不是完整名稱
                    regions_param = selected_regions if selected_regions else None
                    
                    # Prepare districts parameter
                    districts_param = selected_districts if selected_districts else None
                    
                    # Save groups_per_day setting
                    data_access.set_setting("groups_per_day", str(groups_per_day))
                    
                    # Call generate_schedule
                    result = scheduler_engine.generate_schedule(
                        shops_per_day=shops_per_day,
                        start_date=start_date,
                        regions=regions_param,      # ✅ 現在傳 ["NT"] 而不是 ["New Territories"]
                        districts=districts_param,   # ✅ 傳 ["Kwai Tsing"]
                        include_mtr=include_mtr,
                        cross_region=cross_region,
                        include_distance=include_distance,
                        use_clustering=use_clustering
                    )

                    
                    # Display results
                    if result.total_shops > 0:
                        st.success(f"✅ Generated schedule for {result.total_shops} shops!")
                        
                        # Show summary
                        col_sum1, col_sum2, col_sum3, col_sum4 = st.columns(4)
                        
                        with col_sum1:
                            st.metric("Total Shops", result.total_shops)
                        
                        with col_sum2:
                            st.metric("Business Days", result.business_days)
                        
                        with col_sum3:
                            st.metric("Start Date", result.start_date.strftime("%Y-%m-%d"))
                        
                        with col_sum4:
                            st.metric("Finish Date", result.finish_date.strftime("%Y-%m-%d"))
                        
                        # Show region breakdown
                        if result.region_counts:
                            st.markdown("**Region Breakdown:**")
                            cols = st.columns(len(result.region_counts))
                            for idx, (region, count) in enumerate(sorted(result.region_counts.items())):
                                with cols[idx]:
                                    region_name = region_map.get(region, region)
                                    st.metric(region_name, count)
                        
                        # Show cluster quality if available
                        if result.cluster_quality:
                            st.markdown("**Clustering Quality:**")
                            col_q1, col_q2 = st.columns(2)
                            with col_q1:
                                st.metric("Avg Distance", f"{result.cluster_quality['avg_intra_cluster_distance_km']:.2f} km")
                            with col_q2:
                                st.metric("Region Consistency", f"{result.cluster_quality['region_consistency_pct']:.0f}%")
                        
                        st.info("💡 Go to 'Today Schedule' or 'View Schedule' to see the details")
                        
                    else:
                        st.warning("⚠️ No shops match the selected filters")
                        
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
