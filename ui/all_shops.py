# ui/all_shops.py

import streamlit as st
import pandas as pd
from core import data_access

def render():
    """Render the All Shops page."""
    st.subheader("🏪 All Shops")
    
    # ========== Filters ==========
    col1, col2, col3 = st.columns(3)
    
    with col1:
        # Region filter
        with data_access.get_db_connection() as conn:
            cur = conn.cursor()
            # ✅ 修正：改用 region
            cur.execute("""
                SELECT DISTINCT region 
                FROM shop_master 
                WHERE region IS NOT NULL 
                ORDER BY region
            """)
            regions = ["All"] + [row[0] for row in cur.fetchall()]
        
        selected_region = st.selectbox(
            "Region",
            options=regions,
            key="all_shops_region"
        )
    
    with col2:
        # District filter
        with data_access.get_db_connection() as conn:
            cur = conn.cursor()
            # ✅ 修正：改用 district
            if selected_region != "All":
                cur.execute("""
                    SELECT DISTINCT district 
                    FROM shop_master 
                    WHERE district IS NOT NULL AND region = ?
                    ORDER BY district
                """, (selected_region,))
            else:
                cur.execute("""
                    SELECT DISTINCT district 
                    FROM shop_master 
                    WHERE district IS NOT NULL 
                    ORDER BY district
                """)
            
            districts = ["All"] + [row[0] for row in cur.fetchall()]
        
        selected_district = st.selectbox(
            "District",
            options=districts,
            key="all_shops_district"
        )
    
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
            brands = ["All"] + [row[0] for row in cur.fetchall()]
        
        selected_brand = st.selectbox(
            "Brand",
            options=brands,
            key="all_shops_brand"
        )
    
    # ========== Active Status Filter ==========
    show_inactive = st.checkbox(
        "Show inactive shops",
        value=False,
        key="show_inactive"
    )
    
    # ========== Search ==========
    search_term = st.text_input(
        "🔍 Search by Shop ID or Name",
        placeholder="Enter shop code or name...",
        key="shop_search"
    )
    
    # ========== Query Database ==========
    with data_access.get_db_connection() as conn:
        cur = conn.cursor()
        
        # Build query
        query = """
            SELECT 
                shop_id,
                shop_name,
                address,
                region,
                district,
                brand,
                is_mtr,
                is_active,
                lat,
                lng,
                phone
            FROM shop_master
            WHERE 1=1
        """
        params = []
        
        # Apply filters
        if not show_inactive:
            query += " AND is_active = 'Y'"
        
        if selected_region != "All":
            # ✅ 修正：改用 region
            query += " AND region = ?"
            params.append(selected_region)
        
        if selected_district != "All":
            # ✅ 修正：改用 district
            query += " AND district = ?"
            params.append(selected_district)
        
        if selected_brand != "All":
            query += " AND brand = ?"
            params.append(selected_brand)
        
        if search_term:
            query += " AND (shop_id LIKE ? OR shop_name LIKE ?)"
            params.append(f"%{search_term}%")
            params.append(f"%{search_term}%")
        
        # ✅ 修正：ORDER BY 也要使用新欄位名稱
        query += " ORDER BY region, district, shop_id"
        
        cur.execute(query, params)
        rows = cur.fetchall()
    
    # ========== Display Results ==========
    if not rows:
        st.info("📭 No shops found matching the filters")
        return
    
    st.markdown(f"### 📊 Found {len(rows)} shop(s)")
    
    # Convert to DataFrame for display
    df = pd.DataFrame(rows, columns=[
        "Shop ID",
        "Shop Name",
        "Address",
        "Region",
        "District",
        "Brand",
        "MTR",
        "Active",
        "Latitude",
        "Longitude",
        "Phone"
    ])
    
    # Format display
    df["MTR"] = df["MTR"].apply(lambda x: "✅" if x == "Y" else "")
    df["Active"] = df["Active"].apply(lambda x: "✅" if x == "Y" else "❌")
    
    # Display as table
    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Shop ID": st.column_config.TextColumn("Shop ID", width="small"),
            "Shop Name": st.column_config.TextColumn("Shop Name", width="medium"),
            "Address": st.column_config.TextColumn("Address", width="large"),
            "Region": st.column_config.TextColumn("Region", width="small"),
            "District": st.column_config.TextColumn("District", width="medium"),
            "Brand": st.column_config.TextColumn("Brand", width="medium"),
            "MTR": st.column_config.TextColumn("MTR", width="small"),
            "Active": st.column_config.TextColumn("Active", width="small"),
            "Latitude": st.column_config.NumberColumn("Lat", format="%.6f"),
            "Longitude": st.column_config.NumberColumn("Lng", format="%.6f"),
            "Phone": st.column_config.TextColumn("Phone", width="medium"),
        }
    )
    
    # ========== Summary Statistics ==========
    st.markdown("---")
    st.markdown("### 📈 Summary")
    
    col_stat1, col_stat2, col_stat3, col_stat4 = st.columns(4)
    
    with col_stat1:
        st.metric("Total Shops", len(df))
    
    with col_stat2:
        active_count = len(df[df["Active"] == "✅"])
        st.metric("Active", active_count)
    
    with col_stat3:
        mtr_count = len(df[df["MTR"] == "✅"])
        st.metric("MTR Shops", mtr_count)
    
    with col_stat4:
        # ✅ 欄位名稱已經是 "Region"，不需要修改
        unique_regions = df["Region"].nunique()
        st.metric("Regions", unique_regions)
    
    # ========== Export Option ==========
    st.markdown("---")
    
    if st.button("📥 Export to CSV", key="export_csv"):
        csv = df.to_csv(index=False)
        st.download_button(
            label="Download CSV",
            data=csv,
            file_name="shops_export.csv",
            mime="text/csv"
        )
