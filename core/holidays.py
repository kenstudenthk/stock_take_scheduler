# core/holidays.py

import datetime
import pandas as pd
from core.data_access import get_conn, get_db_connection
from functools import lru_cache


# ✅ 使用 cache 避免重複查詢
_holiday_cache = None


def _load_holidays_cache():
    """Load all holidays into memory once."""
    global _holiday_cache
    if _holiday_cache is None:
        with get_db_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT date FROM holidays;")
            _holiday_cache = {row[0] for row in cur.fetchall()}
    return _holiday_cache


def clear_holidays_cache():
    """Clear cache when holidays are updated (call this in settings UI)."""
    global _holiday_cache
    _holiday_cache = None


def is_business_day(d: datetime.date) -> bool:
    """
    Check if a date is a business day (not weekend, not holiday).
    Uses in-memory cache for performance.
    """
    # Weekend check (Saturday=5, Sunday=6)
    if d.weekday() >= 5:
        return False
    
    # Holiday check using cache
    holidays = _load_holidays_cache()
    return d.isoformat() not in holidays


def next_business_day(start: datetime.date) -> datetime.date:
    """Find the next business day from start date."""
    d = start
    while not is_business_day(d):
        d += datetime.timedelta(days=1)
    return d


def get_holiday_df() -> pd.DataFrame:
    """Get all holidays as DataFrame for Settings tab display."""
    with get_db_connection() as conn:
        df = pd.read_sql_query(
            "SELECT date, name_chi, type FROM holidays ORDER BY date;",  # ✅
            conn
        )
    return df


def add_holiday(date: str, name_chi: str, holiday_type: str = "General"):  # ✅
    """Add a new holiday (call clear_holidays_cache after)."""
    with get_db_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT OR REPLACE INTO holidays (date, name_chi, type)  # ✅
            VALUES (?, ?, ?);
            """,
            (date, name_chi, holiday_type),
        )
    clear_holidays_cache()


def import_holidays_from_list(holidays_list: list[dict]):
    """
    Batch import holidays.
    holidays_list format: [{"date": "2025-01-01", "name_chi": "元旦", "type": "Statutory"}, ...]  # ✅
    """
    with get_db_connection() as conn:
        cur = conn.cursor()
        cur.executemany(
            """
            INSERT OR REPLACE INTO holidays (date, name_chi, type)  # ✅
            VALUES (?, ?, ?);
            """,
            [(h["date"], h["name_chi"], h.get("type", "General")) for h in holidays_list],  # ✅
        )
    clear_holidays_cache()


# ✅ 更新預設假期資料格式
HK_HOLIDAYS_2025_2026 = [
    {"date": "2025-01-01", "name_chi": "元旦", "type": "Statutory"},  # ✅
    {"date": "2025-01-29", "name_chi": "農曆年初一", "type": "Statutory"},
    {"date": "2025-01-30", "name_chi": "農曆年初二", "type": "Statutory"},
    {"date": "2025-01-31", "name_chi": "農曆年初三", "type": "Statutory"},
    {"date": "2025-04-04", "name_chi": "清明節", "type": "Statutory"},
    {"date": "2025-04-18", "name_chi": "耶穌受難節", "type": "Statutory"},
    {"date": "2025-04-19", "name_chi": "耶穌受難節翌日", "type": "Statutory"},
    {"date": "2025-04-21", "name_chi": "復活節星期一", "type": "Statutory"},
    {"date": "2025-05-01", "name_chi": "勞動節", "type": "Statutory"},
    {"date": "2025-05-05", "name_chi": "佛誕", "type": "Statutory"},
    {"date": "2025-05-31", "name_chi": "端午節", "type": "Statutory"},
    {"date": "2025-07-01", "name_chi": "香港特別行政區成立紀念日", "type": "Statutory"},
    {"date": "2025-10-01", "name_chi": "國慶日", "type": "Statutory"},
    {"date": "2025-10-07", "name_chi": "中秋節翌日", "type": "Statutory"},
    {"date": "2025-10-11", "name_chi": "重陽節", "type": "Statutory"},
    {"date": "2025-12-25", "name_chi": "聖誕節", "type": "Statutory"},
    {"date": "2025-12-26", "name_chi": "聖誕節後第一個周日", "type": "Statutory"},
    {"date": "2026-01-01", "name_chi": "元旦", "type": "Statutory"},
]



def init_default_holidays():
    """Initialize default Hong Kong holidays if table is empty."""
    with get_db_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM holidays;")
        count = cur.fetchone()[0]
        
        if count == 0:
            print("Initializing default Hong Kong holidays...")
            import_holidays_from_list(HK_HOLIDAYS_2025_2026)
            print(f"✓ Added {len(HK_HOLIDAYS_2025_2026)} default holidays")
