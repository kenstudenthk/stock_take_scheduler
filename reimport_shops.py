from core import data_access

with data_access.get_db_connection() as conn:
    cur = conn.cursor()
    cur.execute("SELECT shop_id, brand, brand_icon_url FROM shop_master LIMIT 5;")
    print(cur.fetchall())
