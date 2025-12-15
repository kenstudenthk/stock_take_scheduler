# check_db_path.py
from core.data_access import DB_PATH, get_db_connection
import os

print(f"📂 Expected DB path: {DB_PATH}")
print(f"📂 Absolute path: {DB_PATH.resolve()}")
print(f"✅ File exists: {DB_PATH.exists()}")

if DB_PATH.exists():
    print(f"📊 File size: {os.path.getsize(DB_PATH)} bytes")
    
    # 檢查表格結構
    with get_db_connection() as conn:
        cur = conn.cursor()
        cur.execute("PRAGMA table_info(shop_master);")
        columns = [col[1] for col in cur.fetchall()]
        print(f"📋 Columns: {columns}")
        
        cur.execute("SELECT COUNT(*) FROM shop_master;")
        count = cur.fetchone()[0]
        print(f"📊 Total shops: {count}")
