import streamlit as st
import os

# --------------------------------------------------------------------------------
# 1. 這是全域唯一的 set_page_config，放在最上面，其他地方全部刪除
# --------------------------------------------------------------------------------
st.set_page_config(
    page_title="Stock Take Scheduler",
    page_icon="📦",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# 2. Import 其他模組 (必須在 set_page_config 之後)
import ui.today_schedule as today_schedule
import ui.view_schedule as view_schedule
import ui.all_shops as all_shops
import ui.generate_schedule as generate_schedule
import ui.settings as settings
from core import data_access, holidays


TAB_TITLES = [
    "📅 Today Schedule",
    "🗓️ Generate Schedule",
    "🗺️ All Shops",        # ✅ 新增
    "🔍 View Schedule",
    "⚙️ Settings",
]



def initialize_app():
    """Initialize database and default data on first run."""
    
    # 1. Always ensure DB structure exists first
    # This creates tables if they are missing (safe to run every time)
    data_access.init_db()

    # 2. Check if we have initialized data before
    try:
        init_flag = data_access.get_setting("app_initialized", None)
    except Exception:
        init_flag = None

    # 3. If NOT initialized, run the first-time setup
    if not init_flag:
        with st.spinner("Initializing application for first time..."):
            
            # A. Import shops from CSV
            try:
                data_access.import_shops_from_csv(overwrite=True)
                st.toast("✓ Imported shop data successfully")
            except FileNotFoundError:
                st.warning("⚠️ Shop CSV file not found (data/MxStockTakeMasterList.csv). Please upload it or re-import in Settings.")
            except Exception as e:
                st.error(f"Error importing shops: {str(e)}")
            
            # B. Initialize default holidays
            try:
                from core import holidays  # Import here to avoid circular dependency
                holidays.init_default_holidays()
                st.toast("✓ Initialized default Hong Kong holidays")
            except Exception as e:
                st.warning(f"Could not initialize holidays: {str(e)}")
            
            # C. Set initialization flag so we don't run this again
            data_access.set_setting("app_initialized", "true")
            data_access.set_setting("app_version", "1.0.0")
            
            st.success("✅ App initialized! Go to Settings to configure your API Key.")


# 5. Main 函式
def main():
    # ❌ 這裡絕對不能再有 st.set_page_config !!! 
    # 這是為了確保不會報 StreamlitAPIException

    # --- 🛠️ 側邊欄：修復工具 (Debug) ---
    with st.sidebar:
        st.title("🔧 Debug Tools")
        st.caption("Admin use only")
        
        # 重置資料庫按鈕
        if st.button("🚨 重置資料庫 (Fix Schema)", help="刪除並重建資料庫表"):
            try:
                import os
                # 嘗試刪除常見路徑的 db (確保刪乾淨)
                db_files = ["data/stock_take.db", "data/db.sqlite"]
                deleted = False
                for f in db_files:
                    if os.path.exists(f):
                        os.remove(f)
                        deleted = True
                
                # 重新初始化 DB
                data_access.init_db()
                if deleted:
                    st.success("舊資料庫已刪除並重建！請手動重新整理網頁。")
                else:
                    st.warning("找不到舊資料庫，已建立新資料庫。")
            except Exception as e:
                st.error(f"重置失敗: {e}")
        
        # 檢查欄位狀態
        try:
            import sqlite3
            # 請確認你的 data_access.py 是用哪個檔名，如果不確定就兩個都試試
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
            pass # 忽略除錯工具的錯誤
    # ---------------------------------------------

    # 1. 執行應用程式初始化 (讀取 CSV、設定 flag 等)
    initialize_app()
    
    # 2. 顯示 Header
    st.title("📦 Stock Take Scheduler")
    st.caption("Hong Kong Store Stock Take Planning Tool")
    
    # 3. 建立 Tabs 導航
    if "TAB_TITLES" not in globals():
        TAB_TITLES = ["📅 Today", "🗓️ Generate", "🗺️ Shops", "🔍 View", "⚙️ Settings"]
        
    tab1, tab2, tab3, tab4, tab5 = st.tabs(TAB_TITLES)

    # 4. 載入各個頁面模組
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

    # 5. Footer (頁尾狀態列)
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
