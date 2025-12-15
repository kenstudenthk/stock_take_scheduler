# ui/settings.py
import streamlit as st
from core import data_access


def render():
    """Render the Settings page."""
    st.subheader("⚙️ Settings")
    
    # ========== 1. General Settings ==========
    st.markdown("### 📋 General Settings")
    
    # ✅ 在函數內讀取設定值（不是在模組載入時）
    current_shops_per_day = data_access.get_setting("shops_per_day", "20")
    current_groups_per_day = data_access.get_setting("groups_per_day", "3")
    
    col1, col2 = st.columns(2)
    
    with col1:
        shops_per_day = st.number_input(
            "Shops per day",
            min_value=1,
            max_value=60,
            value=int(current_shops_per_day) if current_shops_per_day else 20,
            help="Maximum number of shops to schedule per day",
            key="shops_per_day_input"
        )
    
    with col2:
        groups_per_day = st.number_input(
            "Groups per day",
            min_value=1,
            max_value=10,
            value=int(current_groups_per_day) if current_groups_per_day else 3,
            help="Number of teams working per day",
            key="groups_per_day_input"
        )
    
    if st.button("💾 Save General Settings", key="save_general"):
        data_access.set_setting("shops_per_day", str(shops_per_day))
        data_access.set_setting("groups_per_day", str(groups_per_day))
        data_access.set_setting("shops_per_group", str(shops_per_day // groups_per_day))
        st.success("✅ General settings saved!")
    
    st.markdown("---")
    
    # ========== 2. SharePoint Integration ==========
    st.markdown("### 📊 SharePoint Integration")
    
    # ✅ 在函數內讀取設定值
    current_sp_url = data_access.get_setting("SHAREPOINT_LIST_URL", "")
    current_sp_token = data_access.get_setting("SHAREPOINT_ACCESS_TOKEN", "")
    current_status_field = data_access.get_setting("SHAREPOINT_STATUS_FIELD", "ScheduleStatus")
    
    sharepoint_url = st.text_input(
        "SharePoint List URL (Microsoft Graph)",
        value=current_sp_url,
        help=(
            "Format: https://graph.microsoft.com/v1.0/sites/{site-id}/lists/{list-id}\n\n"
            "Example: https://graph.microsoft.com/v1.0/sites/f6281a1f-762e-4216-a070-3b1ddb8dbdc7,c741a961-4f9b-4f24-aaef-af319d78cfa6/lists/ce3a752e-7609-4468-81f8-8babaf503ad8"
        ),
        key="sp_url_input"
    )
    
    sharepoint_token = st.text_input(
        "Access Token (from Graph Explorer)",
        value=current_sp_token,
        type="password",
        help="Get token from: https://developer.microsoft.com/en-us/graph/graph-explorer",
        key="sp_token_input"
    )
    
    status_field = st.text_input(
        "Status Field Internal Name",
        value=current_status_field,
        help="The internal field name for schedule status (default: ScheduleStatus)",
        key="sp_status_field_input"
    )
    
    if st.button("💾 Save SharePoint Settings", key="save_sp"):
        data_access.set_setting("SHAREPOINT_LIST_URL", sharepoint_url)
        data_access.set_setting("SHAREPOINT_ACCESS_TOKEN", sharepoint_token)
        data_access.set_setting("SHAREPOINT_STATUS_FIELD", status_field)
        st.success("✅ SharePoint settings saved!")
    
    # ✅ Test Connection Button
    if st.button("🧪 Test SharePoint Connection", key="test_sp"):
        if not sharepoint_url or not sharepoint_token:
            st.error("❌ Please fill in URL and Token first")
        else:
            with st.spinner("Testing connection..."):
                try:
                    import requests
                    
                    # Simple test: Get first item
                    test_url = f"{sharepoint_url}/items?$top=1&$select=id&$expand=fields($select=field_6,Title)"
                    headers = {
                        "Authorization": f"Bearer {sharepoint_token}",
                        "Accept": "application/json"
                    }
                    response = requests.get(test_url, headers=headers, timeout=10)
                    
                    if response.status_code == 200:
                        data = response.json()
                        items = data.get("value", [])
                        if items:
                            st.success(f"✅ Connection successful! Found {len(items)} item(s)")
                            with st.expander("📋 Sample data"):
                                st.json(items[0])
                        else:
                            st.warning("⚠️ Connection OK but list is empty")
                    else:
                        st.error(f"❌ Connection failed: {response.status_code}")
                        with st.expander("Show error"):
                            st.code(response.text)
                except Exception as e:
                    st.error(f"❌ Connection error: {str(e)}")
    
    st.markdown("---")
    
    # ========== 3. AMap API Settings ==========
    st.markdown("### 🗺️ AMap API Settings")
    
    # ✅ 在函數內讀取設定值
    current_amap_key = data_access.get_setting("AMAP_WEB_KEY", "")
    
    amap_key = st.text_input(
        "AMap Web Service API Key",
        value=current_amap_key,
        type="password",
        help="Get your key from: https://console.amap.com/",
        key="amap_key_input"
    )
    
    if st.button("💾 Save AMap Settings", key="save_amap"):
        data_access.set_setting("AMAP_WEB_KEY", amap_key)
        st.success("✅ AMap settings saved!")
    
    st.markdown("---")
    
    # ========== 4. Holidays Management ==========
    st.markdown("### 📅 Holidays Management")
    
    from core import holidays
    
    # Display existing holidays
    try:
        holiday_df = holidays.get_holiday_df()
        
        if not holiday_df.empty:
            st.dataframe(
                holiday_df,
                use_container_width=True,
                hide_index=True
            )
        else:
            st.info("No holidays configured yet.")
    except Exception as e:
        st.error(f"Error loading holidays: {str(e)}")
    
    # Add new holiday
    st.markdown("#### ➕ Add New Holiday")
    
    col_date, col_name = st.columns(2)
    
    with col_date:
        new_holiday_date = st.date_input(
            "Holiday Date",
            key="new_holiday_date"
        )
    
    with col_name:
        new_holiday_name = st.text_input(
            "Holiday Name (Chinese)",
            placeholder="例如：農曆新年",
            key="new_holiday_name"
        )
    
    if st.button("➕ Add Holiday", key="add_holiday"):
        if new_holiday_name:
            holidays.add_holiday(
                new_holiday_date.isoformat(),
                new_holiday_name,
                "Statutory"
            )
            st.success(f"✅ Added holiday: {new_holiday_name}")
            st.rerun()
        else:
            st.error("❌ Please enter holiday name")
    
    # Initialize default holidays
    if st.button("📥 Initialize Default HK Holidays", key="init_holidays"):
        try:
            holidays.init_default_holidays()
            st.success("✅ Default Hong Kong holidays initialized!")
            st.rerun()
        except Exception as e:
            st.error(f"❌ Error: {str(e)}")
    
    st.markdown("---")
    
    # ========== 5. Database Management ==========
    st.markdown("### 🗄️ Database Management")
    
    st.warning("⚠️ **Danger Zone**: These actions may delete data!")
    
    col_db1, col_db2 = st.columns(2)
    
    with col_db1:
        if st.button("🔄 Clear All Schedules", key="clear_schedules"):
            with data_access.get_db_connection() as conn:
                cur = conn.cursor()
                cur.execute("DELETE FROM schedule;")
            st.success("✅ All schedules cleared")
            st.rerun()
    
    with col_db2:
        if st.button("🔄 Re-import Shop Data", key="reimport_shops"):
            try:
                data_access.import_shops_from_csv(overwrite=True)
                st.success("✅ Shop data re-imported from CSV")
                st.rerun()
            except Exception as e:
                st.error(f"❌ Import failed: {str(e)}")


# ❌ 刪除所有在模組層級的 get_setting() 呼叫
# 例如：不要在這裡寫 default_value = data_access.get_setting(...)
