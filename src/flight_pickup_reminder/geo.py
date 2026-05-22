from math import asin, cos, radians, sin, sqrt
from typing import Any, Optional


EARTH_RADIUS_METERS = 6371000


def distance_meters(lat1: Any, lon1: Any, lat2: Any, lon2: Any) -> Optional[float]:
    try:
        phi1 = radians(float(lat1))
        phi2 = radians(float(lat2))
        delta_phi = radians(float(lat2) - float(lat1))
        delta_lambda = radians(float(lon2) - float(lon1))
    except (TypeError, ValueError):
        return None
    a = sin(delta_phi / 2) ** 2 + cos(phi1) * cos(phi2) * sin(delta_lambda / 2) ** 2
    return EARTH_RADIUS_METERS * 2 * asin(sqrt(a))
