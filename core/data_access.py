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
    """計算店舖數量，自動適應 is_active 或 Available 欄位"""
    with get_db_connection() as conn:
        cur = conn.cursor()
        try:
            # 1. 先試標準欄位 is_active
            cur.execute("SELECT COUNT(*) FROM shop_master WHERE is_active = 1;")
        except Exception:
            # 2. 如果報錯 (no such column)，試試看 Available
            try:
                # 注意：Available 在 CSV 裡可能是 'Y'/'N' 文字
                cur.execute("SELECT COUNT(*) FROM shop_master WHERE Available = 'Y';")
            except Exception:
                # 3. 真的都沒有，就傳回所有店舖數 (當作全部都 active)
                cur.execute("SELECT COUNT(*) FROM shop_master;")
        
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

# ---------------------------------------------------------
# 請將這段程式碼貼到 data_access.py 替換原本的 import_shops_from_json
# ---------------------------------------------------------

def import_shops_from_json(json_data: list, overwrite: bool = True):
    """Import shops from SharePoint List JSON data (Handles Dict/Choice fields)."""
    import pandas as pd
    
    if not json_data:
        print("⚠️ No data received from SharePoint List")
        return

    # 1. 轉成原始 DataFrame
    df_raw = pd.DataFrame(json_data)
    
    # 2. 定義我們要抓取的欄位邏輯
    fetch_rules = {
        "shop_id":      ["field_6", "ShopCode", "Title"],
        "shop_name":    ["field_7", "ShopName"],
        "address_zh":   ["field_8", "AddressChi"],
        "address_en":   ["field_14", "AddressEng"],
        "region_code":  ["field_9", "Region"],       # Choice 欄位
        "area_en":      ["field_10", "Area"],         # Choice 欄位
        "district_en":  ["field_16", "District"],     # Choice 欄位
        "brand":        ["field_11", "Brand"],        # Choice 欄位
        "business_unit":["BusinessUnit", "business_unit"],
        "brand_icon_url": ["field_23", "Brandicon"],
        "lat":          ["field_20", "Latitude"],
        "lng":          ["field_21", "Longitude"],
        "is_active":    ["field_35", "Available"],    # Choice 欄位
        "is_mtr":       ["field_17", "MTR"],          # Choice 欄位
        "phone":        ["field_37", "TelephoneNumber"],
        "contact_name": ["field_38", "Contactname"]
    }

    # 3. 逐行處理 (包含字典解包)
    clean_rows = []
    raw_records = df_raw.to_dict(orient='records')

    for raw_row in raw_records:
        clean_row = {}
        
        for db_col, candidates in fetch_rules.items():
            value = None
            for candidate in candidates:
                if candidate in raw_row and pd.notna(raw_row[candidate]):
                    raw_val = raw_row[candidate]
                    
                    # --- 🛠️ 關鍵修正：處理 Choice/Lookup 字典 ---
                    if isinstance(raw_val, dict):
                        # 嘗試取 'Value' (SharePoint Choice 標準格式)
                        # 有些 lookup 可能是 'Title' 或 'Id'，這裡優先取 Value
                        value = raw_val.get('Value') 
                        if value is None:
                             value = raw_val.get('Title') # 有時候是 Title
                        if value is None:
                             # 如果真的取不到，轉成字串避免報錯
                             value = str(raw_val)
                    # ----------------------------------------
                    elif isinstance(raw_val, list):
                        # 複選 Choice 會是 List，轉字串 (e.g. "['Option A', 'Option B']")
                        value = ", ".join([str(v.get('Value', v)) if isinstance(v, dict) else str(v) for v in raw_val])
                    else:
                        value = raw_val
                    
                    break # 找到值就停
            
            clean_row[db_col] = value
            
        clean_rows.append(clean_row)

    # 4. 轉成 DataFrame
    df_final = pd.DataFrame(clean_rows)
    
    # 5. 資料清洗
    if "shop_id" in df_final.columns:
        df_final = df_final[df_final["shop_id"].notna()]
        df_final["shop_id"] = df_final["shop_id"].astype(str)
        df_final = df_final[df_final["shop_id"].str.strip() != ""]

    # 數值轉換
    for col in ["lat", "lng"]:
        df_final[col] = pd.to_numeric(df_final[col], errors='coerce')

    # 布林轉換 (現在 is_active 如果是 'Y' 字串就能正確處理了)
    for col in ["is_mtr", "is_active"]:
        df_final[col] = df_final[col].apply(
            lambda x: 1 if str(x).upper() in ['Y', 'YES', 'TRUE', '1'] else 0
        )

    # 去重
    df_final = df_final.drop_duplicates(subset=['shop_id'])

    # 6. 寫入 DB
    with get_db_connection() as conn:
        if overwrite:
            df_final.to_sql("shop_master", conn, if_exists="replace", index=False)
            print("✓ shop_master table replaced successfully.")
        else:
            required_db_cols = list(fetch_rules.keys())
            for _, row in df_final.iterrows():
                try:
                    cols = ",".join(required_db_cols)
                    placeholders = ",".join(["?"] * len(required_db_cols))
                    sql = f"INSERT OR REPLACE INTO shop_master ({cols}) VALUES ({placeholders})"
                    conn.execute(sql, tuple(row[col] for col in required_db_cols))
                except Exception as e:
                    print(f"Error inserting row {row.get('shop_id')}: {e}")

    print(f"✓ Successfully imported {len(df_final)} shops from SharePoint List (JSON)")

# =============================================================================
# SharePoint 同步功能
# =============================================================================

def export_schedule_to_sharepoint(year: int = None, month: int = None):
    print("[DEBUG] export_schedule_to_sharepoint called with", year, month)
    """將排程資料寫回 SharePoint List"""
    try:
        import requests  # ✅ 確保有安裝 requests
        import json
        
        # ✅ 修正：直接呼叫 get_setting()，不用 data_access 前綴
        sharepoint_url = get_setting("SHAREPOINT_LIST_URL")
        access_token = get_setting("SHAREPOINT_ACCESS_TOKEN")
        
        if not sharepoint_url or not access_token:
            print("⚠️ SharePoint 設定未配置，跳過寫回")
            return False
        
        # ✅ 修正：使用現有的 search_schedule() 函式
        if year and month:
            date_str = f"{year:04d}-{month:02d}-01"  # 該月第一天
            schedules = search_schedule(date=date_str)  # 只能搜尋特定日期
        else:
            # ✅ 修正：改用 SQL 查詢取得所有排程
            with get_db_connection() as conn:
                cur = conn.cursor()
                cur.execute("SELECT * FROM schedule ORDER BY date, shop_id;")
                schedules = [dict(r) for r in cur.fetchall()]
        
        if not schedules:
            print("ℹ️ 沒有排程資料需要寫回")
            return True
        
        print(f"📤 準備寫回 {len(schedules)} 筆排程到 SharePoint...")
        
        # 逐筆更新 SharePoint List
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json;odata=verbose",
            "Accept": "application/json;odata=verbose"
        }
        
        success_count = 0
        for sched in schedules:
            shop_id = sched["shop_id"]
            sched_date = sched["date"]
            status = sched.get("status", "Planned")
            
            # 建構 SharePoint 更新 payload
            payload = {
                "__metadata": {"type": "SP.Data.MxStockTakeMasterListListItem"},  # ✅ 改成您的 List 名稱
                "field_39": sched_date,  # ✅ 對應您的 ScheduledDate 欄位
                "field_40": status,       # ✅ 對應您的 Status 欄位
                "field_6": shop_id        # ✅ 對應您的 ShopCode 欄位
            }
            
            # ✅ 更新 SharePoint item（需要取得 item ID）
            item_id = _get_sharepoint_item_id(shop_id, sharepoint_url, access_token)
            
            if item_id:
                url = f"{sharepoint_url}/items({item_id})"
                response = requests.patch(  # ✅ 使用 PATCH 而非 POST
                    url,
                    headers=headers,
                    json=payload
                )
                
                if response.status_code in [200, 201, 204]:
                    success_count += 1
                else:
                    print(f"❌ 寫回失敗 {shop_id}: {response.status_code} - {response.text}")
            else:
                print(f"⚠️ 找不到 SharePoint item ID for shop {shop_id}")
        
        print(f"✅ 成功寫回 {success_count}/{len(schedules)} 筆排程")
        return success_count > 0
        
    except ImportError:
        print("❌ 請先安裝 requests 模組：pip install requests")
        return False
    except Exception as e:
        print(f"❌ SharePoint 寫回失敗: {e}")
        import traceback
        traceback.print_exc()
        return False


def _get_sharepoint_item_id(shop_id: str, list_url: str, token: str) -> int | None:
    """
    根據 shop_id 查詢對應的 SharePoint List Item ID
    
    Args:
        shop_id: 店舖代碼（例如 "S001"）
        list_url: SharePoint List API URL
        token: Access Token
        
    Returns:
        SharePoint Item ID 或 None（找不到時）
    """
    try:
        import requests
        
        # ✅ 使用 OData 查詢語法搜尋
        query_url = f"{list_url}/items?$filter=field_6 eq '{shop_id}'&$select=id"
        
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/json;odata=verbose"
        }
        
        response = requests.get(query_url, headers=headers)
        
        if response.status_code == 200:
            data = response.json()
            items = data.get("d", {}).get("results", [])
            
            if items and len(items) > 0:
                return items[0].get("Id") or items[0].get("id")
        
        return None
        
    except Exception as e:
        print(f"❌ 查詢 SharePoint Item ID 失敗: {e}")
        return None


def sync_schedule_back_to_sharepoint(start_date: str | None = None) -> bool:
    """
    將排程結果寫回 SharePoint（簡化版介面）
    """
    try:
        print(f"[DEBUG] sync_schedule_back_to_sharepoint called, start_date={start_date!r}")
        if start_date:
            year = int(start_date[:4])
            month = int(start_date[5:7])
            print(f"[DEBUG] -> calling export_schedule_to_sharepoint({year}, {month})")
            return export_schedule_to_sharepoint(year, month)
        else:
            print("[DEBUG] -> calling export_schedule_to_sharepoint() for ALL")
            return export_schedule_to_sharepoint()
    except Exception as e:
        print(f"❌ 同步失敗: {e}")
        return False




