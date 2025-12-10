# core/scheduler_engine.py
import math
from core import route_optimizer
import datetime
from dataclasses import dataclass
from typing import List
from core import data_access
from core import holidays
from core import amap_client


@dataclass
class ScheduleResult:
    total_shops: int
    business_days: int
    start_date: datetime.date
    finish_date: datetime.date
    avg_daily_distance_km: float = 0.0
    avg_public_transport_hours: float = 0.0
    shops_closed: int = 0
    shops_finished: int = 0
    region_counts: dict | None = None


def estimate_required_business_days(total_shops: int, shops_per_day: int) -> int:
    if shops_per_day <= 0:
        return 0
    return (total_shops + shops_per_day - 1) // shops_per_day


def estimate_finish_date(start_date, required_days: int) -> datetime.date:
    if isinstance(start_date, datetime.date):
        d = start_date
    else:
        d = datetime.date.fromisoformat(str(start_date))

    count = 0
    while count < required_days:
        if holidays.is_business_day(d):
            count += 1
            if count == required_days:
                break
        d += datetime.timedelta(days=1)
    return d


def generate_schedule(
    shops_per_day: int,
    start_date,
    regions: List[str] | None = None,
    districts: List[str] | None = None,
    include_mtr: str = "Yes",
    cross_region: str = "Allow",
    include_distance: bool = False,
) -> ScheduleResult:
    # 0. Read group settings
    raw_groups = data_access.get_setting("groups_per_day", None)
    raw_per_group = data_access.get_setting("shops_per_group", None)

    try:
        groups_per_day = int(raw_groups) if raw_groups is not None else 3
    except (TypeError, ValueError):
        groups_per_day = 3

    try:
        shops_per_group = int(raw_per_group) if raw_per_group is not None else 3
    except (TypeError, ValueError):
        shops_per_group = 3

    shops_per_day = groups_per_day * shops_per_group

    # 1. Get active shops
    shops = data_access.get_all_shops(active_only=True)

    # Region / District / MTR filters
    if regions:
        region_map = {
            "Hong Kong Island": "HK",
            "Kowloon": "KN",
            "New Territories": "NT",
            "Islands": "IS",
            "Macau": "MO",
        }
        region_codes = {region_map[r] for r in regions if r in region_map}
        shops = [s for s in shops if s["region_code"] in region_codes]

    if districts:
        shops = [s for s in shops if s["district_en"] in districts]

    if include_mtr == "No":
        shops = [s for s in shops if s["is_mtr"] == 0]

    # 2. Sort
    shops_sorted = sorted(
        shops,
        key=lambda s: (s["region_code"], s["district_en"] or "", s["shop_id"]),
    )
    total_shops = len(shops_sorted)

    if total_shops == 0:
        return ScheduleResult(
            total_shops=0,
            business_days=0,
            start_date=start_date if isinstance(start_date, datetime.date) else datetime.date.fromisoformat(str(start_date)),
            finish_date=start_date if isinstance(start_date, datetime.date) else datetime.date.fromisoformat(str(start_date)),
            region_counts={"HK": 0, "KN": 0, "NT": 0, "IS": 0, "MO": 0},
        )

    # 3. ✅ Prepare batch insert data
    if isinstance(start_date, datetime.date):
        d = start_date
    else:
        d = datetime.date.fromisoformat(str(start_date))

    now = datetime.datetime.now().isoformat(timespec="seconds")
    
    # ✅ Collect all rows in memory first (MUCH faster)
    schedule_rows = []
    assigned = 0
    business_days_used = 0

    while assigned < total_shops:
        d = holidays.next_business_day(d)
        day_quota = shops_per_day

        while day_quota > 0 and assigned < total_shops:
            shop = shops_sorted[assigned]

            index_in_day = shops_per_day - day_quota
            group_no = (index_in_day // shops_per_group) + 1
            if group_no > groups_per_day:
                group_no = groups_per_day

            schedule_rows.append((
                d.isoformat(),
                shop["shop_id"],
                "Planned",
                None,
                "Auto",
                0,       # temporary
                0.0,
                0.0,
                now,
                now,
                group_no,
            ))

            assigned += 1
            day_quota -= 1

        business_days_used += 1
        d += datetime.timedelta(days=1)

    # ✅ Single transaction with batch insert
    with data_access.get_db_connection() as conn:
        cur = conn.cursor()
        cur.execute("DELETE FROM schedule;")
        
        # ✅ executemany is MUCH faster than looping execute
        cur.executemany(
            """
            INSERT INTO schedule (
                date, shop_id, status, status_reason,
                assigned_by, day_route_order,
                day_total_distance_km, day_total_travel_time_min,
                created_at, updated_at, group_no
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """,
            schedule_rows,
        )

    # Save capacity setting
    data_access.set_setting("shops_per_day", str(shops_per_day))

    finish_date = estimate_finish_date(start_date, business_days_used)

    # ✅ Optimize routes (uses its own connection)
    _optimize_day_route_orders()

    # ✅ Optional distance calculation
    if include_distance:
        _compute_day_totals_with_amap()
    else:
        with data_access.get_db_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                UPDATE schedule
                SET day_total_distance_km = 0.0,
                    day_total_travel_time_min = 0.0;
                """
            )

    # Region counts
    region_counts = {"HK": 0, "KN": 0, "NT": 0, "IS": 0, "MO": 0}
    for s in shops_sorted:
        code = s["region_code"]
        if code in region_counts:
            region_counts[code] += 1

    result = ScheduleResult(
        total_shops=total_shops,
        business_days=business_days_used,
        start_date=start_date if isinstance(start_date, datetime.date) else datetime.date.fromisoformat(str(start_date)),
        finish_date=finish_date,
        avg_daily_distance_km=0.0,
        avg_public_transport_hours=0.0,
        shops_closed=0,
        shops_finished=0,
        region_counts=region_counts,
    )
    return result


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Approximate great-circle distance between two points (km)."""
    R = 6371.0
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)

    a = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c


def _compute_day_totals_with_amap():
    """Sum driving distance & time for each day using AMap API."""
    with data_access.get_db_connection() as conn:
        cur = conn.cursor()

        cur.execute("SELECT DISTINCT date FROM schedule ORDER BY date;")
        dates = [r[0] for r in cur.fetchall()]

        for d in dates:
            cur.execute(
                """
                SELECT s.shop_id, s.day_route_order, sm.lat, sm.lng
                FROM schedule s
                JOIN shop_master sm ON s.shop_id = sm.shop_id
                WHERE s.date = ?
                ORDER BY s.day_route_order;
                """,
                (d,),
            )
            rows = cur.fetchall()
            
            if len(rows) <= 1:
                total_dist_km = 0.0
                total_time_min = 0.0
            else:
                total_dist_km = 0.0
                total_time_min = 0.0

                for i in range(len(rows) - 1):
                    _, _, lat_a, lng_a = rows[i]
                    _, _, lat_b, lng_b = rows[i + 1]

                    if lat_a is None or lng_a is None or lat_b is None or lng_b is None:
                        continue

                    dist_km, time_min = amap_client.get_route_distance_time(
                        origin_lng=lng_a,
                        origin_lat=lat_a,
                        dest_lng=lng_b,
                        dest_lat=lat_b,
                    )
                    total_dist_km += dist_km
                    total_time_min += time_min

            cur.execute(
                """
                UPDATE schedule
                SET day_total_distance_km = ?, day_total_travel_time_min = ?
                WHERE date = ?;
                """,
                (total_dist_km, total_time_min, d),
            )


def _optimize_day_route_orders():
    """
    For each date and group, use TSP to optimize visiting order.
    ✅ Uses single connection for all optimizations.
    """
    with data_access.get_db_connection() as conn:
        cur = conn.cursor()

        # Get all dates
        cur.execute("SELECT DISTINCT date FROM schedule ORDER BY date;")
        dates = [r[0] for r in cur.fetchall()]

        for d in dates:
            # Get all groups for this date
            cur.execute(
                "SELECT DISTINCT group_no FROM schedule WHERE date = ? ORDER BY group_no;",
                (d,),
            )
            groups = [g[0] for g in cur.fetchall()]

            for gno in groups:
                cur.execute(
                    """
                    SELECT s.shop_id, s.day_route_order, sm.lat, sm.lng
                    FROM schedule s
                    JOIN shop_master sm ON s.shop_id = sm.shop_id
                    WHERE s.date = ? AND s.group_no = ?
                    ORDER BY s.rowid;
                    """,
                    (d, gno),
                )
                rows = cur.fetchall()
                n = len(rows)
                
                if n <= 1:
                    if n == 1:
                        shop_id, _, _, _ = rows[0]
                        cur.execute(
                            """
                            UPDATE schedule
                            SET day_route_order = 1
                            WHERE date = ? AND group_no = ? AND shop_id = ?;
                            """,
                            (d, gno, shop_id),
                        )
                    continue

                # Build distance matrix
                distance_matrix = []
                for i in range(n):
                    _, _, lat_i, lng_i = rows[i]
                    row_i = []
                    for j in range(n):
                        _, _, lat_j, lng_j = rows[j]
                        if i == j or lat_i is None or lng_i is None or lat_j is None or lng_j is None:
                            row_i.append(0.0)
                        else:
                            dist_km = _haversine_km(lat_i, lng_i, lat_j, lng_j)
                            row_i.append(dist_km * 1000.0)  # meters
                    distance_matrix.append(row_i)

                # Solve TSP
                order = route_optimizer.solve_tsp(distance_matrix)

                # ✅ Batch update using executemany
                update_data = []
                for new_order, idx in enumerate(order, start=1):
                    shop_id, _, _, _ = rows[idx]
                    update_data.append((new_order, d, gno, shop_id))

                cur.executemany(
                    """
                    UPDATE schedule
                    SET day_route_order = ?
                    WHERE date = ? AND group_no = ? AND shop_id = ?;
                    """,
                    update_data,
                )
