# ui/settings.py

import streamlit as st
import datetime  
from core import data_access


def render():
    """Render the Settings page with improved UI/UX."""
    st.subheader("⚙️ Settings")
    
    # Create tabs for better organization
    tab1, tab2, tab3, tab4 = st.tabs([
        "📡 SharePoint Connection",
        "🗓️ Schedule Parameters",
        "🗺️ Map Settings",
        "💾 Data Management"
    ])
    
    # ========== Tab 1: SharePoint Connection ==========
    with tab1:
        st.markdown("### 📡 SharePoint List Configuration")
        st.caption("Configure connection to your SharePoint List for data synchronization")
        
        col1, col2 = st.columns([2, 1])
        
        with col1:
            sp_url = st.text_input(
                "SharePoint List URL",
                value=data_access.get_setting("SHAREPOINT_LIST_URL", ""),
                help="Microsoft Graph API endpoint for your SharePoint List",
                placeholder="https://graph.microsoft.com/v1.0/sites/{site-id}/lists/{list-id}"
            )
            
            sp_token = st.text_input(
                "Access Token",
                value=data_access.get_setting("SHAREPOINT_ACCESS_TOKEN", ""),
                type="password",
                help="OAuth 2.0 Bearer token for Microsoft Graph API"
            )
            
            status_field = st.text_input(
                "Status Field Name",
                value=data_access.get_setting("SHAREPOINT_STATUS_FIELD", "ScheduleStatus"),
                help="Internal name of the status field in SharePoint"
            )
        
        with col2:
            st.info("""
            **How to get these values:**
            
            1. **List URL**: Use Graph Explorer to find your list
            2. **Access Token**: Use Azure AD app registration
            3. **Status Field**: Check column settings in SharePoint
            """)
        
        col_save, col_test = st.columns(2)
        
        with col_save:
            if st.button("💾 Save SharePoint Settings", type="primary", use_container_width=True):
                data_access.set_setting("SHAREPOINT_LIST_URL", sp_url)
                data_access.set_setting("SHAREPOINT_ACCESS_TOKEN", sp_token)
                data_access.set_setting("SHAREPOINT_STATUS_FIELD", status_field)
                st.success("✅ SharePoint settings saved")
        
        with col_test:
            if st.button("🧪 Test Connection", use_container_width=True):
                if sp_url and sp_token:
                    try:
                        with st.spinner("Testing..."):
                            result = data_access.import_shops_from_sharepoint(
                                list_url=sp_url,
                                token=sp_token,
                                overwrite=False
                            )
                            st.success(f"✅ Connection successful! Found {result['success']} shops")
                    except Exception as e:
                        st.error(f"❌ Connection failed: {e}")
                else:
                    st.warning("⚠️ Please enter URL and token first")
    
    # ========== Tab 2: Schedule Parameters ==========
    with tab2:
        st.markdown("### 🗓️ Schedule Generation Parameters")
        st.caption("Configure default parameters for schedule generation")
        
        col1, col2 = st.columns(2)
        
        with col1:
            shops_per_day = st.number_input(
                "Shops per Day",
                min_value=1,
                max_value=100,
                value=int(data_access.get_setting("shops_per_day", "20")),
                help="Default number of shops to schedule per day"
            )
            
            groups_per_day = st.number_input(
                "Groups per Day",
                min_value=1,
                max_value=10,
                value=int(data_access.get_setting("groups_per_day", "3")),
                help="Number of teams/groups working each day"
            )
        
        with col2:
            max_distance = st.number_input(
                "Max Distance (km)",
                min_value=1,
                max_value=50,
                value=int(data_access.get_setting("max_distance_km", "10")),
                help="Maximum distance between shops in same route"
            )
            
            buffer_days = st.number_input(
                "Buffer Days",
                min_value=0,
                max_value=30,
                value=int(data_access.get_setting("buffer_days", "3")),
                help="Extra days to add at the end of schedule"
            )
        
        if st.button("💾 Save Schedule Parameters", type="primary", use_container_width=True):
            data_access.set_setting("shops_per_day", str(shops_per_day))
            data_access.set_setting("groups_per_day", str(groups_per_day))
            data_access.set_setting("max_distance_km", str(max_distance))
            data_access.set_setting("buffer_days", str(buffer_days))
            st.success("✅ Schedule parameters saved")
    
    # ========== Tab 3: Map Settings ==========
    with tab3:
        st.markdown("### 🗺️ Map Configuration")
        st.caption("Configure map display and routing options")
        
        col1, col2 = st.columns(2)
        
        with col1:
            map_provider = st.selectbox(
                "Map Provider",
                options=["Google Maps", "AMap (高德地圖)"],
                index=0,
                help="Default map provider for navigation"
            )
            
            amap_key = st.text_input(
                "AMap Web API Key",
                value=data_access.get_setting("AMAP_WEB_KEY", ""),
                type="password",
                help="Required for AMap features"
            )
        
        with col2:
            default_center = st.text_input(
                "Default Map Center",
                value=data_access.get_setting("map_center", "22.3193,114.1694"),
                help="Latitude,Longitude for default map center"
            )
            
            default_zoom = st.slider(
                "Default Zoom Level",
                min_value=8,
                max_value=15,
                value=int(data_access.get_setting("default_zoom", "11")),
                help="Higher number = more zoomed in"
            )
        
        if st.button("💾 Save Map Settings", type="primary", use_container_width=True):
            data_access.set_setting("map_provider", map_provider)
            data_access.set_setting("AMAP_WEB_KEY", amap_key)
            data_access.set_setting("map_center", default_center)
            data_access.set_setting("default_zoom", str(default_zoom))
            st.success("✅ Map settings saved")
    
    # ========== Tab 4: Data Management ==========
    # ui/settings.py (修改 Tab 4: Data Management 部分)

    # ========== Tab 4: Data Management ==========
    with tab4:
        st.markdown("### 💾 Data Import/Export")
        st.caption("Manage your shop master data and schedules")
        
        # Import section
        st.markdown("#### 📥 Import Data")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("**Shop Master Data**")
            if st.button("📥 Import Shops from SharePoint", use_container_width=True, key="import_shops"):
                sp_url = data_access.get_setting("SHAREPOINT_LIST_URL")
                sp_token = data_access.get_setting("SHAREPOINT_ACCESS_TOKEN")
                
                if sp_url and sp_token:
                    with st.spinner("Importing shops..."):
                        try:
                            result = data_access.import_shops_from_sharepoint(
                                list_url=sp_url,
                                token=sp_token,
                                overwrite=True
                            )
                            st.success(f"✅ Imported {result['success']} shops")
                            if result['failed'] > 0:
                                st.warning(f"⚠️ {result['failed']} shops failed")
                        except Exception as e:
                            st.error(f"❌ Import failed: {e}")
                else:
                    st.warning("⚠️ Configure SharePoint settings first")
        
        with col2:
            st.markdown("**Schedule Data**")
            if st.button("📥 Import Schedules from SharePoint", use_container_width=True, key="import_schedules"):
                sp_url = data_access.get_setting("SHAREPOINT_LIST_URL")
                sp_token = data_access.get_setting("SHAREPOINT_ACCESS_TOKEN")
                
                if sp_url and sp_token:
                    with st.spinner("Importing schedules..."):
                        try:
                            result = data_access.import_schedules_from_sharepoint(
                                list_url=sp_url,
                                token=sp_token
                            )
                            st.success(f"✅ Imported {result['success']} schedules")
                            if result['failed'] > 0:
                                st.warning(f"⚠️ {result['failed']} schedules failed")
                            if result['skipped'] > 0:
                                st.info(f"ℹ️ {result['skipped']} schedules skipped")
                        except Exception as e:
                            st.error(f"❌ Import failed: {e}")
                else:
                    st.warning("⚠️ Configure SharePoint settings first")
        
        st.markdown("---")
        
        # Export section
        st.markdown("#### 📤 Export Data")
        
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("📥 Export All Shops (CSV)", use_container_width=True):
                try:
                    shops = data_access.get_all_shops(active_only=False)
                    import pandas as pd
                    df = pd.DataFrame(shops)
                    csv = df.to_csv(index=False)
                    st.download_button(
                        "💾 Download shops.csv",
                        csv,
                        file_name="all_shops.csv",
                        mime="text/csv",
                        use_container_width=True
                    )
                except Exception as e:
                    st.error(f"❌ Export failed: {e}")
        
        with col2:
            if st.button("📥 Export All Schedules (CSV)", use_container_width=True):
                try:
                    with data_access.get_db_connection() as conn:
                        import pandas as pd
                        df = pd.read_sql_query("SELECT * FROM schedule ORDER BY schedule_date, group_number", conn)
                        csv = df.to_csv(index=False)
                        st.download_button(
                            "💾 Download schedules.csv",
                            csv,
                            file_name="all_schedules.csv",
                            mime="text/csv",
                            use_container_width=True
                        )
                except Exception as e:
                    st.error(f"❌ Export failed: {e}")
        
        st.markdown("---")
        
        # Sync to SharePoint
        st.markdown("#### 🔄 Sync to SharePoint")
        
        col1, col2 = st.columns(2)
        
        with col1:
            sync_start_date = st.date_input(
                "Start Date",
                value=datetime.date.today(),
                key="sync_start_date"
            )
        
        with col2:
            sync_end_date = st.date_input(
                "End Date",
                value=datetime.date.today() + datetime.timedelta(days=30),
                key="sync_end_date"
            )
        
        if st.button("🔄 Sync Schedules to SharePoint", type="primary", use_container_width=True):
            sp_url = data_access.get_setting("SHAREPOINT_LIST_URL")
            sp_token = data_access.get_setting("SHAREPOINT_ACCESS_TOKEN")
            
            if sp_url and sp_token:
                with st.spinner("Syncing to SharePoint..."):
                    try:
                        result = data_access.export_schedules_to_sharepoint(
                            start_date=sync_start_date.isoformat(),
                            end_date=sync_end_date.isoformat(),
                            list_url=sp_url,
                            token=sp_token
                        )
                        st.success(f"✅ Synced {result['success']} schedules")
                        if result['failed'] > 0:
                            st.warning(f"⚠️ {result['failed']} schedules failed")
                    except Exception as e:
                        st.error(f"❌ Sync failed: {e}")
            else:
                st.warning("⚠️ Configure SharePoint settings first")
        
        st.markdown("---")
        
        # Danger zone (保持原樣)
        with st.expander("⚠️ Danger Zone", expanded=False):
            # ... (原有的危險區域代碼)

        # Danger zone
            with st.expander("⚠️ Danger Zone", expanded=False):
                st.error("**Warning: These actions cannot be undone!**")
                
                col1, col2 = st.columns(2)
                
                with col1:
                    if st.button("🗑️ Clear All Schedules", use_container_width=True):
                        try:
                            with data_access.get_db_connection() as conn:
                                cur = conn.cursor()
                                cur.execute("DELETE FROM schedule;")
                            st.success("✅ All schedules cleared")
                        except Exception as e:
                            st.error(f"❌ Failed: {e}")
                
                with col2:
                    if st.button("🔄 Reset Database", use_container_width=True):
                        st.warning("⚠️ This will delete ALL data!")
                        if st.button("⚠️ Confirm Reset"):
                            try:
                                import os
                                if data_access.DB_PATH.exists():
                                    os.remove(data_access.DB_PATH)
                                data_access.init_db()
                                st.success("✅ Database reset")
                            except Exception as e:
                                st.error(f"❌ Failed: {e}")
