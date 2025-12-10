# core/amap_client.py
import requests
import time
from functools import lru_cache
from core import data_access


AMAP_DRIVING_URL = "https://restapi.amap.com/v3/direction/driving"

# ✅ Rate limiting: avoid hitting API quota
_last_call_time = 0
_min_interval = 0.1  # 100ms between calls (10 req/sec max)


class AmapConfigError(Exception):
    """Raised when AMap API key is not configured."""
    pass


class AmapAPIError(Exception):
    """Raised when AMap API returns an error."""
    pass


def _get_api_key() -> str:
    """Get AMap API key from settings."""
    # ✅ Use consistent key name
    key = data_access.get_setting("AMAP_WEB_KEY", "")
    
    if not key:
        raise AmapConfigError(
            "AMap API key is not set. Please go to Settings tab and save it."
        )
    
    return key


def _rate_limit():
    """Ensure minimum interval between API calls."""
    global _last_call_time
    now = time.time()
    elapsed = now - _last_call_time
    
    if elapsed < _min_interval:
        time.sleep(_min_interval - elapsed)
    
    _last_call_time = time.time()


def get_route_distance_time(
    origin_lng: float,
    origin_lat: float,
    dest_lng: float,
    dest_lat: float,
    strategy: int = 0,
) -> tuple[float, float]:
    """
    Call AMap driving route API and return (distance_km, duration_min).
    
    Args:
        origin_lng: Origin longitude
        origin_lat: Origin latitude
        dest_lng: Destination longitude
        dest_lat: Destination latitude
        strategy: Route strategy (0=fastest, 1=avoid tolls, 2=shortest distance)
    
    Returns:
        (distance_km, duration_min) tuple. Returns (0.0, 0.0) on error.
    
    Raises:
        AmapConfigError: If API key is not configured
    """
    try:
        key = _get_api_key()
        
        # ✅ Rate limiting
        _rate_limit()
        
        params = {
            "key": key,
            "origin": f"{origin_lng},{origin_lat}",
            "destination": f"{dest_lng},{dest_lat}",
            "extensions": "base",
            "strategy": strategy,
        }
        
        resp = requests.get(AMAP_DRIVING_URL, params=params, timeout=10)  # ✅ Increased timeout
        resp.raise_for_status()
        data = resp.json()
        
        # ✅ Better error handling
        if data.get("status") != "1":
            error_info = data.get("info", "Unknown error")
            print(f"⚠️ AMap API error: {error_info}")
            return 0.0, 0.0
        
        # ✅ Safer data extraction
        if "route" not in data or "paths" not in data["route"] or not data["route"]["paths"]:
            print(f"⚠️ AMap API returned no routes")
            return 0.0, 0.0
        
        route = data["route"]["paths"][0]
        distance_m = float(route.get("distance", 0))
        duration_s = float(route.get("duration", 0))
        
        distance_km = distance_m / 1000.0
        duration_min = duration_s / 60.0
        
        return distance_km, duration_min
    
    except AmapConfigError:
        raise  # Re-raise config errors
    except requests.exceptions.Timeout:
        print(f"⚠️ AMap API timeout for route {origin_lng},{origin_lat} -> {dest_lng},{dest_lat}")
        return 0.0, 0.0
    except requests.exceptions.RequestException as e:
        print(f"⚠️ AMap API request error: {e}")
        return 0.0, 0.0
    except (KeyError, ValueError, TypeError) as e:
        print(f"⚠️ AMap API response parsing error: {e}")
        return 0.0, 0.0
    except Exception as e:
        print(f"⚠️ Unexpected error in AMap client: {e}")
        return 0.0, 0.0


def batch_get_routes(
    origins: list[tuple[float, float]],
    destinations: list[tuple[float, float]],
) -> list[tuple[float, float]]:
    """
    Get multiple routes in batch (with rate limiting).
    
    Args:
        origins: List of (lng, lat) tuples for origins
        destinations: List of (lng, lat) tuples for destinations
    
    Returns:
        List of (distance_km, duration_min) tuples
    """
    if len(origins) != len(destinations):
        raise ValueError("Origins and destinations must have same length")
    
    results = []
    total = len(origins)
    
    for i, (origin, dest) in enumerate(zip(origins, destinations)):
        if i % 10 == 0:  # ✅ Progress indicator
            print(f"Fetching routes: {i}/{total}...")
        
        dist, time = get_route_distance_time(
            origin_lng=origin[0],
            origin_lat=origin[1],
            dest_lng=dest[0],
            dest_lat=dest[1],
        )
        results.append((dist, time))
    
    return results


def test_api_key() -> bool:
    """
    Test if the configured API key is valid.
    
    Returns:
        True if key works, False otherwise
    """
    try:
        # Test with a simple Hong Kong route
        dist, time = get_route_distance_time(
            origin_lng=114.1694,  # Central
            origin_lat=22.2783,
            dest_lng=114.1753,    # Admiralty
            dest_lat=22.2799,
        )
        return dist > 0 or time > 0
    except AmapConfigError:
        return False
    except Exception:
        return False
