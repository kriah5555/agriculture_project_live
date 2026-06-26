"""
elevation.py
------------
Fetch elevation (metres above sea level) for a lat/lon point.

Primary:  Open-Meteo forecast API  (free, no auth, fast)
Fallback: Google Earth Engine SRTM (requires GEE project permission)
"""

import os
import requests as _req
from dotenv import load_dotenv

load_dotenv()

_GEE_PROJECT = os.environ.get("GEE_PROJECT", "soilmain")
_SRTM        = "USGS/SRTMGL1_003"
_SCALE_M     = 30


def get_elevation(lat: float, lon: float) -> float | None:
    """Return elevation in metres for a given point, or None on failure."""
    # Try Open-Meteo first — fast, no auth
    try:
        r = _req.get(
            "https://api.open-meteo.com/v1/forecast",
            params={"latitude": lat, "longitude": lon, "current_weather": "true"},
            timeout=6,
        )
        r.raise_for_status()
        elev = r.json().get("elevation")
        if elev is not None:
            return round(float(elev), 2)
    except Exception:
        pass

    # Fallback: GEE SRTM
    try:
        import ee
        try:
            ee.data.getInfo("projects/earthengine-public/assets/users")
        except ee.EEException:
            ee.Initialize(project=_GEE_PROJECT)
        point = ee.Geometry.Point([lon, lat])
        srtm  = ee.Image(_SRTM)
        stats = srtm.select("elevation").reduceRegion(
            reducer=ee.Reducer.mean(), geometry=point, scale=_SCALE_M
        ).getInfo()
        val = stats.get("elevation")
        return round(val, 2) if val is not None else None
    except Exception as e:
        print(f"  [elevation] GEE fallback failed for ({lat}, {lon}): {e}")
        return None