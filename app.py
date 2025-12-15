# app.py

import streamlit as st
import os

# ========== 1. 頁面配置 (必須最先執行) ==========
st.set_page_config(
    page_title="Stock Take Scheduler",
    page_icon="📦",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ========== 2. Import 核心模組 ==========
from core import data_access, holidays

# ========== 3. 初始化資料庫 ==========
data_access.init_db()

# ========== 4. Import UI 模組 ==========
import ui.today_schedule as today_schedule
import ui.view_schedule as view_schedule
import ui.all_shops as all_shops
import ui.generate_schedule as generate_schedule
import ui.settings as settings

# ========== 5. 常數定義 ==========
TAB_TITLES = [
    "📅 Today Schedule",
    "🗓️ Generate Schedule",
    "🗺️ All Shops",
    "🔍 View Schedule",
    "⚙️ Settings",
]


def initialize_app():
    """首次初始化檢查"""
    try:
        init_flag = data_access.get_setting("app_initialized", None)
    except Exception:
        init_flag = None
    
    if not init_flag:
        with st.spinner("Initializing application..."):
            # 嘗試從 SharePoint 匯入
            try:
                sp_url = data_access.get_setting("SHAREPOINT_LIST_URL")
                sp_token = data_access.get_setting("SHAREPOINT_ACCESS_TOKEN")
                
                if sp_url and sp_token:
                    result = data_access.import_shops_from_sharepoint(overwrite=False)
                    st.toast(f"✓ Imported {result['success']} shops")
                else:
                    st.warning("⚠️ Please configure SharePoint in Settings")
            except Exception as e:
                st.warning(f"⚠️ Import failed: {str(e)}")
            
            # 初始化假期
            try:
                holidays.init_default_holidays()
                st.toast("✓ Holidays initialized")
            except Exception as e:
                st.warning(f"⚠️ Holidays init failed: {str(e)}")
            
            # 設定標誌
            data_access.set_setting("app_initialized", "true")
            data_access.set_setting("app_version", "1.0.0")


def main():
    """Main application entry point."""
    
    # ========== 側邊欄: Debug Tools ==========
    with st.sidebar:
        st.title("🔧 Debug Tools")
        st.caption("Admin use only")
        
        # === 強制修復按鈕 (最優先) ===
        if st.button("🔥 強制修復資料庫", type="primary", use_container_width=True):
            try:
                import os
                
                st.info("開始修復...")
                
                # 1. 備份 SharePoint 設定
                backup = {}
                db_path = data_access.DB_PATH
                
                if db_path.exists():
                    try:
                        with data_access.get_db_connection() as conn:
                            cur = conn.cursor()
                            cur.execute("SELECT key, value FROM settings;")
                            backup = {row[0]: row[1] for row in cur.fetchall()}
                        st.write(f"✓ 已備份 {len(backup)} 個設定")
                    except:
                        st.write("⚠️ 無法備份設定")
                
                sp_url = backup.get("SHAREPOINT_LIST_URL")
                sp_token = backup.get("SHAREPOINT_ACCESS_TOKEN")
                
                # 2. 完全刪除資料庫檔案
                if db_path.exists():
                    os.remove(db_path)
                    st.write(f"✓ 已刪除: {db_path}")
                
                # 3. 使用正確的 SQL 直接建立表格
                st.write("正在建立新表格...")
                
                import sqlite3
                conn = sqlite3.connect(db_path)
                cur = conn.cursor()
                
                # Shop Master (使用正確的欄位名稱)
                cur.execute("""
                    CREATE TABLE shop_master (
                        shop_id TEXT PRIMARY KEY,
                        shop_name TEXT,
                        address TEXT,
                        region TEXT,
                        district TEXT,
                        brand TEXT,
                        brand_code TEXT,
                        division TEXT,
                        english_address TEXT,
                        location TEXT,
                        lat REAL,
                        lng REAL,
                        brand_icon_url TEXT,
                        is_mtr TEXT DEFAULT 'N',
                        phone TEXT,
                        is_active TEXT DEFAULT 'Y'
                    );
                """)
                
                # Schedule
                cur.execute("""
                    CREATE TABLE schedule (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        shop_id TEXT NOT NULL,
                        shop_name TEXT,
                        address TEXT,
                        region TEXT,
                        district TEXT,
                        brand TEXT,
                        lat REAL,
                        lng REAL,
                        is_mtr TEXT DEFAULT 'N',
                        schedule_date TEXT NOT NULL,
                        group_number INTEGER,
                        status TEXT DEFAULT 'Planned',
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    );
                """)
                
                # Settings
                cur.execute("""
                    CREATE TABLE settings (
                        key TEXT PRIMARY KEY,
                        value TEXT
                    );
                """)
                
                # Holidays
                cur.execute("""
                    CREATE TABLE holidays (
                        date TEXT PRIMARY KEY,
                        name_chi TEXT,
                        type TEXT
                    );
                """)
                
                conn.commit()
                conn.close()
                
                st.write("✓ 新表格已建立")
                
                # 4. 驗證 Schema
                conn = sqlite3.connect(db_path)
                cur = conn.cursor()
                cur.execute("PRAGMA table_info(shop_master);")
                columns = [col[1] for col in cur.fetchall()]
                conn.close()
                
                st.write(f"✓ 欄位: {', '.join(columns)}")
                
                if "region" in columns and "district" in columns and "address" in columns:
                    st.success("✅ Schema 驗證成功!")
                else:
                    st.error("❌ Schema 仍然錯誤!")
                    st.stop()
                
                # 5. 恢復設定
                for key, value in backup.items():
                    data_access.set_setting(key, value)
                st.write(f"✓ 已恢復 {len(backup)} 個設定")
                
                # 6. 匯入資料
                if sp_url and sp_token:
                    st.write("正在從 SharePoint 匯入...")
                    result = data_access.import_shops_from_sharepoint(
                        list_url=sp_url,
                        token=sp_token,
                        overwrite=False
                    )
                    st.success(f"✅ 成功匯入 {result['success']} 間店舖!")
                else:
                    st.warning("⚠️ 請到 Settings 設定 SharePoint")
                
                # 7. 初始化假期
                holidays.init_default_holidays()
                st.write("✓ 假期已初始化")
                
                # 8. 完成
                data_access.set_setting("app_initialized", "true")
                st.balloons()
                st.success("🎉 修復完成!")
                st.info("請按 Ctrl+Shift+R (或 Cmd+Shift+R) 強制重新整理頁面")
                
            except Exception as e:
                st.error(f"❌ 修復失敗: {e}")
                import traceback
                st.code(traceback.format_exc())
        
        # === 診斷區塊 ===
        st.markdown("---")
        with st.expander("🔍 即時診斷"):
            db_path = data_access.DB_PATH
            
            if db_path.exists():
                st.success("✅ DB 存在")
                
                try:
                    with data_access.get_db_connection() as conn:
                        cur = conn.cursor()
                        cur.execute("PRAGMA table_info(shop_master);")
                        columns = [col[1] for col in cur.fetchall()]
                        
                        required = ["region", "district", "address"]
                        missing = [c for c in required if c not in columns]
                        
                        if missing:
                            st.error(f"❌ 缺少欄位: {', '.join(missing)}")
                        else:
                            st.success("✅ Schema 正確")
                            cur.execute("SELECT COUNT(*) FROM shop_master;")
                            count = cur.fetchone()[0]
                            st.metric("店舖總數", count)
                except Exception as e:
                    st.error(f"診斷失敗: {e}")
            else:
                st.error("❌ 資料庫不存在")

        
        # === 一鍵修復按鈕 ===
        st.markdown("---")
        
        if st.button("⚡ 一鍵修復", type="primary", use_container_width=True):
            with st.spinner("修復中..."):
                try:
                    # 1. 備份設定
                    backup = {}
                    try:
                        with data_access.get_db_connection() as conn:
                            cur = conn.cursor()
                            cur.execute("SELECT key, value FROM settings;")
                            backup = {row[0]: row[1] for row in cur.fetchall()}
                    except:
                        pass
                    
                    sp_url = backup.get("SHAREPOINT_LIST_URL")
                    sp_token = backup.get("SHAREPOINT_ACCESS_TOKEN")
                    
                    # 2. 刪除資料庫
                    if db_path.exists():
                        os.remove(db_path)
                    
                    # 3. 重新初始化
                    data_access.init_db()
                    
                    # 4. 恢復設定
                    for key, value in backup.items():
                        data_access.set_setting(key, value)
                    
                    # 5. 匯入資料
                    if sp_url and sp_token:
                        result = data_access.import_shops_from_sharepoint(
                            list_url=sp_url,
                            token=sp_token,
                            overwrite=False
                        )
                        st.success(f"✅ 匯入 {result['success']} 間店舖")
                    else:
                        st.warning("⚠️ 請到 Settings 設定 SharePoint")
                    
                    # 6. 初始化假期
                    holidays.init_default_holidays()
                    
                    # 7. 完成
                    st.balloons()
                    st.success("🎉 修復完成!")
                    st.info("請重新整理頁面")
                    
                except Exception as e:
                    st.error(f"❌ 修復失敗: {e}")
                    import traceback
                    with st.expander("錯誤詳情"):
                        st.code(traceback.format_exc())
    
    # ========== 主內容區域 ==========
    
    # 1. 初始化檢查
    initialize_app()
    
    # 2. Header
    st.title("📦 Stock Take Scheduler")
    st.caption("Hong Kong Store Stock Take Planning Tool")
    
    # 3. Tabs
    tab1, tab2, tab3, tab4, tab5 = st.tabs(TAB_TITLES)
    
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
    
    # 4. Footer
    st.markdown("---")
    col1, col2, col3 = st.columns([2, 1, 1])
    
    with col1:
        try:
            total = data_access.count_active_shops()
            st.caption(f"📊 Total active shops: {total}")
        except:
            st.caption("📊 Total active shops: (Loading...)")
    
    with col2:
        try:
            ver = data_access.get_setting("app_version", "1.0.0")
            st.caption(f"Version: {ver}")
        except:
            st.caption("Version: 1.0.0")
    
    with col3:
        if st.button("🔄 Soft Reset", help="重新執行初始化"):
            data_access.set_setting("app_initialized", "false")
            st.rerun()


if __name__ == "__main__":
    main()
