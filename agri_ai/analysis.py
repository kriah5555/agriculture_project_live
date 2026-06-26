"""
agri_ai/analysis.py
===================
Polygon-level analysis combining zone classification + SAR crop detection.

Public API:
  analyze_polygon(coords, radius_km, season)  → dict
"""

import math
from agri_ai.zone import classify_zone
from agri_ai.gee  import get_sar_timeline


def polygon_centroid(coords):
    """coords: list of [lon, lat]. Returns (lat, lon)."""
    lat = sum(c[1] for c in coords) / len(coords)
    lon = sum(c[0] for c in coords) / len(coords)
    return lat, lon


def polygon_area_ha(coords):
    """Shoelace formula on spherical coords. Returns area in hectares."""
    R = 6371000
    n = len(coords)
    area = 0.0
    for i in range(n):
        j     = (i + 1) % n
        lat1  = math.radians(coords[i][1])
        lat2  = math.radians(coords[j][1])
        dlon  = math.radians(coords[j][0] - coords[i][0])
        area += dlon * (2 + math.sin(lat1) + math.sin(lat2))
    return abs(area * R * R / 2) / 10000


def analyze_polygon(coords, radius_km=2, season='kharif'):
    """
    Full polygon analysis: zone + climate + SAR crop detection.

    coords    : list of [lon, lat] pairs (at least 3)
    radius_km : buffer radius for SAR analysis
    season    : kharif | rabi | zaid | all

    Returns a dict ready to serialize as JSON.
    """
    lat, lon = polygon_centroid(coords)
    area_ha  = polygon_area_ha(coords)

    try:
        zone_name, zone_meta, climate, location = classify_zone(lat, lon)
    except Exception:
        zone_name, zone_meta, climate, location = 'Unknown', {}, {}, {}

    try:
        crop_data = get_sar_timeline(coords, radius_km, season)
    except Exception:
        crop_data = None

    return {
        'status':           'done',
        'centroid':         {'lat': round(lat, 5), 'lon': round(lon, 5)},
        'area_ha':          round(area_ha, 3),
        'zone_name':        zone_name,
        'zone_data':        zone_meta,
        'climate_data':     climate,
        'location':         location,
        'crop_predictions': crop_data,
        'radius_km':        radius_km,
        'season':           season,
    }