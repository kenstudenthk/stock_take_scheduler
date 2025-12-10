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
    
    # Check if initialization is needed (using a flag in settings)
    init_flag = data_access.get_setting("app_initialized", None)
    
    if init_flag is None:
        with st.spinner("Initializing application for first time..."):
            # 1. Initialize database structure
            data_access.init_db()
            
            # 2. Import shops from CSV
            try:
                data_access.import_shops_from_csv(overwrite=True)
                st.success("✓ Imported shop data successfully")
            except FileNotFoundError:
                st.warning("⚠️ Shop CSV file not found. Please add shops manually in Settings.")
            except Exception as e:
                st.error(f"Error importing shops: {str(e)}")
            
            # 3. Initialize default holidays
            try:
                holidays.init_default_holidays()
                st.success("✓ Initialized default Hong Kong holidays")
            except Exception as e:
                st.warning(f"Could not initialize holidays: {str(e)}")
            
            # 4. Set initialization flag
            data_access.set_setting("app_initialized", "true")
            data_access.set_setting("app_version", "1.0.0")
            
            st.success("✅ Application initialized successfully!")
            st.info("👉 Please go to Settings to configure your AMap API key.")
    else:
        # Already initialized, just ensure database structure is up-to-date
        data_access.init_db()


def main():
    """Main application entry point."""
    
    # Initialize app on first run
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
