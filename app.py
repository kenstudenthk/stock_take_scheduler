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
    # 在 app.py 的 Debug Sidebar 中加入

with st.sidebar:
    st.title("🔧 Debug Tools")
    st.caption("Admin use only")
    
    # ========== 終極修復 ==========
    if st.button("💥 終極修復 (直接重建)", type="primary", use_container_width=True):
        st.warning("⚠️ 此操作會直接刪除並重建所有表格!")
        
        if st.checkbox("確認執行終極修復"):
            try:
                import os
                
                # === 步驟 1: 備份 SharePoint 設定 ===
                st.info("1️⃣ 備份設定...")
                backup = {}
                
                try:
                    with data_access.get_db_connection() as conn:
                        cur = conn.cursor()
                        cur.execute("SELECT key, value FROM settings;")
                        backup = {row[0]: row[1] for row in cur.fetchall()}
                    st.success(f"✓ 已備份 {len(backup)} 個設定")
                except:
                    st.warning("⚠️ 無法備份設定")
                
                # === 步驟 2: 完全刪除資料庫檔案 ===
                st.info("2️⃣ 刪除資料庫檔案...")
                
                db_path = data_access.DB_PATH
                
                if db_path.exists():
                    os.remove(db_path)
                    st.success(f"✓ 已刪除: {db_path}")
                else:
                    st.info("ℹ️ 資料庫不存在")
                
                # === 步驟 3: 強制建立新 schema ===
                st.info("3️⃣ 建立新表格...")
                
                # 直接執行 SQL 建立表格
                with data_access.get_db_connection() as conn:
                    cur = conn.cursor()
                    
                    # Shop Master Table
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
                    
                    # Schedule Table
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
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            FOREIGN KEY (shop_id) REFERENCES shop_master(shop_id)
                        );
                    """)
                    
                    # Settings Table
                    cur.execute("""
                        CREATE TABLE settings (
                            key TEXT PRIMARY KEY,
                            value TEXT
                        );
                    """)
                    
                    # Holidays Table
                    cur.execute("""
                        CREATE TABLE holidays (
                            date TEXT PRIMARY KEY,
                            name_chi TEXT,
                            type TEXT
                        );
                    """)
                    
                    conn.commit()
                
                st.success("✓ 新表格已建立")
                
                # === 步驟 4: 驗證 schema ===
                st.info("4️⃣ 驗證 schema...")
                
                with data_access.get_db_connection() as conn:
                    cur = conn.cursor()
                    cur.execute("PRAGMA table_info(shop_master);")
                    columns = [col[1] for col in cur.fetchall()]
                
                st.write("**shop_master 欄位:**")
                st.code(", ".join(columns))
                
                required = ["region", "district", "address", "lat", "lng"]
                missing = [c for c in required if c not in columns]
                
                if missing:
                    st.error(f"❌ 缺少欄位: {', '.join(missing)}")
                    st.stop()
                else:
                    st.success("✅ Schema 驗證通過!")
                
                # === 步驟 5: 恢復設定 ===
                st.info("5️⃣ 恢復設定...")
                
                for key, value in backup.items():
                    data_access.set_setting(key, value)
                
                if backup:
                    st.success(f"✓ 已恢復 {len(backup)} 個設定")
                
                # === 步驟 6: 匯入資料 ===
                st.info("6️⃣ 匯入店舖資料...")
                
                sp_url = backup.get("SHAREPOINT_LIST_URL")
                sp_token = backup.get("SHAREPOINT_ACCESS_TOKEN")
                
                if sp_url and sp_token:
                    result = data_access.import_shops_from_sharepoint(
                        list_url=sp_url,
                        token=sp_token,
                        overwrite=False
                    )
                    st.success(f"✓ 成功: {result['success']}, 失敗: {result['failed']}, 跳過: {result['skipped']}")
                else:
                    st.warning("⚠️ 無 SharePoint 設定,請前往 Settings 手動匯入")
                
                # === 步驟 7: 初始化假期 ===
                st.info("7️⃣ 初始化假期...")
                holidays.init_default_holidays()
                st.success("✓ 假期已初始化")
                
                # === 步驟 8: 設定標誌 ===
                data_access.set_setting("app_initialized", "true")
                data_access.set_setting("app_version", "1.0.0")
                
                # === 完成 ===
                st.balloons()
                st.success("🎉 終極修復完成!")
                st.info("請點擊下方按鈕重新整理")
                
                if st.button("🔄 重新整理頁面"):
                    st.rerun()
                
            except Exception as e:
                st.error(f"❌ 修復失敗: {e}")
                import traceback
                st.code(traceback.format_exc())

    
    # 在 app.py 的強制重建按鈕中修改

    if st.button("⚡ 強制重建表格 (Fix Schema)", type="primary"):
        try:
            # ✅ 步驟 0: 先備份 SharePoint 設定
            st.info("💾 備份設定...")
            try:
                old_url = data_access.get_setting("SHAREPOINT_LIST_URL")
                old_token = data_access.get_setting("SHAREPOINT_ACCESS_TOKEN")
                old_shops_per_day = data_access.get_setting("shops_per_day", "20")
                old_groups_per_day = data_access.get_setting("groups_per_day", "3")
            except:
                old_url = None
                old_token = None
                old_shops_per_day = "20"
                old_groups_per_day = "3"
            
            st.write(f"- SharePoint URL: {'已備份' if old_url else '未設定'}")
            st.write(f"- Access Token: {'已備份' if old_token else '未設定'}")
            
            # 步驟 1: 刪除舊表格
            st.info("🗑️ 刪除舊表格...")
            with data_access.get_db_connection() as conn:
                cur = conn.cursor()
                cur.execute("DROP TABLE IF EXISTS shop_master;")
                cur.execute("DROP TABLE IF EXISTS schedule;")
                cur.execute("DROP TABLE IF EXISTS holidays;")
                cur.execute("DROP TABLE IF EXISTS settings;")  # ⚠️ 這會清空所有設定
                conn.commit()
            
            st.success("✅ 舊表格已刪除")
            
            # 步驟 2: 重新建立正確的 schema
            st.info("🔨 建立新表格...")
            data_access.init_db()
            
            # ✅ 步驟 3: 恢復 SharePoint 設定
            st.info("♻️ 恢復設定...")
            if old_url:
                data_access.set_setting("SHAREPOINT_LIST_URL", old_url)
                st.write("- SharePoint URL 已恢復")
            if old_token:
                data_access.set_setting("SHAREPOINT_ACCESS_TOKEN", old_token)
                st.write("- Access Token 已恢復")
            
            data_access.set_setting("shops_per_day", old_shops_per_day)
            data_access.set_setting("groups_per_day", old_groups_per_day)
            
            # 步驟 4: 從 SharePoint 匯入資料
            if old_url and old_token:
                st.info("📥 從 SharePoint 匯入資料...")
                result = data_access.import_shops_from_sharepoint(
                    list_url=old_url,
                    token=old_token,
                    overwrite=False
                )
                
                st.success(f"""
                ✅ 匯入完成!
                - 成功: {result['success']} 筆
                - 失敗: {result['failed']} 筆
                - 跳過: {result['skipped']} 筆
                """)
            else:
                st.warning("⚠️ SharePoint 設定未備份,請前往 Settings 頁面重新設定")
            
            # 步驟 5: 初始化假期
            st.info("📅 初始化假期...")
            holidays.init_default_holidays()
            
            # 步驟 6: 設定初始化標誌
            data_access.set_setting("app_initialized", "true")
            data_access.set_setting("app_version", "1.0.0")
            
            st.balloons()
            st.success("🎉 資料庫重建完成!")
            st.info("請重新整理頁面")
            
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
