# core/data_access.py
import os
import sqlite3
from pathlib import Path
from contextlib import contextmanager
import datetime
import pandas as pd


# 路徑設定
BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "data" / "db.sqlite"
CSV_PATH = BASE_DIR / "data" / "MxStockTakeMasterList.csv"


@contextmanager
def get_db_connection():
    """Context manager for database connections."""
    conn = None
    try:
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(DB_PATH, timeout=10.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL;")
        yield conn
        conn.commit()
    except Exception:
        if conn:
            conn.rollback()
        raise
    finally:
        if conn:
            conn.close()


def get_conn():
    """取得 SQLite 連線（保留向後相容，但建議用 get_db_connection）"""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=10.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    return conn


# ---------- 初始化 & 匯入 ----------

def init_db():
    """Initialize database and run all migrations."""
    with get_db_connection() as conn:
        cur = conn.cursor()

        # 店舖主檔
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS shop_master (
                shop_id TEXT PRIMARY KEY,
                shop_name TEXT,
                address_zh TEXT,
                address_en TEXT,
                region_code TEXT,
                area_en TEXT,
                district_en TEXT,
                is_mtr INTEGER,
                brand TEXT,
                business_unit TEXT,
                brand_icon_url TEXT,
                lat REAL,
                lng REAL,
                is_active INTEGER,
                phone TEXT,
                contact_name TEXT
            );
            """
        )

        # 排程表
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS schedule (
                schedule_id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT,
                shop_id TEXT,
                status TEXT,
                status_reason TEXT,
                assigned_by TEXT,
                day_route_order INTEGER,
                day_total_distance_km REAL,
                day_total_travel_time_min REAL,
                created_at TEXT,
                updated_at TEXT,
                FOREIGN KEY (shop_id) REFERENCES shop_master (shop_id)
            );
            """
        )



        # 假期表
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS holidays (
                date TEXT PRIMARY KEY,
                name_zh TEXT,
                type TEXT
            );
            """
        )

        # Settings 表
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT
            );
            """
        )
    
    # Migration runs after connection is closed
    add_group_column_if_missing()


def add_group_column_if_missing():
    """Add group_no column to schedule table if it doesn't exist."""
    with get_db_connection() as conn:
        cur = conn.cursor()
        try:
            cur.execute("ALTER TABLE schedule ADD COLUMN group_no INTEGER DEFAULT 1")
            print("✓ Added group_no column to schedule table")
        except sqlite3.OperationalError as e:
            if "duplicate column name" in str(e).lower():
                print("✓ group_no column already exists")
            else:
                raise


def import_shops_from_csv(overwrite: bool = True):
    """從 MxStockTakeMasterList.csv 匯入 shop_master"""
    if not CSV_PATH.exists():
        raise FileNotFoundError(f"CSV file not found: {CSV_PATH}")

    df = pd.read_csv(CSV_PATH)

    # 欄位映射 + 清洗
    df_new = pd.DataFrame({
        "shop_id": df["Shop Code"].astype(str),
        "shop_name": df["ShopName"],
        "address_zh": df["Address(Chi)"],
        "address_en": df["Address(Eng)"],
        "region_code": df["Region"],
        "area_en": df["Area"],
        "district_en": df["District"],
        "is_mtr": (df["MTR(Y/N)"] == "Y").astype(int),
        "brand": df["Brand"],
        "business_unit": df["Business Unit"],
        "brand_icon_url": df["Brandicon"],
        "lat": pd.to_numeric(df["Latitude"], errors="coerce"),
        "lng": pd.to_numeric(df["Longitude"], errors="coerce"),
        "is_active": (df["Available"] == "Y").astype(int),
        "phone": df.get("Telephone Number", ""),
        "contact_name": df.get("Contact name", ""),
    })

    df_new = df_new[df_new["shop_id"].notna() & (df_new["shop_id"] != "")]

    # ✓ 使用 context manager 確保正確關閉
    with get_db_connection() as conn:
        if overwrite:
            df_new.to_sql("shop_master", conn, if_exists="replace", index=False)
        else:
            df_new.to_sql("shop_master", conn, if_exists="append", index=False)
        print(f"✓ Successfully imported {len(df_new)} shops")


# ---------- 查詢工具 ----------

def count_active_shops() -> int:
    """計算仍在營業（is_active=1）的店舖數量"""
    with get_db_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM shop_master WHERE is_active = 1;")
        return cur.fetchone()[0]


def get_shop_by_id(shop_id: str) -> dict | None:
    """根據 shop_id 取得店舖資訊（dict），找不到回傳 None"""
    with get_db_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM shop_master WHERE shop_id = ?;", (shop_id,))
        row = cur.fetchone()
        return dict(row) if row else None


def get_all_shops(active_only: bool = True) -> list[dict]:
    """取得全部店舖；active_only=True 時只回傳 is_active=1 的"""
    with get_db_connection() as conn:
        cur = conn.cursor()
        if active_only:
            cur.execute("SELECT * FROM shop_master WHERE is_active = 1;")
        else:
            cur.execute("SELECT * FROM shop_master;")
        return [dict(r) for r in cur.fetchall()]


def get_month_summary(year: int, month: int) -> dict:
    """Return counts of schedule rows by status for a given year-month."""
    prefix = f"{year:04d}-{month:02d}-"
    with get_db_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT status, COUNT(*) AS cnt
            FROM schedule
            WHERE date LIKE ? || '%'
            GROUP BY status;
            """,
            (prefix,),
        )
        rows = cur.fetchall()

    base = {"Planned": 0, "Done": 0, "Closed": 0, "Rescheduled": 0}
    for status, cnt in rows:
        if status in base:
            base[status] = cnt
    base["Total"] = sum(base.values())
    return base


# ---------- Schedule 操作 ----------

def get_today_date() -> str:
    """取得今天日期字串（YYYY-MM-DD）"""
    return datetime.date.today().isoformat()


def get_schedule_for_date(date_str: str) -> list[dict]:
    """取得某天的排程列表"""
    with get_db_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT * FROM schedule
            WHERE date = ?
            ORDER BY day_route_order ASC, shop_id ASC;
            """,
            (date_str,),
        )
        return [dict(r) for r in cur.fetchall()]


def search_schedule(
    date: str | None = None,
    shop_id: str | None = None,
    region: str | None = None,
    district: str | None = None,
    status: list[str] | None = None,
) -> list[dict]:
    """Search schedule with optional filters."""
    with get_db_connection() as conn:
        cur = conn.cursor()

        base_sql = """
        SELECT 
            s.date,
            s.shop_id,
            s.status,
            s.status_reason,
            sm.shop_name,
            sm.address_zh,
            sm.region_code,
            sm.district_en,
            sm.brand_icon_url AS brand_icon_url,
            sm.lat,
            sm.lng
        FROM schedule s
        JOIN shop_master sm ON s.shop_id = sm.shop_id
        WHERE 1=1
        """
        params = []

        if date:
            base_sql += " AND s.date = ?"
            params.append(date)

        if shop_id:
            base_sql += " AND s.shop_id = ?"
            params.append(shop_id)

        if region and region != "All":
            base_sql += " AND sm.region_code = ?"
            params.append(region)

        if district:
            base_sql += " AND sm.district_en LIKE ?"
            params.append(f"%{district}%")

        if status and len(status) > 0:
            placeholders = ",".join("?" for _ in status)
            base_sql += f" AND (s.status IN ({placeholders}) OR s.status IS NULL)"
            params.extend(status)

        base_sql += " ORDER BY s.date, sm.region_code, sm.district_en, s.shop_id"

        cur.execute(base_sql, params)
        return [dict(r) for r in cur.fetchall()]

def search_shops(
    date: str | None = None,
    shop_id: str | None = None,
    regions: list[str] | None = None,
    districts: list[str] | None = None,  # ✅ CHANGED: accepts list
    status: list[str] | None = None,
    brand: str | None = None,
) -> list[dict]:
    """Search shops from shop_master with optional filters."""
    with get_db_connection() as conn:
        cur = conn.cursor()
        
        base_sql = """
            SELECT
                s.date,
                sm.shop_id,
                s.status,
                sm.shop_name,
                sm.region_code,
                sm.district_en,
                sm.address_zh,
                sm.lat,
                sm.lng,
                sm.brand,
                sm.brand_icon_url
            FROM shop_master sm
            LEFT JOIN schedule s ON sm.shop_id = s.shop_id
            WHERE sm.is_active = 1
        """
        
        params: list = []
        
        if date:
            base_sql += " AND (s.date = ? OR s.date IS NULL)"
            params.append(date)
        
        if shop_id:
            base_sql += " AND sm.shop_id = ?"
            params.append(shop_id)
        
        # Handle multiple regions
        if regions and len(regions) > 0:
            placeholders = ",".join("?" for _ in regions)
            base_sql += f" AND sm.region_code IN ({placeholders})"
            params.extend(regions)
        
        # ✅ CHANGED: Handle multiple districts (list)
        if districts and len(districts) > 0:
            placeholders = ",".join("?" for _ in districts)
            base_sql += f" AND sm.district_en IN ({placeholders})"
            params.extend(districts)
        
        if status and len(status) > 0:
            placeholders = ",".join("?" for _ in status)
            base_sql += f" AND (s.status IN ({placeholders}) OR s.status IS NULL)"
            params.extend(status)
        
        if brand:
            base_sql += " AND sm.brand LIKE ?"
            params.append(f"%{brand}%")
        
        base_sql += " ORDER BY sm.region_code, sm.district_en, sm.shop_id"
        
        cur.execute(base_sql, params)
        return [dict(r) for r in cur.fetchall()]





def update_schedule_status(schedule_date: str, shop_id: str, status: str, status_reason: str | None):
    """Update schedule status"""
    with get_db_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            UPDATE schedule
            SET status = ?, status_reason = ?, updated_at = datetime('now')
            WHERE date = ? AND shop_id = ?;
            """,
            (status, status_reason, schedule_date, shop_id),
        )


def mark_shop_permanently_closed(shop_id: str, schedule_id: int | None = None):
    """標記店舖為永久 Closed"""
    now = datetime.datetime.now().isoformat(timespec="seconds")
    with get_db_connection() as conn:
        cur = conn.cursor()
        cur.execute("UPDATE shop_master SET is_active = 0 WHERE shop_id = ?;", (shop_id,))
        
        if schedule_id is not None:
            cur.execute(
                "UPDATE schedule SET status = 'Closed', updated_at = ? WHERE schedule_id = ?;",
                (now, schedule_id),
            )


def move_schedule_to_new_date(old_date: str, new_date: str, shop_id: str):
    """Move one shop from old_date to new_date"""
    with get_db_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            UPDATE schedule
            SET date = ?, status = 'Planned', status_reason = NULL, updated_at = datetime('now')
            WHERE date = ? AND shop_id = ?;
            """,
            (new_date, old_date, shop_id),
        )


def auto_reschedule(schedule_id: int) -> str | None:
    """自動重排的骨架函式"""
    today = datetime.date.today()
    suggested = today + datetime.timedelta(days=7)
    return suggested.isoformat()


def count_shops_on_date(schedule_date: str) -> int:
    """Return how many shops are scheduled on a given date"""
    with get_db_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM schedule WHERE date = ?;", (schedule_date,))
        row = cur.fetchone()
        return row[0] if row else 0


# ---------- Settings ----------

def get_amap_key() -> str | None:
    """Get AMap API key"""
    with get_db_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT value FROM settings WHERE key = 'AMAP_WEB_KEY';")
        row = cur.fetchone()
        return row[0] if row else None


def set_amap_key(key: str):
    """Set AMap API key"""
    with get_db_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO settings (key, value)
            VALUES ('AMAP_WEB_KEY', ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value;
            """,
            (key,),
        )


def set_setting(key: str, value: str):
    """Set a setting value"""
    with get_db_connection() as conn:
        cur = conn.cursor()
        cur.execute("REPLACE INTO settings (key, value) VALUES (?, ?);", (key, value))


def get_setting(key: str, default: str | None = None) -> str | None:
    """Get a setting value"""
    with get_db_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT value FROM settings WHERE key = ?;", (key,))
        row = cur.fetchone()
        return row[0] if row else default
        
def import_shops_from_json(json_data: list, overwrite: bool = True):
    """Import shops from SharePoint List JSON data."""
    import pandas as pd
    
    # Map SharePoint List columns to our DB columns
    # Adjust 'SP_Col_Name' to match your actual SharePoint List column internal names
    df = pd.DataFrame(json_data)
    
    # Example Mapping (Verify your actual list column names!)
    # SharePoint usually returns 'Title' for the first column
    column_mapping = {
        "Title": "shop_id",            # Assuming Shop Code is the Title
        "ShopName": "shop_name",
        "AddressChi": "address_zh",
        "AddressEng": "address_en",
        "Region": "region_code",
        "Area": "area_en",
        "District": "district_en",
        "MTR_x0028_Y_x002f_N_x0029_": "is_mtr", # Special characters like (Y/N) get encoded
        "Brand": "brand",
        "BusinessUnit": "business_unit",
        "Brandicon": "brand_icon_url",
        "Latitude": "lat",
        "Longitude": "lng",
        "Available": "is_active",
        "TelephoneNumber": "phone",
        "Contactname": "contact_name"
    }
    
    # Rename columns available in the JSON
    # We use a loop to be safe against missing columns
    rename_dict = {}
    for sp_col, db_col in column_mapping.items():
        if sp_col in df.columns:
            rename_dict[sp_col] = db_col
            
    df_new = df.rename(columns=rename_dict)
    
    # Data Cleaning
    if "shop_id" in df_new.columns:
        df_new = df_new[df_new["shop_id"].notna()]
        df_new["shop_id"] = df_new["shop_id"].astype(str)
        
    # Convert Yes/No or Y/N to integers if needed
    if "is_mtr" in df_new.columns:
        # SharePoint boolean is usually True/False or "Y"/"N" string
        df_new["is_mtr"] = df_new["is_mtr"].apply(lambda x: 1 if x == True or x == "Y" else 0)
        
    if "is_active" in df_new.columns:
        df_new["is_active"] = df_new["is_active"].apply(lambda x: 1 if x == True or x == "Y" else 0)

    # ... (rest of the logic is same as CSV import: creating df_final and saving to SQL) ...
    # Ensure all required DB columns exist, fill with None/0 if missing
    required_cols = ["shop_id", "shop_name", "address_zh", "region_code", "district_en", "lat", "lng", "brand"]
    for col in required_cols:
        if col not in df_new.columns:
            df_new[col] = None

    # Save to DB
    with get_db_connection() as conn:
        if overwrite:
            df_new.to_sql("shop_master", conn, if_exists="replace", index=False)
        else:
            df_new.to_sql("shop_master", conn, if_exists="append", index=False)
            
    print(f"✓ Successfully imported {len(df_new)} shops from SharePoint List")

