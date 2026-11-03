"""Distance / delivery-range helpers (pure Python twin of routers/shops._distance_expr)."""
import math

EARTH_RADIUS_KM = 6371


def haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    a = math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(math.radians(lng2 - lng1) / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.asin(min(1.0, math.sqrt(a)))


def delivery_range_problem(shop, lat: float | None, lng: float | None) -> str | None:
    """Why `shop` can't deliver to (lat, lng), or None if it can."""
    if lat is None or lng is None:
        return (
            "This address has no map location yet. Edit it and tap \u201cUse my current location\u201d "
            "so we can check which shops deliver there."
        )
    if shop.latitude is None or shop.longitude is None:
        return f'"{shop.name}" hasn\u2019t set its location, so it can\u2019t take delivery orders yet.'
    radius = float(shop.delivery_radius_km)
    km = haversine_km(lat, lng, shop.latitude, shop.longitude)
    if km > radius:
        return (
            f'"{shop.name}" delivers within {radius:g} km and this address is {km:.1f} km away. '
            "Choose another address or pick it up from the shop."
        )
    return None
