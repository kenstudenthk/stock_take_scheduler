# ui/all_shops.py

import streamlit as st
import pandas as pd
from core import data_access
from core import folium_map
from streamlit_folium import st_folium


def render():
    """Render the All Shops page."""
    st.subheader("🏪 All Shops")
    
    # ========== Filters ==========
    st.markdown("### 🔍 Filters")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        # Region filter
        with data_access.get_db_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                SELECT DISTINCT region 
                FROM shop_master 
                WHERE region IS NOT NULL 
                ORDER BY region
            """)
            regions = [row[0] for row in cur.fetchall()]
        
        region_map = {
            "HK": "Hong Kong Island",
            "KN": "Kowloon",
            "NT": "New Territories",
            "IS": "Islands",
            "MO": "Macau"
        }
        
        region_display = [region_map.get(r, r) for r in regions]
        
        selected_regions_display = st.multiselect(
            "Region",
            options=["All"] + region_display,
            default=["All"]
        )
        
        reverse_map = {v: k for k, v in region_map.items()}
        
        if "All" in selected_regions_display:
            selected_regions = None
        else:
            selected_regions = [reverse_map.get(r, r) for r in selected_regions_display]
    
    with col2:
        # District filter
        districts = []
        try:
            with data_access.get_db_connection() as conn:
                cur = conn.cursor()
                if selected_regions:
                    placeholders = ','.join('?' * len(selected_regions))
                    cur.execute(f"""
                        SELECT DISTINCT district 
                        FROM shop_master 
                        WHERE region IN ({placeholders}) AND district IS NOT NULL
                        ORDER BY district
                    """, selected_regions)
                else:
                    cur.execute("""
                        SELECT DISTINCT district 
                        FROM shop_master 
                        WHERE district IS NOT NULL
                        ORDER BY district
                    """)
                districts = [row[0] for row in cur.fetchall()]
        except:
            districts = []
        
        selected_districts = st.multiselect(
            "District",
            options=["All"] + districts,
            default=["All"]
        )
        
        if "All" in selected_districts:
            selected_districts = None
    
    with col3:
        # Brand filter
        with data_access.get_db_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                SELECT DISTINCT brand 
                FROM shop_master 
                WHERE brand IS NOT NULL
                ORDER BY brand
            """)
            brands = [row[0] for row in cur.fetchall()]
        
        selected_brand = st.selectbox(
            "Brand",
            options=["All"] + brands,
            index=0
        )
    
    with col4:
        # Active status filter
        show_inactive = st.checkbox("Show inactive shops", value=False)
    
    # ========== Search Button ==========
    if st.button("🔍 Search", type="primary"):
        st.session_state['all_shops_searched'] = True
    
    # ========== Display Results ==========
    if st.session_state.get('all_shops_searched', False):
        with st.spinner("Loading shops..."):
            try:
                # Build query
                with data_access.get_db_connection() as conn:
                    cur = conn.cursor()
                    
                    query = "SELECT shop_id, shop_name, brand, region, district, address, lat, lng, is_mtr, phone, is_active, brand_icon_url FROM shop_master WHERE 1=1"
                    params = []
                    
                    if not show_inactive:
                        query += " AND is_active = 'Y'"
                    
                    if selected_regions:
                        placeholders = ','.join('?' * len(selected_regions))
                        query += f" AND region IN ({placeholders})"
                        params.extend(selected_regions)
                    
                    if selected_districts:
                        placeholders = ','.join('?' * len(selected_districts))
                        query += f" AND district IN ({placeholders})"
                        params.extend(selected_districts)
                    
                    if selected_brand != "All":
                        query += " AND brand = ?"
                        params.append(selected_brand)
                    
                    query += " ORDER BY region, district, shop_id"
                    
                    cur.execute(query, params)
                    rows = cur.fetchall()
                
                if not rows:
                    st.warning("No shops found")
                    return
                
                # Convert to DataFrame
                df = pd.DataFrame(rows, columns=[
                    "Shop ID", "Shop Name", "Brand", "Region", "District", 
                    "Address", "Lat", "Lng", "MTR", "Phone", "Active", "Brand Logo"
                ])
                
                st.success(f"✅ Found {len(df)} shops")
                
                # ========== Map Display ==========
                st.markdown("### 🗺️ Shop Locations")
                
                map_data = []
                for _, row in df.iterrows():
                    if pd.notna(row['Lat']) and pd.notna(row['Lng']):
                        map_data.append({
                            'shop_id': row['Shop ID'],
                            'shop_name': row['Shop Name'],
                            'brand': row['Brand'],
                            'brand_icon_url': row['Brand Logo'] or '',
                            'region': row['Region'],
                            'district': row['District'],
                            'address': row['Address'],
                            'lat': float(row['Lat']),
                            'lng': float(row['Lng']),
                            'group_number': 1,
                            'status': 'Active' if row['Active'] == 'Y' else 'Inactive'
                        })
                
                if map_data:
                    try:
                        folium_map_obj = folium_map.create_route_map_folium(
                            schedule_data=map_data,
                            date_str="All Shops",
                            show_route_lines=False,
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
                
                display_df = df[["Brand Logo", "Shop ID", "Shop Name", "Brand", "Region", "District", "Address", "Phone", "Active"]]
                
                st.dataframe(
                    display_df,
                    use_container_width=True,
                    column_config={
                        "Brand Logo": st.column_config.ImageColumn(
                            "Logo",
                            width="medium",  # ✅ 改為 medium (原本是 small)
                            help="Brand Logo"
                        ),
                        "Active": st.column_config.TextColumn(
                            "Status"
                        )
                    },
                    hide_index=True,
                    height=500  # ✅ 固定高度,避免過長
                )
                
                # Download button
                csv = df.to_csv(index=False)
                st.download_button(
                    "📥 Download CSV",
                    csv,
                    file_name="all_shops.csv",
                    mime="text/csv"
                )
                
                st.markdown("---")
                
                # ========== STATISTICS ==========
                st.markdown("### 📊 Statistics")
                
                col_stat1, col_stat2, col_stat3 = st.columns(3)
                
                with col_stat1:
                    st.metric("Total Shops", len(df))
                
                with col_stat2:
                    active_count = len(df[df['Active'] == 'Y'])
                    st.metric("Active Shops", active_count)
                
                with col_stat3:
                    mtr_count = len(df[df['MTR'] == 'Y'])
                    st.metric("MTR Shops", mtr_count)
                
                # ========== Brand breakdown with improved layout ==========
                st.markdown("---")
                st.markdown("### 🏢 Brand Breakdown")
                
                brand_counts = df['Brand'].value_counts()
                
                # Get brand logos
                brand_logos = {}
                for _, row in df.iterrows():
                    brand = row['Brand']
                    if brand not in brand_logos and pd.notna(row['Brand Logo']):
                        brand_logos[brand] = row['Brand Logo']
                
                # ✅ 改進的品牌統計佈局: Logo + 數字橫向排列
                for brand, count in sorted(brand_counts.items(), key=lambda x: -x[1]):
                    logo_url = brand_logos.get(brand, '')
                    
                    col_logo, col_brand, col_count = st.columns([0.8, 2.5, 1])
                    
                    with col_logo:
                        if logo_url and logo_url.startswith('http'):
                            try:
                                st.image(logo_url, width=60)
                            except:
                                st.markdown("🏪")
                        else:
                            st.markdown("🏪")
                    
                    with col_brand:
                        st.markdown(f"**{brand}**")
                    
                    with col_count:
                        st.metric("", count, label_visibility="collapsed")
                
            except Exception as e:
                st.error(f"❌ Error: {str(e)}")
                import traceback
                with st.expander("Error details"):
                    st.code(traceback.format_exc())
