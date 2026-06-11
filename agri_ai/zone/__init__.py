"""
agri_ai.zone
------------
Agroclimatic zone classification.

Usage:
    from agri_ai.zone import classify_zone, classify_global_climate_zone, CLIMATE_ZONE_METADATA

    # Full lat/lon lookup (India/Karnataka-aware + global fallback):
    zone_name, zone_meta, climate, location = classify_zone(lat, lon)

    # Simple Köppen classifier from known climate values:
    zone = classify_global_climate_zone(temp_c, rainfall_mm, elevation_m)
"""

from .classifier import (
    classify_zone,
    classify_global_climate_zone,
    CLIMATE_ZONE_METADATA,
    KARNATAKA_ZONE_METADATA,
    INDIA_NATIONAL_ZONE_METADATA,
    GLOBAL_ZONE_METADATA,
)

__all__ = [
    "classify_zone",
    "classify_global_climate_zone",
    "CLIMATE_ZONE_METADATA",
    "KARNATAKA_ZONE_METADATA",
    "INDIA_NATIONAL_ZONE_METADATA",
    "GLOBAL_ZONE_METADATA",
]