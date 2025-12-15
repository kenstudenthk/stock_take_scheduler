# app.py

import streamlit as st
import os
from pathlib import Path

# ========== 1. 最先執行：設定頁面配置 ==========
st.set_page_config(
    page_title="Stock Take Scheduler",
    page_icon="📦",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ========== 2. Import 核心模組（不含 UI） ==========
from core import data_access, holidays

# ========== 3. 立即初始化資料庫 ==========
# ✅ 這必須在 import UI 模組之前執行！
data_access.init_db()

# ========== 4. 現在才 import UI 模組 ==========
import ui.today_schedule as today_schedule
import ui.view_schedule as view_schedule
import ui.all_shops as all_shops
import ui.generate_schedule as generate_schedule
import ui.settings as settings

# ========== 5. 定義常數 ==========
TAB_TITLES = [
    "📅 Today Schedule",
    "🗓️ Generate Schedule",
    "🗺️ All Shops",
    "🔍 View Schedule",
    "⚙️ Settings",
]


def initialize_app():
    """Initialize database and default data on first run."""
    # 資料庫已經在上面初始化了，這裡只檢查是否需要首次設定
    try:
        init_flag = data_access.get_setting("app_initialized", None)
    except Exception:
        init_flag = None
    
    # 如果未初始化，執行首次設定
    if not init_flag:
        with st.spinner("Initializing application for first time..."):
            # A. Import shops from SharePoint (優先) or CSV
            try:
                # ✅ 優先從 SharePoint 匯入
                sharepoint_url = data_access.get_setting("SHAREPOINT_LIST_URL")
                sharepoint_token = data_access.get_setting("SHAREPOINT_ACCESS_TOKEN")
                
                if sharepoint_url and sharepoint_token:
                    st.info("📥 Importing from SharePoint...")
                    result = data_access.import_shops_from_sharepoint(overwrite=False)
                    st.toast(f"✓ Imported {result['success']} shops from SharePoint")
                else:
                    # 備用：從 CSV 匯入
                    st.info("📥 Importing from CSV...")
                    data_access.import_shops_from_csv(overwrite=False)
                    st.toast("✓ Imported shop data from CSV")
                    
            except FileNotFoundError:
                st.warning("⚠️ Shop CSV file not found. Please upload data via Settings.")
            except Exception as e:
                st.error(f"Error importing shops: {str(e)}")
            
            # B. Initialize default holidays
            try:
                holidays.init_default_holidays()
                st.toast("✓ Initialized default Hong Kong holidays")
            except Exception as e:
                st.warning(f"Could not initialize holidays: {str(e)}")
            
            # C. Set initialization flag
            data_access.set_setting("app_initialized", "true")
            data_access.set_setting("app_version", "1.0.0")
            st.success("✅ App initialized! Go to Settings to configure.")


def main():
    """Main application entry point."""
    
    # --- 🛠️ Debug Sidebar ---
    with st.sidebar:
         st.title("🔧 Debug Tools")
         st.caption("Admin use only")
    
    # ✅ 新增：強制重建表格按鈕
    if st.button("⚡ 強制重建表格 (Fix Schema)", type="primary"):
        try:
            with data_access.get_db_connection() as conn:
                cur = conn.cursor()
                
                # 1. 刪除舊表格
                st.info("🗑️ 刪除舊表格...")
                cur.execute("DROP TABLE IF EXISTS shop_master;")
                cur.execute("DROP TABLE IF EXISTS schedule;")
                cur.execute("DROP TABLE IF EXISTS holidays;")
                cur.execute("DROP TABLE IF EXISTS settings;")
                conn.commit()
                
                st.success("✅ 舊表格已刪除")
                
            # 2. 重新建立正確的 schema
            st.info("🔨 建立新表格...")
            data_access.init_db()
            
            # 3. 重新匯入資料
            st.info("📥 從 SharePoint 匯入資料...")
            result = data_access.import_shops_from_sharepoint(overwrite=False)
            
            st.success(f"""
            ✅ 表格重建完成!
            - 成功匯入: {result['success']} 筆
            - 失敗: {result['failed']} 筆
            - 跳過: {result['skipped']} 筆
            """)
            
            # 4. 初始化假期
            holidays.init_default_holidays()
            
            # 5. 重置初始化標誌
            data_access.set_setting("app_initialized", "true")
            
            st.balloons()
            st.info("請重新整理頁面以載入新資料")
            
        except Exception as e:
            st.error(f"❌ 重建失敗: {e}")
            import traceback
            st.code(traceback.format_exc())
    
    # 2. Display header
    st.title("📦 Stock Take Scheduler")
    st.caption("Hong Kong Store Stock Take Planning Tool")
    
    # 3. Create tabs
    tab1, tab2, tab3, tab4, tab5 = st.tabs(TAB_TITLES)
    
    # 4. Render each tab
    with tab1:
        today_schedule.render()
    
    with tab2:
        generate_schedule.render()
    
    with tab3:
        all_shops.render()
    
    with tab4:
        view_schedule.render()
    
    with tab5:
        settings.render()
    
    # 5. Footer
    st.markdown("---")
    col1, col2, col3 = st.columns([2, 1, 1])
    
    with col1:
        try:
            total = data_access.count_active_shops()
            st.caption(f"📊 Total active shops: {total}")
        except:
            st.caption("📊 Total active shops: (Loading...)")
    
    with col2:
        ver = data_access.get_setting("app_version", "1.0.0")
        st.caption(f"Version: {ver}")
    
    with col3:
        if st.button("🔄 Soft Reset"):
            data_access.set_setting("app_initialized", "false")
            st.rerun()


if __name__ == "__main__":
    main()
