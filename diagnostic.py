# diagnostic.py
from core.data_access import get_db_connection

def check_schema():
    """檢查實際資料庫結構"""
    with get_db_connection() as conn:
        cur = conn.cursor()
        
        # 檢查 shop_master 欄位
        cur.execute("PRAGMA table_info(shop_master);")
        columns = cur.fetchall()
        
        print("📋 shop_master 實際欄位:")
        for col in columns:
            print(f"  - {col[1]} ({col[2]})")
        
        # 檢查資料筆數
        cur.execute("SELECT COUNT(*) FROM shop_master;")
        count = cur.fetchone()[0]
        print(f"\n📊 Total shops: {count}")
        
        # 檢查範例資料
        cur.execute("SELECT * FROM shop_master LIMIT 1;")
        sample = cur.fetchone()
        if sample:
            print(f"\n📄 Sample record:")
            for idx, col in enumerate(columns):
                print(f"  {col[1]}: {sample[idx]}")

if __name__ == "__main__":
    check_schema()
