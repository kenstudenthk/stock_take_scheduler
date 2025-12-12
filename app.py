# app.py
import streamlit as st
import ui.today_schedule as today_schedule
import ui.view_schedule as view_schedule
import ui.all_shops as all_shops



# ✅ CRITICAL: st.set_page_config() MUST be the first Streamlit command
st.set_page_config(
    page_title="Stock Take Scheduler",
    page_icon="📦",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# Import after set_page_config
from core import data_access, holidays
from ui import today_schedule, generate_schedule, view_schedule, settings


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



def main():
    """Main application entry point."""
    # st.set_page_config(...)
    
    # --- 暫時除錯用 ---
    import sqlite3
    conn = sqlite3.connect('data/stock_take.db') # 或是你的 db 路徑
    st.write("Shop Master Columns:", [row[1] for row in conn.execute("PRAGMA table_info(shop_master)")])
    conn.close()
    # ----------------
    
    initialize_app()
    
    # Header
    st.title("📦 Stock Take Scheduler")
    st.caption("Hong Kong Store Stock Take Planning Tool")
    
    # Main tabs
    tab1, tab2, tab3, tab4, tab5 = st.tabs(TAB_TITLES)

    with tab1:
        today_schedule.render()

    with tab2:
        generate_schedule.render()

    with tab3:
        all_shops.render()          # ✅ 新的 All Shops 頁

    with tab4:
        view_schedule.render()

    with tab5:
        settings.render()

    
    # Footer
    st.markdown("---")
    col1, col2, col3 = st.columns([2, 1, 1])
    
    with col1:
        total_shops = data_access.count_active_shops()
        st.caption(f"📊 Total active shops: {total_shops}")
    
    with col2:
        app_version = data_access.get_setting("app_version", "1.0.0")
        st.caption(f"Version: {app_version}")
    
    with col3:
        # ✅ Add a reset button (admin use)
        if st.button("🔄 Reset initialization", help="Re-import data and reset app"):
            data_access.set_setting("app_initialized", "false")
            st.rerun()


if __name__ == "__main__":
    main()
