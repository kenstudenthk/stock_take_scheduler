# core/clustering.py
"""
Proximity-based shop clustering for optimized schedule generation.

This module implements geographical clustering algorithms inspired by the 2024 R script,
with enhancements for real-time traffic data and filter compatibility.
"""

import numpy as np
import networkx as nx
from sklearn.cluster import KMeans
from sklearn.metrics.pairwise import haversine_distances
from typing import List, Dict, Tuple, Set
import math


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calculate great-circle distance between two points using Haversine formula.
    
    Args:
        lat1, lon1: First point coordinates
        lat2, lon2: Second point coordinates
        
    Returns:
        Distance in kilometers
    """
    R = 6371.0  # Earth radius in km
    
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)
    
    a = (math.sin(d_phi / 2) ** 2 + 
         math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    
    return R * c


def build_neighbor_network(
    shops: List[dict],
    max_distance_km: float = 5.5,
    max_neighbors: int = 5,
    same_region_only: bool = True
) -> Dict[str, List[Tuple[str, float]]]:
    """
    Build a neighbor network for each shop (inspired by 2024 R script).
    
    For each shop, find up to `max_neighbors` nearest shops within `max_distance_km`
    that are in the same region (if same_region_only=True).
    
    Args:
        shops: List of shop dictionaries with keys: shop_id, lat, lng, region_code
        max_distance_km: Maximum distance to consider as "nearby" (default: 5.5 km)
        max_neighbors: Maximum number of neighbors per shop (default: 5)
        same_region_only: Only allow neighbors in same region (default: True)
        
    Returns:
        Dictionary mapping shop_id to list of (nearby_shop_id, distance_km) tuples
        
    Example:
        {
            "S001": [("S002", 0.3), ("S005", 0.8), ("S010", 1.2)],
            "S002": [("S001", 0.3), ("S003", 0.5)],
            ...
        }
    """
    # Filter shops with valid coordinates
    valid_shops = [
        s for s in shops 
        if s.get('lat') is not None and s.get('lng') is not None
    ]
    
    if len(valid_shops) == 0:
        return {}
    
    # Build coordinate matrix for vectorized calculation
    coords = np.array([[s['lat'], s['lng']] for s in valid_shops])
    coords_rad = np.radians(coords)
    
    # Calculate distance matrix using haversine
    dist_matrix_rad = haversine_distances(coords_rad)
    dist_matrix_km = dist_matrix_rad * 6371.0  # Earth radius
    
    # Build neighbor map
    neighbor_map = {}
    
    for i, shop in enumerate(valid_shops):
        shop_id = shop['shop_id']
        region = shop.get('region_code', '')
        
        neighbors = []
        
        for j, other_shop in enumerate(valid_shops):
            if i == j:
                continue  # Skip self
            
            # Same region check
            if same_region_only and other_shop.get('region_code') != region:
                continue
            
            dist_km = dist_matrix_km[i][j]
            
            # Distance threshold check
            if dist_km <= max_distance_km:
                neighbors.append((other_shop['shop_id'], round(dist_km, 3)))
        
        # Sort by distance and take top N
        neighbors_sorted = sorted(neighbors, key=lambda x: x[1])[:max_neighbors]
        neighbor_map[shop_id] = neighbors_sorted
    
    return neighbor_map


def cluster_shops_by_proximity(
    shops: List[dict],
    neighbor_map: Dict[str, List[Tuple[str, float]]],
    max_per_cluster: int = 10,
    min_cluster_size: int = 2
) -> List[List[str]]:
    """
    Cluster shops based on proximity network using graph connected components.
    
    Algorithm:
    1. Build undirected graph from neighbor_map
    2. Find connected components
    3. If component is too large (> max_per_cluster), split using K-Means
    4. If component is too small (< min_cluster_size), keep as is
    
    Args:
        shops: List of shop dictionaries
        neighbor_map: Output from build_neighbor_network()
        max_per_cluster: Maximum shops per cluster (will split if exceeded)
        min_cluster_size: Minimum shops per cluster (clusters below this won't be split further)
        
    Returns:
        List of clusters, where each cluster is a list of shop_ids
        
    Example:
        [
            ["S001", "S002", "S003"],  # Cluster 1: 3 nearby shops
            ["S010", "S011"],          # Cluster 2: 2 nearby shops
            ["S020"],                  # Cluster 3: 1 isolated shop
            ...
        ]
    """
    # Build undirected graph
    G = nx.Graph()
    
    for shop_id, neighbors in neighbor_map.items():
        for nearby_id, dist in neighbors:
            G.add_edge(shop_id, nearby_id, weight=dist)
    
    # Add isolated nodes (shops with no neighbors)
    all_shop_ids = {s['shop_id'] for s in shops}
    for shop_id in all_shop_ids:
        if shop_id not in G:
            G.add_node(shop_id)
    
    # Find connected components
    components = list(nx.connected_components(G))
    
    clusters = []
    
    for component in components:
        component_list = list(component)
        
        # If component is small enough, keep as is
        if len(component_list) <= max_per_cluster:
            clusters.append(component_list)
        else:
            # Split large component using K-Means
            sub_clusters = _split_large_cluster(
                component_list, shops, max_per_cluster, min_cluster_size
            )
            clusters.extend(sub_clusters)
    
    return clusters


def _split_large_cluster(
    shop_ids: List[str],
    shops: List[dict],
    max_size: int,
    min_size: int = 2,
    depth: int = 0,
    max_depth: int = 10
) -> List[List[str]]:
    """
    Split a large cluster into smaller ones using K-Means clustering.
    
    Args:
        shop_ids: List of shop IDs in the large cluster
        shops: Full list of shop dictionaries
        max_size: Maximum size per sub-cluster
        min_size: Minimum size per sub-cluster
        depth: Current recursion depth (internal use)
        max_depth: Maximum recursion depth to prevent infinite loops
        
    Returns:
        List of sub-clusters
    """
    # ✅ 終止條件 1: 達到最大遞迴深度
    if depth >= max_depth:
        print(f"⚠️ Max recursion depth reached at depth {depth}, returning cluster as-is")
        return [shop_ids]
    
    # ✅ 終止條件 2: 集群已經夠小
    if len(shop_ids) <= max_size:
        return [shop_ids]
    
    # ✅ 終止條件 3: 集群太小無法分割
    if len(shop_ids) < 2:
        return [shop_ids]
    
    # Build shop_id -> shop dict mapping
    shop_dict = {s['shop_id']: s for s in shops}
    
    # Extract coordinates
    coords = []
    valid_ids = []
    
    for sid in shop_ids:
        shop = shop_dict.get(sid)
        if shop and shop.get('lat') is not None and shop.get('lng') is not None:
            coords.append([shop['lat'], shop['lng']])
            valid_ids.append(sid)
    
    # ✅ 終止條件 4: 沒有有效座標
    if len(valid_ids) == 0:
        return []
    
    if len(valid_ids) <= max_size:
        return [valid_ids]
    
    # Calculate number of clusters needed
    n_clusters = math.ceil(len(valid_ids) / max_size)
    n_clusters = max(2, min(n_clusters, len(valid_ids)))  # ✅ 確保不超過店舖數量
    
    # ✅ 終止條件 5: 無法進一步分割
    if n_clusters < 2:
        return [valid_ids]
    
    try:
        # Apply K-Means
        coords_array = np.array(coords)
        kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
        labels = kmeans.fit_predict(coords_array)
        
        # Group by cluster label
        sub_clusters = [[] for _ in range(n_clusters)]
        for sid, label in zip(valid_ids, labels):
            sub_clusters[label].append(sid)
        
        # Filter out empty clusters
        sub_clusters = [sc for sc in sub_clusters if len(sc) > 0]
        
        # ✅ 檢查分割是否有效 (避免無限遞迴)
        if len(sub_clusters) == 1 or max(len(sc) for sc in sub_clusters) >= len(valid_ids):
            # 分割無效,直接返回
            print(f"⚠️ K-Means split ineffective at depth {depth}, returning as-is")
            return [valid_ids]
        
        # If splitting resulted in clusters that are still too large, recursively split
        final_clusters = []
        for sc in sub_clusters:
            if len(sc) > max_size and len(sc) < len(valid_ids):  # ✅ 確保有進展
                # ✅ 傳遞 depth + 1
                final_clusters.extend(
                    _split_large_cluster(sc, shops, max_size, min_size, depth + 1, max_depth)
                )
            else:
                final_clusters.append(sc)
        
        return final_clusters
        
    except Exception as e:
        # ✅ 如果 K-Means 失敗,降級處理
        print(f"⚠️ K-Means failed at depth {depth}: {e}")
        # 簡單分割成相等大小的子集群
        chunk_size = max_size
        return [valid_ids[i:i+chunk_size] for i in range(0, len(valid_ids), chunk_size)]



def calculate_cluster_quality(
    clusters: List[List[str]],
    shops: List[dict],
    neighbor_map: Dict[str, List[Tuple[str, float]]]
) -> Dict[str, float]:
    """
    Calculate quality metrics for the clustering result.
    
    Metrics:
    - avg_intra_cluster_distance: Average distance between shops within same cluster
    - region_consistency: Percentage of clusters with all shops in same region
    - avg_cluster_size: Average number of shops per cluster
    - total_clusters: Total number of clusters
    
    Args:
        clusters: Output from cluster_shops_by_proximity()
        shops: List of shop dictionaries
        neighbor_map: Output from build_neighbor_network()
        
    Returns:
        Dictionary of quality metrics
    """
    shop_dict = {s['shop_id']: s for s in shops}
    
    total_intra_dist = 0.0
    total_pairs = 0
    same_region_clusters = 0
    
    for cluster in clusters:
        if len(cluster) < 2:
            continue
        
        # Calculate intra-cluster distances
        for i, sid1 in enumerate(cluster):
            for sid2 in cluster[i+1:]:
                shop1 = shop_dict.get(sid1)
                shop2 = shop_dict.get(sid2)
                
                if shop1 and shop2 and shop1.get('lat') and shop2.get('lat'):
                    dist = haversine_km(
                        shop1['lat'], shop1['lng'],
                        shop2['lat'], shop2['lng']
                    )
                    total_intra_dist += dist
                    total_pairs += 1
        
        # Check region consistency
        regions = {shop_dict[sid].get('region_code') for sid in cluster if sid in shop_dict}
        if len(regions) == 1:
            same_region_clusters += 1
    
    avg_intra_dist = total_intra_dist / total_pairs if total_pairs > 0 else 0.0
    region_consistency = same_region_clusters / len(clusters) if len(clusters) > 0 else 0.0
    avg_cluster_size = sum(len(c) for c in clusters) / len(clusters) if len(clusters) > 0 else 0.0
    
    return {
        "avg_intra_cluster_distance_km": round(avg_intra_dist, 2),
        "region_consistency_pct": round(region_consistency * 100, 1),
        "avg_cluster_size": round(avg_cluster_size, 1),
        "total_clusters": len(clusters),
        "singleton_clusters": sum(1 for c in clusters if len(c) == 1),
        "large_clusters": sum(1 for c in clusters if len(c) >= 5),
    }


def assign_clusters_to_days(
    clusters: List[List[str]],
    start_date,
    shops_per_day: int,
    groups_per_day: int = 3,
    include_mtr_filter: str = "Yes",
    cross_region_filter: str = "Allow",
    shop_dict: Dict[str, dict] = None
) -> List[dict]:
    """
    Assign shop clusters to specific dates and groups.
    
    Strategy:
    1. Sort clusters by size (larger first) to avoid fragmentation
    2. Fill each day's quota with complete clusters when possible
    3. Respect MTR separation if include_mtr_filter="Separate plan"
    4. Respect region boundaries if cross_region_filter="Limit to same region"
    
    Args:
        clusters: Output from cluster_shops_by_proximity()
        start_date: datetime.date object
        shops_per_day: Total shops to schedule per day
        groups_per_day: Number of groups per day
        include_mtr_filter: "Yes", "No", or "Separate plan"
        cross_region_filter: "Allow" or "Limit to same region"
        shop_dict: Optional pre-built shop_id -> shop mapping
        
    Returns:
        List of assignment dicts with keys: date, shop_id, group_no
    """
    from core import holidays
    import datetime
    
    # Sort clusters by size (descending) to reduce fragmentation
    sorted_clusters = sorted(clusters, key=len, reverse=True)
    
    # Handle MTR separation
    if include_mtr_filter == "Separate plan" and shop_dict:
        mtr_clusters = []
        non_mtr_clusters = []
        
        for cluster in sorted_clusters:
            is_mtr_cluster = any(
                shop_dict.get(sid, {}).get('is_mtr', 0) == 1
                for sid in cluster
            )
            if is_mtr_cluster:
                mtr_clusters.append(cluster)
            else:
                non_mtr_clusters.append(cluster)
        
        # Schedule non-MTR first, then MTR
        sorted_clusters = non_mtr_clusters + mtr_clusters
    
    # Initialize scheduling
    current_date = start_date if isinstance(start_date, datetime.date) else datetime.date.fromisoformat(str(start_date))
    current_date = holidays.next_business_day(current_date)
    
    daily_quota = shops_per_day
    shops_per_group = shops_per_day // groups_per_day
    
    assignments = []
    current_day_shops = 0
    
    for cluster in sorted_clusters:
        cluster_size = len(cluster)
        
        # If cluster doesn't fit in current day, move to next day
        if current_day_shops + cluster_size > shops_per_day:
            # Move to next business day
            current_date += datetime.timedelta(days=1)
            current_date = holidays.next_business_day(current_date)
            current_day_shops = 0
        
        # Assign each shop in cluster to current date
        for i, shop_id in enumerate(cluster):
            # Calculate group number (1-indexed)
            position_in_day = current_day_shops + i
            group_no = (position_in_day // shops_per_group) + 1
            group_no = min(group_no, groups_per_day)  # Cap at max groups
            
            assignments.append({
                'date': current_date.isoformat(),
                'shop_id': shop_id,
                'group_no': group_no
            })
        
        current_day_shops += cluster_size
    
    return assignments
