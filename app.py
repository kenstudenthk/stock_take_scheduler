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
    try:
        init_flag = data_access.get_setting("app_initialized", None)
    except Exception:
        init_flag = None
    
    if not init_flag:
        with st.spinner("Initializing application for first time..."):
            # A. Import shops from SharePoint or CSV
            try:
                sp_url = data_access.get_setting("SHAREPOINT_LIST_URL")
                sp_token = data_access.get_setting("SHAREPOINT_ACCESS_TOKEN")
                
                if sp_url and sp_token:
                    result = data_access.import_shops_from_sharepoint(overwrite=False)
                    st.toast(f"✓ Imported {result['success']} shops from SharePoint")
                else:
                    data_access.import_shops_from_csv(overwrite=False)
                    st.toast("✓ Imported shop data from CSV")
            except FileNotFoundError:
                st.warning("⚠️ Shop data not found. Please configure in Settings.")
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


def main():
    """Main application entry point."""
    
    # ========== Sidebar: Debug Tools ==========
    with st.sidebar:
        st.title("🔧 Debug Tools")
        st.caption("Admin use only")
        
        # === 即時診斷 ===
        with st.expander("🔍 即時診斷", expanded=True):
            db_path = data_access.DB_PATH
            
            if db_path.exists():
                st.success(f"✅ DB 存在")
                st.caption(f"大小: {os.path.getsize(db_path)} bytes")
                
                try:
                    with data_access.get_db_connection() as conn:
                        cur = conn.cursor()
                        
                        # 檢查表格
                        cur.execute("SELECT name FROM sqlite_master WHERE type='table';")
                        tables = [row[0] for row in cur.fetchall()]
                        st.write("**表格:**", ", ".join(tables))
                        
                        # 檢查 shop_master 欄位
                        if "shop_master" in tables:
                            cur.execute("PRAGMA table_info(shop_master);")
                            columns = [col[1] for col in cur.fetchall()]
                            
                            required = ["region", "district", "address"]
                            missing = [c for c in required if c not in columns]
                            
                            if missing:
                                st.error(f"❌ 缺少: {', '.join(missing)}")
                                st.warning("⚠️ 需要執行重建!")
                            else:
                                st.success("✅ Schema 正確")
                                cur.execute("SELECT COUNT(*) FROM shop_master;")
                                count = cur.fetchone()[0]
                                st.metric("店舖總數", count)
                        else:
                            st.error("❌ shop_master 不存在")
                            
                except Exception as e:
                    st.error(f"診斷失敗: {e}")
            else:
                st.error("❌ 資料庫不存在")
        
        # 在 app.py 側邊欄中,在診斷區塊後加入

        st.markdown("---")
        st.subheader("🔥 快速修復")

        if st.button("⚡ 一鍵修復 Schema", type="primary", use_container_width=True):
            with st.spinner("執行中..."):
                try:
                    import os
                    
                    # 1. 獲取備份
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
                    db_path = data_access.DB_PATH
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
                    st.success("✅ 修復完成!")
                    st.balloons()
                    
                    # 強制重新整理
                    st.rerun()
                    
                except Exception as e:
                    st.error(f"❌ 修復失敗: {e}")
                    import traceback
                    st.code(traceback.format_exc())

        
        # ✅ 所有邏輯都在這個 if 區塊內
        if st.button("💥 執行完整重建", type="primary", use_container_width=True):
            # ✅ 確認對話框也在 if 內
            confirm = st.checkbox("⚠️ 我了解此操作會刪除所有資料")
            
            if confirm:  # ✅ 只有確認後才執行
                try:
                    progress = st.progress(0, text="準備中...")
                    
                    # === 步驟 1: 備份設定 ===
                    progress.progress(10, text="1️⃣ 備份設定...")
                    backup = {}
                    
                    try:
                        with data_access.get_db_connection() as conn:
                            cur = conn.cursor()
                            cur.execute("SELECT key, value FROM settings;")
                            backup = {row[0]: row[1] for row in cur.fetchall()}
                        
                        old_url = backup.get("SHAREPOINT_LIST_URL")
                        old_token = backup.get("SHAREPOINT_ACCESS_TOKEN")
                        
                        st.write(f"✓ 已備份 {len(backup)} 個設定")
                        if old_url:
                            st.write(f"  - SharePoint URL: {old_url[:30]}...")
                        if old_token:
                            st.write(f"  - Access Token: {'*' * 20}")
                    except:
                        old_url = None
                        old_token = None
                        st.warning("⚠️ 無法備份設定")
                    
                    # === 步驟 2: 刪除資料庫 ===
                    progress.progress(20, text="2️⃣ 刪除舊資料庫...")
                    
                    db_path = data_access.DB_PATH
                    if db_path.exists():
                        os.remove(db_path)
                        st.write("✓ 已刪除舊資料庫")
                    else:
                        st.write("ℹ️ 資料庫不存在")
                    
                    # === 步驟 3: 建立新表格 ===
                    progress.progress(40, text="3️⃣ 建立新表格...")
                    
                    with data_access.get_db_connection() as conn:
                        cur = conn.cursor()
                        
                        # Shop Master
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
                    
                    st.write("✓ 新表格已建立")
                    
                    # === 步驟 4: 驗證 Schema ===
                    progress.progress(50, text="4️⃣ 驗證 Schema...")
                    
                    with data_access.get_db_connection() as conn:
                        cur = conn.cursor()
                        cur.execute("PRAGMA table_info(shop_master);")
                        columns = [col[1] for col in cur.fetchall()]
                    
                    required = ["region", "district", "address", "lat", "lng"]
                    missing = [c for c in required if c not in columns]
                    
                    if missing:
                        st.error(f"❌ Schema 驗證失敗: 缺少 {missing}")
                        st.stop()
                    
                    st.write(f"✓ Schema 驗證通過: {', '.join(columns[:8])}...")
                    
                    # === 步驟 5: 恢復設定 ===
                    progress.progress(60, text="5️⃣ 恢復設定...")
                    
                    for key, value in backup.items():
                        data_access.set_setting(key, value)
                    
                    st.write(f"✓ 已恢復 {len(backup)} 個設定")
                    
                    # === 步驟 6: 匯入資料 ===
                    progress.progress(70, text="6️⃣ 匯入店舖資料...")
                    
                    if old_url and old_token:
                        st.write("📥 從 SharePoint 匯入...")
                        result = data_access.import_shops_from_sharepoint(
                            list_url=old_url,
                            token=old_token,
                            overwrite=False
                        )
                        st.write(f"✓ 成功: {result['success']}, 失敗: {result['failed']}, 跳過: {result['skipped']}")
                    else:
                        st.warning("⚠️ 請前往 Settings 設定 SharePoint")
                    
                    # === 步驟 7: 初始化假期 ===
                    progress.progress(85, text="7️⃣ 初始化假期...")
                    
                    holidays.init_default_holidays()
                    st.write("✓ 假期已初始化")
                    
                    # === 步驟 8: 完成 ===
                    progress.progress(100, text="✅ 完成!")
                    
                    data_access.set_setting("app_initialized", "true")
                    data_access.set_setting("app_version", "1.0.0")
                    
                    st.balloons()
                    st.success("🎉 重建完成!")
                    st.info("請重新整理頁面")
                    
                    # 重新整理按鈕
                    if st.button("🔄 重新整理頁面", type="primary", key="reload"):
                        st.rerun()
                    
                except Exception as e:
                    st.error(f"❌ 重建失敗: {e}")
                    import traceback
                    with st.expander("查看錯誤詳情"):
                        st.code(traceback.format_exc())
    
    # ========== 主內容區域 (不在 sidebar 內!) ==========
    
    # 1. 初始化檢查
    initialize_app()
    
    # 2. Header
    st.title("📦 Stock Take Scheduler")
    st.caption("Hong Kong Store Stock Take Planning Tool")
    
    # ... 其餘主內容 ...

    
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
        ver = data_access.get_setting("app_version", "1.0.0")
        st.caption(f"Version: {ver}")
    
    with col3:
        if st.button("🔄 Soft Reset", help="重新執行初始化"):
            data_access.set_setting("app_initialized", "false")
            st.rerun()


if __name__ == "__main__":
    main()
