import math

CANADIAN_CITIES: dict[str, tuple[float, float]] = {
    "toronto": (43.6532, -79.3832),
    "vancouver": (49.2827, -123.1207),
    "montreal": (45.5019, -73.5674),
    "ottawa": (45.4215, -75.6972),
    "calgary": (51.0447, -114.0719),
    "edmonton": (53.5461, -113.4938),
    "waterloo": (43.4643, -80.5204),
    "kitchener": (43.4516, -80.4925),
    "hamilton": (43.2557, -79.8711),
    "mississauga": (43.5890, -79.6441),
    "brampton": (43.7315, -79.7624),
    "london": (42.9849, -81.2453),
    "kingston": (44.2312, -76.4860),
    "guelph": (43.5448, -80.2482),
    "halifax": (44.6488, -63.5752),
    "victoria": (48.4284, -123.3656),
    "winnipeg": (49.8951, -97.1384),
    "quebec city": (46.8139, -71.2080),
    "saskatoon": (52.1332, -106.6700),
    "regina": (50.4452, -104.6189),
    "fredericton": (45.9636, -66.6431),
    "moncton": (46.0878, -64.7782),
    "st john's": (47.5615, -52.7126),
}


def coordinates_for_location(location: str | None) -> tuple[float, float] | None:
    normalized = (location or "").casefold()
    return next(
        (coordinates for city, coordinates in CANADIAN_CITIES.items() if city in normalized),
        None,
    )


def distance_km(first: tuple[float, float], second: tuple[float, float]) -> float:
    lat1, lon1, lat2, lon2 = map(math.radians, (*first, *second))
    delta_lat = lat2 - lat1
    delta_lon = lon2 - lon1
    value = (
        math.sin(delta_lat / 2) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin(delta_lon / 2) ** 2
    )
    return 6371.0 * 2 * math.atan2(math.sqrt(value), math.sqrt(1 - value))
