"""
ndvi.py
-------
Module to fetch mean NDVI values from Google Earth Engine
using Sentinel-2 Surface Reflectance imagery.
"""

import os
import ee
from dotenv import load_dotenv

load_dotenv()

# ── Configuration ─────────────────────────────────────────────────────────────
PROJECT_ID      = os.environ.get("GEE_PROJECT", "soilmain")
COLLECTION      = "COPERNICUS/S2_SR_HARMONIZED"
CLOUD_THRESHOLD = 20 # Max allowed cloud percentage
SCALE_METERS    = 10 # Sentinel-2 native resolution for B4/B8


def _initialize_ee():
    """Initialize Earth Engine if it hasn't been initialized yet."""
    try:
        ee.data.getInfo("projects/earthengine-public/assets/users")
    except ee.EEException:
        # Not initialized — do it now
        ee.Initialize(project=PROJECT_ID)


def get_ndvi(lat: float, lon: float, start_date: str, end_date: str):
    """
    Fetch the mean NDVI for a given location and date range using Sentinel-2.

    Parameters
    ----------
    lat        : float  — Latitude of the point (e.g. 17.385)
    lon        : float  — Longitude of the point (e.g. 78.486)
    start_date : str    — Start date in 'YYYY-MM-DD' format
    end_date   : str    — End date in 'YYYY-MM-DD' format

    Returns
    -------
    float or None — Mean NDVI value, or None if data is unavailable.
    """
    try:
        _initialize_ee()

        # Define the point geometry
        point = ee.Geometry.Point([lon, lat])

        # Filter Sentinel-2 collection
        collection = (
            ee.ImageCollection(COLLECTION)
            .filterBounds(point)
            .filterDate(start_date, end_date)
            .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", CLOUD_THRESHOLD))
        )

        # Check if any images exist
        count = collection.size().getInfo()
        if count == 0:
            print(f"  [NDVI] No cloud-free images found for ({lat}, {lon}) "
                  f"between {start_date} and {end_date}.")
            return None

        # Add NDVI band and compute temporal mean
        def add_ndvi(image):
            ndvi = image.normalizedDifference(["B8", "B4"]).rename("NDVI")
            return image.addBands(ndvi)

        mean_ndvi_image = collection.map(add_ndvi).select("NDVI").mean()

        # Sample the value at the point
        stats = mean_ndvi_image.reduceRegion(
            reducer=ee.Reducer.mean(),
            geometry=point,
            scale=SCALE_METERS
        ).getInfo()

        ndvi_value = stats.get("NDVI")
        return round(ndvi_value, 6) if ndvi_value is not None else None

    except ee.EEException as e:
        print(f"  [NDVI] Earth Engine error for ({lat}, {lon}): {e}")
        return None
    except Exception as e:
        print(f"  [NDVI] Unexpected error for ({lat}, {lon}): {e}")
        return None
