# fix_schema.py
import sys
from pathlib import Path

# 加入專案路徑
sys.path.insert(0, str(Path(__file__).resolve().parent))

from core import data_access, holidays

def main():
    print("🔧 開始修復資料庫 schema...")
    
    try:
        # 1. 刪除舊表格
        print("\n1️⃣ 刪除舊表格...")
        with data_access.get_db_connection() as conn:
            cur = conn.cursor()
            cur.execute("DROP TABLE IF EXISTS shop_master;")
            cur.execute("DROP TABLE IF EXISTS schedule;")
            cur.execute("DROP TABLE IF EXISTS holidays;")
            cur.execute("DROP TABLE IF EXISTS settings;")
            conn.commit()
        print("✅ 舊表格已刪除")
        
        # 2. 重新建立正確的 schema
        print("\n2️⃣ 建立新表格...")
        data_access.init_db()
        print("✅ 新表格已建立")
        
        # 3. 驗證 schema
        print("\n3️⃣ 驗證 schema...")
        with data_access.get_db_connection() as conn:
            cur = conn.cursor()
            cur.execute("PRAGMA table_info(shop_master);")
            columns = [col[1] for col in cur.fetchall()]
            print(f"📋 Columns: {columns}")
            
            required = ["region", "district", "address", "lat", "lng"]
            missing = [c for c in required if c not in columns]
            
            if missing:
                print(f"❌ 缺少欄位: {missing}")
                return False
            else:
                print("✅ Schema 正確!")
        
        # 4. 從 SharePoint 匯入資料
        print("\n4️⃣ 從 SharePoint 匯入資料...")
        result = data_access.import_shops_from_sharepoint(overwrite=False)
        print(f"""
        ✅ 匯入完成:
           - 成功: {result['success']}
           - 失敗: {result['failed']}
           - 跳過: {result['skipped']}
        """)
        
        # 5. 初始化假期
        print("\n5️⃣ 初始化假期...")
        holidays.init_default_holidays()
        print("✅ 假期已初始化")
        
        # 6. 設定初始化標誌
        print("\n6️⃣ 設定初始化標誌...")
        data_access.set_setting("app_initialized", "true")
        data_access.set_setting("app_version", "1.0.0")
        
        print("\n" + "="*50)
        print("🎉 資料庫修復完成!")
        print("="*50)
        
        return True
        
    except Exception as e:
        print(f"\n❌ 修復失敗: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
