# core/scheduler_engine.py
"""
Schedule generation engine with proximity-based clustering.
"""

import math
import datetime
from dataclasses import dataclass
from typing import List
from core import data_access, holidays, amap_client, route_optimizer, clustering


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
    cluster_quality: dict | None = None  # ✅ NEW


def estimate_required_business_days(total_shops: int, shops_per_day: int) -> int:
    """Estimate number of business days needed."""
    if shops_per_day <= 0:
        return 0
    return (total_shops + shops_per_day - 1) // shops_per_day


def estimate_finish_date(start_date, required_days: int) -> datetime.date:
    """Calculate finish date by counting required_days business days."""
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
    use_clustering: bool = True,  # ✅ NEW
) -> ScheduleResult:
    """
    Generate optimized schedule with proximity-based clustering.
    """
    # ========== Phase 0: Read settings ==========
    raw_groups = data_access.get_setting("groups_per_day", None)
    raw_per_group = data_access.get_setting("shops_per_group", None)
    
    try:
        groups_per_day = int(raw_groups) if raw_groups is not None else 3
    except (TypeError, ValueError):
        groups_per_day = 3
    
    try:
        shops_per_group = int(raw_per_group) if raw_per_group is not None else (shops_per_day // groups_per_day)
    except (TypeError, ValueError):
        shops_per_group = shops_per_day // groups_per_day
    
    shops_per_day = groups_per_day * shops_per_group
    
    # ========== Phase 1: Get and filter shops ==========
    shops = data_access.get_all_shops(active_only=True)

    if regions:
        # ✅ regions 參數現在接收代碼 (如 ["NT"])
        shops = [s for s in shops if s["region"] in regions]

    if districts:
        # ✅ 使用正確的欄位名稱
        shops = [s for s in shops if s["district"] in districts]

    if include_mtr == "No":
        shops = [s for s in shops if s["is_mtr"] != "Y"]


    total_shops = len(shops)
    
    if total_shops == 0:
        return ScheduleResult(
            total_shops=0,
            business_days=0,
            start_date=start_date if isinstance(start_date, datetime.date) else datetime.date.fromisoformat(str(start_date)),
            finish_date=start_date if isinstance(start_date, datetime.date) else datetime.date.fromisoformat(str(start_date)),
            region_counts={"HK": 0, "KN": 0, "NT": 0, "IS": 0, "MO": 0},
        )
    
    # ========== Phase 2 & 3: Clustering (NEW) ==========
    if use_clustering:
        print("📍 Building neighbor network...")
        neighbor_map = clustering.build_neighbor_network(
            shops,
            max_distance_km=5.5,
            max_neighbors=5,
            same_region_only=(cross_region == "Limit to same region")
        )
        
        print("🗂️ Clustering shops by proximity...")
        max_cluster_size = min(shops_per_day, 12)
        clusters = clustering.cluster_shops_by_proximity(
            shops,
            neighbor_map,
            max_per_cluster=max_cluster_size,
            min_cluster_size=1
        )
        
        print(f"✓ Created {len(clusters)} clusters")
        
        cluster_quality = clustering.calculate_cluster_quality(clusters, shops, neighbor_map)
        print(f"✓ Avg intra-cluster distance: {cluster_quality['avg_intra_cluster_distance_km']} km")
        print(f"✓ Region consistency: {cluster_quality['region_consistency_pct']}%")
        
        # ========== Phase 4: Assign clusters to days ==========
        shop_dict = {s['shop_id']: s for s in shops}
        
        print("📅 Assigning clusters to days...")
        assignments = clustering.assign_clusters_to_days(
            clusters,
            start_date,
            shops_per_day,
            groups_per_day,
            include_mtr,
            cross_region,
            shop_dict
        )
        
    else:
        # ========== Fallback: Simple sorting ==========
    
        print("📋 Using simple sorting (no clustering)...")
        shops_sorted = sorted(
            shops,
            key=lambda s: (s["region"], s.get("district", ""), s["shop_id"]),  # ✅ 修正欄位名稱
        )

        
        if isinstance(start_date, datetime.date):
            d = start_date
        else:
            d = datetime.date.fromisoformat(str(start_date))
        
        assignments = []
        assigned = 0
        
        while assigned < total_shops:
            d = holidays.next_business_day(d)
            day_quota = shops_per_day
            
            while day_quota > 0 and assigned < total_shops:
                shop = shops_sorted[assigned]
                index_in_day = shops_per_day - day_quota
                group_no = (index_in_day // shops_per_group) + 1
                group_no = min(group_no, groups_per_day)
                
                assignments.append({
                    'date': d.isoformat(),
                    'shop_id': shop['shop_id'],
                    'group_no': group_no
                })
                
                assigned += 1
                day_quota -= 1
            
            d += datetime.timedelta(days=1)
        
        cluster_quality = None
    
    # ========== Phase 5: Write to database ==========
    print("💾 Writing schedule to database...")
    now = datetime.datetime.now().isoformat(timespec="seconds")

    schedule_rows = []
    for assignment in assignments:
        # ✅ 需要從 shop_id 查詢店舖資料
        shop = next((s for s in shops if s['shop_id'] == assignment['shop_id']), None)
        
        if shop:
            schedule_rows.append((
                assignment['shop_id'],
                shop.get('shop_name', ''),
                shop.get('address', ''),
                shop.get('region', ''),
                shop.get('district', ''),
                shop.get('brand', ''),
                shop.get('lat', 0.0),
                shop.get('lng', 0.0),
                shop.get('is_mtr', 'N'),
                assignment['date'],  # ✅ schedule_date
                assignment['group_no'],
                "Planned",
                now,
            ))

    with data_access.get_db_connection() as conn:
        cur = conn.cursor()
        cur.execute("DELETE FROM schedule;")
        cur.executemany(
            """
            INSERT INTO schedule (
                shop_id, shop_name, address, region, district,
                brand, lat, lng, is_mtr,
                schedule_date, group_number, status, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """,
            schedule_rows,
        )

    print(f"✓ Scheduled {len(schedule_rows)} shops")


    
    data_access.set_setting("shops_per_day", str(shops_per_day))
    
    unique_dates = sorted(set(a['date'] for a in assignments))
    business_days_used = len(unique_dates)
    finish_date = estimate_finish_date(start_date, business_days_used)
    
    # ========== Phase 6: Optimize routes ==========
    print("🔄 Optimizing routes...")
    _optimize_day_route_orders()
    
    # ========== Phase 7: Optional distance calculation ==========
    if include_distance:
        print("🗺️ Calculating distances with AMap API...")
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
    
    # ========== Calculate statistics ==========
   
    region_counts = {"HK": 0, "KN": 0, "NT": 0, "IS": 0, "MO": 0}
    for s in shops:
        code = s["region"]  # ✅ 改為 s["region"]
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
        cluster_quality=cluster_quality,
    )
    
    print("✅ Schedule generation complete!")
    return result


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Approximate great-circle distance between two points (km)."""
    R = 6371.0
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)
    
    a = (math.sin(d_phi / 2) ** 2 + 
         math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    
    return R * c


def _compute_day_totals_with_amap():
    """Sum driving distance & time for each day using AMap API."""
    with data_access.get_db_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT DISTINCT schedule_date FROM schedule ORDER BY schedule_date;")
        dates = [r[0] for r in cur.fetchall()]
        
        for d in dates:
            cur.execute(
                """
                SELECT s.shop_id, sm.lat, sm.lng
                FROM schedule s
                JOIN shop_master sm ON s.shop_id = sm.shop_id
                WHERE s.schedule_date = ?
                ORDER BY s.group_number, s.shop_id;
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
                    _, lat_a, lng_a = rows[i]
                    _, lat_b, lng_b = rows[i + 1]
                    
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
            
            # Note: 目前 schedule 表格沒有這些欄位,暫時跳過
            # cur.execute(
            #     """
            #     UPDATE schedule
            #     SET day_total_distance_km = ?, day_total_travel_time_min = ?
            #     WHERE schedule_date = ?;
            #     """,
            #     (total_dist_km, total_time_min, d),
            # )



def _optimize_day_route_orders():
    """For each date and group, use TSP to optimize visiting order."""
    with data_access.get_db_connection() as conn:
        cur = conn.cursor()
        
        cur.execute("SELECT DISTINCT schedule_date FROM schedule ORDER BY schedule_date;")
        dates = [r[0] for r in cur.fetchall()]
        
        for d in dates:
            cur.execute(
                "SELECT DISTINCT group_number FROM schedule WHERE schedule_date = ? ORDER BY group_number;",
                (d,),
            )
            groups = [g[0] for g in cur.fetchall()]
            
            for gno in groups:
                cur.execute(
                    """
                    SELECT s.shop_id, sm.lat, sm.lng
                    FROM schedule s
                    JOIN shop_master sm ON s.shop_id = sm.shop_id
                    WHERE s.schedule_date = ? AND s.group_number = ?
                    ORDER BY s.id;
                    """,
                    (d, gno),
                )
                rows = cur.fetchall()
                n = len(rows)
                
                if n <= 1:
                    # 只有 1 間或 0 間店舖,不需要優化
                    continue
                
                # Build distance matrix
                distance_matrix = []
                for i in range(n):
                    _, lat_i, lng_i = rows[i]
                    row_i = []
                    for j in range(n):
                        _, lat_j, lng_j = rows[j]
                        if i == j or lat_i is None or lng_i is None or lat_j is None or lng_j is None:
                            row_i.append(0.0)
                        else:
                            dist_km = _haversine_km(lat_i, lng_i, lat_j, lng_j)
                            row_i.append(dist_km * 1000.0)
                    distance_matrix.append(row_i)
                
                # Solve TSP
                try:
                    order = route_optimizer.solve_tsp(distance_matrix)
                    
                    # 目前 schedule 表格沒有 day_route_order 欄位
                    # 暫時跳過路徑順序更新
                    # 如果需要,可以加入 route_order 欄位
                    
                except Exception as e:
                    print(f"⚠️ TSP optimization failed for {d} group {gno}: {e}")
                    continue


# ❌ DELETE THIS SECTION - IT SHOULD NOT BE HERE
# (Remove the _render_stats function entirely from this file)
