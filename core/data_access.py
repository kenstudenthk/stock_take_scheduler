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

def export_schedule_to_sharepoint(year: int = None, month: int = None) -> bool:
    """
    將排程資料透過 Power Automate Flow 寫回 SharePoint List
    （不再直接呼叫 SharePoint REST + Token）
    """
    import requests
    import json

    # 從 settings 讀 Flow URL
    flow_url = get_setting("PA_SCHEDULE_WRITE_URL")
    if not flow_url:
        print("⚠️ PA_SCHEDULE_WRITE_URL 未設定，跳過寫回")
        return False

    # 取得要寫回的 schedule 資料
    with get_db_connection() as conn:
        cur = conn.cursor()
        if year and month:
            # 該月第一天，簡單版本：只抓同一個月的資料可再擴充
            month_prefix = f"{year:04d}-{month:02d}-"
            cur.execute(
                """
                SELECT shop_id, date, COALESCE(status, 'Planned') AS status
                FROM schedule
                WHERE date LIKE ? || '%'
                ORDER BY date, shop_id;
                """,
                (month_prefix,),
            )
        else:
            cur.execute(
                """
                SELECT shop_id, date, COALESCE(status, 'Planned') AS status
                FROM schedule
                ORDER BY date, shop_id;
                """
            )
        rows = cur.fetchall()

    if not rows:
        print("ℹ️ 沒有排程資料需要寫回")
        return True

    items = [
        {
            "shop_id": r[0],
            "date": r[1],
            "status": r[2],
        }
        for r in rows
    ]

    payload = {"items": items}

    try:
        print(f"📤 準備透過 Power Automate 寫回 {len(items)} 筆排程...")
        resp = requests.post(
            flow_url,
            headers={"Content-Type": "application/json"},
            data=json.dumps(payload),
            timeout=30,
        )
        resp.raise_for_status()
        print("✅ Flow 回應:", resp.status_code, resp.text)
        # 可選：檢查 resp.json().get("ok", True)
        return True
    except Exception as e:
        print(f"❌ 呼叫 Power Automate Flow 失敗: {e}")
        import traceback
        traceback.print_exc()
        return False



def _get_sharepoint_item_id(shop_id: str, list_url: str, token: str) -> str | None:
    """
    根據 Shop Code (field_6) 查詢對應的 SharePoint Item ID
    
    前提：field_6 已在 SharePoint List 中設為索引欄位
    
    Args:
        shop_id: 店舖代碼（任何格式，例如 "3326" 或 "03326"）
        list_url: Microsoft Graph List URL
        token: Microsoft Graph Access Token
        
    Returns:
        SharePoint Item ID (字串) 或 None
    """
    try:
        import requests
        
        # ✅ 將 shop_id 補齊為 5 位數（統一格式）
        shop_code_padded = str(shop_id).zfill(5)
        
        print(f"🔍 Querying SharePoint for field_6 = '{shop_code_padded}'")
        
        # ✅ 使用 field_6 查詢（已索引，速度快）
        query_url = f"{list_url}/items?$filter=fields/field_6 eq '{shop_code_padded}'&$select=id&$expand=fields($select=field_6,Title,ScheduleStatus)"
        
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/json"
            # ✅ 不需要 Prefer header（因為 field_6 已索引）
        }
        
        response = requests.get(query_url, headers=headers, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            items = data.get("value", [])
            
            if items and len(items) > 0:
                item_id = items[0].get("id")
                fields = items[0].get("fields", {})
                
                print(f"✅ Found Item:")
                print(f"   - Item ID: {item_id}")
                print(f"   - field_6: {fields.get('field_6')}")
                print(f"   - Title: {fields.get('Title')}")
                print(f"   - Current Status: {fields.get('ScheduleStatus')}")
                
                return item_id
            else:
                print(f"⚠️ No item found with field_6 = '{shop_code_padded}'")
                return None
        else:
            print(f"❌ Query failed: {response.status_code}")
            print(f"Response: {response.text}")
            return None
        
    except Exception as e:
        print(f"❌ 查詢失敗: {e}")
        import traceback
        traceback.print_exc()
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

import requests  # 如果檔案上面還沒 import，就補這行

def update_sharepoint_item_status(
    item_id: str,
    new_status: str,
    list_url: str | None = None,
    token: str | None = None,
    status_field_internal_name: str = "ScheduleStatus",
) -> bool:
    """
    更新 SharePoint List 項目狀態
    """
    import requests
    
    if list_url is None:
        list_url = get_setting("SHAREPOINT_LIST_URL")
    if token is None:
        token = get_setting("SHAREPOINT_ACCESS_TOKEN")

    if not list_url or not token:
        print("⚠️ SharePoint settings not configured")
        return False

    url = f"{list_url}/items/{item_id}/fields"

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "application/json"
    }

    body = {
        status_field_internal_name: new_status
    }

    try:
        print(f"📤 Updating Item {item_id}: {status_field_internal_name}='{new_status}'")
        
        response = requests.patch(url, headers=headers, json=body, timeout=15)
        
        if response.status_code in (200, 204):
            print(f"✅ SharePoint updated successfully")
            return True
        else:
            print(f"❌ Update failed: {response.status_code}")
            print(f"Response: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Update error: {e}")
        import traceback
        traceback.print_exc()
        return False
    
def import_shops_from_sharepoint(
    list_url: str | None = None,
    token: str | None = None,
    overwrite: bool = False
) -> dict:
    """
    從 SharePoint List 匯入店舖資料到本地資料庫
    
    Args:
        list_url: Microsoft Graph List URL
        token: Access Token
        overwrite: 是否覆蓋現有資料
        
    Returns:
        {"success": int, "failed": int, "skipped": int}
    """
    import requests
    
    # 從 settings 讀取（如果未提供）
    if list_url is None:
        list_url = get_setting("SHAREPOINT_LIST_URL")
    if token is None:
        token = get_setting("SHAREPOINT_ACCESS_TOKEN")
    
    if not list_url or not token:
        raise ValueError("SharePoint URL 或 Token 未設定")
    
    print("📥 開始從 SharePoint 匯入店舖資料...")
    
    # Step 1: 取得所有 SharePoint List 項目
    query_url = f"{list_url}/items?$select=id&$expand=fields&$top=5000"
    
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json"
    }
    
    try:
        response = requests.get(query_url, headers=headers, timeout=30)
        
        if response.status_code != 200:
            raise Exception(f"SharePoint API 錯誤: {response.status_code} - {response.text}")
        
        data = response.json()
        items = data.get("value", [])
        
        print(f"📊 從 SharePoint 取得 {len(items)} 筆資料")
        
        if not items:
            return {"success": 0, "failed": 0, "skipped": 0}
        
        # Step 2: 解析資料並寫入資料庫
        success_count = 0
        failed_count = 0
        skipped_count = 0
        
        with get_db_connection() as conn:
            cur = conn.cursor()
            
            for item in items:
                try:
                    fields = item.get("fields", {})
                    
                    # 必要欄位檢查
                    shop_id = fields.get("field_6")  # Shop Code
                    if not shop_id:
                        print(f"⚠️ 跳過：缺少 Shop Code (field_6)")
                        skipped_count += 1
                        continue
                    
                    # 如果不覆蓋，檢查是否已存在
                    if not overwrite:
                        cur.execute("SELECT 1 FROM shop_master WHERE shop_id = ?", (shop_id,))
                        if cur.fetchone():
                            print(f"⏭️ 跳過 {shop_id}（已存在）")
                            skipped_count += 1
                            continue
                    
                    # 準備資料（對應您的 SharePoint 欄位）
                    shop_data = {
                        "shop_id": shop_id,
                        "shop_name": fields.get("field_7", ""),  # Shop Name
                        "address": fields.get("field_8", ""),  # Address
                        "region": fields.get("field_9", ""),  # Region
                        "district": fields.get("field_10", ""),  # District
                        "brand": fields.get("field_11", ""),  # Brand
                        "brand_code": fields.get("field_12", ""),  # Brand Code
                        "division": fields.get("field_13", ""),  # Division
                        "english_address": fields.get("field_14", ""),  # English Address
                        "location": fields.get("field_15", ""),  # Location
                        "lat": fields.get("field_20", 0.0),  # Latitude
                        "lng": fields.get("field_21", 0.0),  # Longitude
                        "brand_icon_url": fields.get("field_22", ""),  # Brand Icon
                        "is_mtr": fields.get("field_17", "N"),  # Is MTR
                        "phone": fields.get("field_37", ""),  # Phone
                        "is_active": "Y" if fields.get("field_35") == "Y" else "N",  # Active flag
                    }
                    
                    # 寫入或更新資料庫
                    if overwrite:
                        # UPSERT 操作
                        cur.execute("""
                            INSERT OR REPLACE INTO shop_master (
                                shop_id, shop_name, address, region, district,
                                brand, brand_code, division, english_address, location,
                                lat, lng, brand_icon_url, is_mtr, phone, is_active
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """, (
                            shop_data["shop_id"],
                            shop_data["shop_name"],
                            shop_data["address"],
                            shop_data["region"],
                            shop_data["district"],
                            shop_data["brand"],
                            shop_data["brand_code"],
                            shop_data["division"],
                            shop_data["english_address"],
                            shop_data["location"],
                            shop_data["lat"],
                            shop_data["lng"],
                            shop_data["brand_icon_url"],
                            shop_data["is_mtr"],
                            shop_data["phone"],
                            shop_data["is_active"]
                        ))
                    else:
                        # 只插入新記錄
                        cur.execute("""
                            INSERT INTO shop_master (
                                shop_id, shop_name, address, region, district,
                                brand, brand_code, division, english_address, location,
                                lat, lng, brand_icon_url, is_mtr, phone, is_active
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """, (
                            shop_data["shop_id"],
                            shop_data["shop_name"],
                            shop_data["address"],
                            shop_data["region"],
                            shop_data["district"],
                            shop_data["brand"],
                            shop_data["brand_code"],
                            shop_data["division"],
                            shop_data["english_address"],
                            shop_data["location"],
                            shop_data["lat"],
                            shop_data["lng"],
                            shop_data["brand_icon_url"],
                            shop_data["is_mtr"],
                            shop_data["phone"],
                            shop_data["is_active"]
                        ))
                    
                    success_count += 1
                    print(f"✅ 成功匯入: {shop_id}")
                    
                except Exception as e:
                    failed_count += 1
                    print(f"❌ 匯入失敗 {shop_id}: {e}")
            
            conn.commit()
        
        print(f"\n📊 匯入完成：")
        print(f"   ✅ 成功: {success_count}")
        print(f"   ❌ 失敗: {failed_count}")
        print(f"   ⏭️ 跳過: {skipped_count}")
        
        return {
            "success": success_count,
            "failed": failed_count,
            "skipped": skipped_count
        }
        
    except Exception as e:
        print(f"❌ SharePoint 匯入失敗: {e}")
        import traceback
        traceback.print_exc()
        raise
