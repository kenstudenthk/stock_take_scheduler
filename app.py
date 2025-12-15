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
        
        # ✅ 修正：使用正確的資料庫路徑
        db_path = data_access.DB_PATH
        
        # Reset database button
        if st.button("🚨 重置資料庫 (Fix Schema)", help="刪除並重建資料庫表"):
            try:
                deleted = False
                if db_path.exists():
                    os.remove(db_path)
                    deleted = True
                
                # Reinitialize DB
                data_access.init_db()
                
                # ✅ 重置初始化標誌,觸發重新匯入
                data_access.set_setting("app_initialized", "false")
                
                if deleted:
                    st.success("✅ 舊資料庫已刪除並重建！點擊下方 Soft Reset 重新匯入資料。")
                else:
                    st.warning("找不到舊資料庫，已建立新資料庫。")
                    
            except Exception as e:
                st.error(f"重置失敗: {e}")
                import traceback
                st.code(traceback.format_exc())
        
        # Check DB schema
        try:
            if db_path.exists():
                with data_access.get_db_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute("PRAGMA table_info(shop_master);")
                    columns = [info[1] for info in cursor.fetchall()]
                
                with st.expander("🔍 DB Schema Check"):
                    st.write(f"**DB Path:** `{db_path}`")
                    st.write(f"**Exists:** {db_path.exists()}")
                    st.write(f"**Size:** {os.path.getsize(db_path)} bytes")
                    st.write("**Columns:**")
                    st.code(", ".join(columns))
                    
                    # ✅ 檢查關鍵欄位
                    required_cols = ["region", "district", "address", "lat", "lng"]
                    missing = [c for c in required_cols if c not in columns]
                    
                    if not missing:
                        st.success("✅ All required columns present")
                    else:
                        st.error(f"❌ Missing columns: {missing}")
                        
                    # 顯示資料筆數
                    with data_access.get_db_connection
