# rebuild_database.py
"""
獨立的資料庫重建腳本
直接在命令列執行: python rebuild_database.py
"""

import os
import sys
from pathlib import Path

# 加入專案路徑
BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

from core import data_access, holidays

def main():
    print("=" * 60)
    print("🔧 資料庫重建工具")
    print("=" * 60)
    
    # === 步驟 1: 備份 SharePoint 設定 ===
    print("\n📋 步驟 1: 備份設定...")
    backup = {}
    
    try:
        if data_access.DB_PATH.exists():
            with data_access.get_db_connection() as conn:
                cur = conn.cursor()
                cur.execute("SELECT key, value FROM settings;")
                backup = {row[0]: row[1] for row in cur.fetchall()}
            print(f"   ✓ 已備份 {len(backup)} 個設定")
            
            # 顯示 SharePoint 設定
            sp_url = backup.get("SHAREPOINT_LIST_URL")
            sp_token = backup.get("SHAREPOINT_ACCESS_TOKEN")
            
            if sp_url:
                print(f"   ✓ SharePoint URL: {sp_url[:50]}...")
            if sp_token:
                print(f"   ✓ Access Token: {'*' * 20}...{sp_token[-10:]}")
        else:
            print("   ℹ️ 資料庫不存在,跳過備份")
    except Exception as e:
        print(f"   ⚠️ 備份失敗 (可能是首次執行): {e}")
    
    # === 步驟 2: 刪除舊資料庫 ===
    print("\n🗑️ 步驟 2: 刪除舊資料庫...")
    
    if data_access.DB_PATH.exists():
        try:
            os.remove(data_access.DB_PATH)
            print(f"   ✓ 已刪除: {data_access.DB_PATH}")
        except Exception as e:
            print(f"   ❌ 刪除失敗: {e}")
            return False
    else:
        print("   ℹ️ 資料庫不存在")
    
    # === 步驟 3: 建立新 schema ===
    print("\n🔨 步驟 3: 建立新表格...")
    
    try:
        data_access.init_db()
        print("   ✓ 表格已建立")
    except Exception as e:
        print(f"   ❌ 建立失敗: {e}")
        return False
    
    # === 步驟 4: 驗證 schema ===
    print("\n🔍 步驟 4: 驗證 schema...")
    
    try:
        with data_access.get_db_connection() as conn:
            cur = conn.cursor()
            cur.execute("PRAGMA table_info(shop_master);")
            columns = [col[1] for col in cur.fetchall()]
        
        print(f"   📋 欄位: {', '.join(columns)}")
        
        required = ["region", "district", "address", "lat", "lng"]
        missing = [c for c in required if c not in columns]
        
        if missing:
            print(f"   ❌ 缺少必要欄位: {', '.join(missing)}")
            return False
        else:
            print("   ✓ Schema 驗證通過")
    except Exception as e:
        print(f"   ❌ 驗證失敗: {e}")
        return False
    
    # === 步驟 5: 恢復設定 ===
    print("\n♻️ 步驟 5: 恢復設定...")
    
    for key, value in backup.items():
        try:
            data_access.set_setting(key, value)
        except Exception as e:
            print(f"   ⚠️ 無法恢復設定 {key}: {e}")
    
    if backup:
        print(f"   ✓ 已恢復 {len(backup)} 個設定")
    
    # === 步驟 6: 匯入店舖資料 ===
    print("\n📥 步驟 6: 匯入店舖資料...")
    
    sp_url = backup.get("SHAREPOINT_LIST_URL")
    sp_token = backup.get("SHAREPOINT_ACCESS_TOKEN")
    
    if sp_url and sp_token:
        try:
            print("   → 從 SharePoint 匯入...")
            result = data_access.import_shops_from_sharepoint(
                list_url=sp_url,
                token=sp_token,
                overwrite=False
            )
            print(f"   ✓ 成功: {result['success']} 筆")
            print(f"   ✓ 失敗: {result['failed']} 筆")
            print(f"   ✓ 跳過: {result['skipped']} 筆")
        except Exception as e:
            print(f"   ❌ SharePoint 匯入失敗: {e}")
            
            # 嘗試 CSV 備用方案
            print("   → 嘗試從 CSV 匯入...")
            try:
                data_access.import_shops_from_csv(overwrite=False)
                print("   ✓ CSV 匯入成功")
            except FileNotFoundError:
                print("   ⚠️ CSV 檔案不存在")
                print("   ⚠️ 請手動設定 SharePoint 或上傳 CSV")
    else:
        print("   ⚠️ 無 SharePoint 設定")
        print("   ⚠️ 請前往 Settings 頁面設定")
    
    # === 步驟 7: 初始化假期 ===
    print("\n📅 步驟 7: 初始化假期...")
    
    try:
        holidays.init_default_holidays()
        print("   ✓ 假期已初始化")
    except Exception as e:
        print(f"   ❌ 假期初始化失敗: {e}")
    
    # === 步驟 8: 設定標誌 ===
    print("\n⚙️ 步驟 8: 設定初始化標誌...")
    
    try:
        data_access.set_setting("app_initialized", "true")
        data_access.set_setting("app_version", "1.0.0")
        print("   ✓ 標誌已設定")
    except Exception as e:
        print(f"   ❌ 設定失敗: {e}")
    
    # === 步驟 9: 最終驗證 ===
    print("\n✅ 步驟 9: 最終驗證...")
    
    try:
        with data_access.get_db_connection() as conn:
            cur = conn.cursor()
            
            # 檢查店舖數量
            cur.execute("SELECT COUNT(*) FROM shop_master;")
            shop_count = cur.fetchone()[0]
            
            # 檢查假期數量
            cur.execute("SELECT COUNT(*) FROM holidays;")
            holiday_count = cur.fetchone()[0]
            
            # 顯示範例店舖
            cur.execute("""
                SELECT shop_id, shop_name, region, district 
                FROM shop_master 
                LIMIT 3;
            """)
            samples = cur.fetchall()
        
        print(f"   📊 店舖數量: {shop_count}")
        print(f"   📅 假期數量: {holiday_count}")
        
        if samples:
            print("\n   📋 範例店舖:")
            for s in samples:
                print(f"      - {s[0]}: {s[1]} ({s[2]}, {s[3]})")
        
        if shop_count > 0 and holiday_count > 0:
            print("\n" + "=" * 60)
            print("🎉 重建完成!")
            print("=" * 60)
            print("\n請重新啟動 Streamlit 應用程式:")
            print("  streamlit run app.py")
            return True
        else:
            print("\n" + "=" * 60)
            print("⚠️ 重建完成但資料不完整")
            print("=" * 60)
            print("\n請檢查:")
            if shop_count == 0:
                print("  - SharePoint 設定是否正確")
                print("  - 或上傳 CSV 檔案到 data/MxStockTakeMasterList.csv")
            if holiday_count == 0:
                print("  - holidays.py 是否正確")
            return False
            
    except Exception as e:
        print(f"   ❌ 驗證失敗: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
