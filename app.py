# app.py
import streamlit as st
import os

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
            # A. Import shops from CSV
            try:
                data_access.import_shops_from_csv(overwrite=True)
                st.toast("✓ Imported shop data successfully")
            except FileNotFoundError:
                st.warning("⚠️ Shop CSV file not found (data/MxStockTakeMasterList.csv).")
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
        
        # Reset database button
        if st.button("🚨 重置資料庫 (Fix Schema)", help="刪除並重建資料庫表"):
            try:
                # Try to delete common DB paths
                db_files = ["data/stock_take.db", "data/db.sqlite"]
                deleted = False
                
                for f in db_files:
                    if os.path.exists(f):
                        os.remove(f)
                        deleted = True
                
                # Reinitialize DB
                data_access.init_db()
                
                if deleted:
                    st.success("舊資料庫已刪除並重建！請手動重新整理網頁。")
                else:
                    st.warning("找不到舊資料庫，已建立新資料庫。")
            except Exception as e:
                st.error(f"重置失敗: {e}")
        
        # Check DB schema
        try:
            import sqlite3
            
            db_path = "data/db.sqlite"
            if not os.path.exists(db_path):
                db_path = "data/stock_take.db"
            
            if os.path.exists(db_path):
                conn = sqlite3.connect(db_path)
                cursor = conn.cursor()
                cursor.execute("PRAGMA table_info(shop_master);")
                columns = [info[1] for info in cursor.fetchall()]
                conn.close()
                
                with st.expander("🔍 DB Schema Check"):
                    st.write(f"DB: {db_path}")
                    st.write(columns)
                    if "lat" in columns and "lng" in columns:
                        st.success("✅ lat/lng OK")
                    else:
                        st.error("❌ lat/lng MISSING")
            else:
                st.warning("⚠️ DB file not found yet.")
        except Exception:
            pass  # Ignore debug tool errors
    
    # --- Main App Flow ---
    # 1. Run initialization check
    initialize_app()
    
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
