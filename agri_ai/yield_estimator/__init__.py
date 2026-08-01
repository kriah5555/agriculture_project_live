"""
agri_ai.yield_estimator
------------------------
District-level crop yield estimator, ported from the standalone yield_project
prototype (India_All_Districts_Crop_Yield_Master_1997-2024 + Open-Meteo +
irrigation stats). No ML model — a deterministic formula over static
reference tables plus live NDVI from GEE:

    predicted_yield = potential_yield * soil_factor * water_factor * ndvi_factor

Usage:
    from agri_ai.yield_estimator import get_hierarchy, estimate_yield

    result = estimate_yield('Belagavi', 'Rice (Paddy)', soc=0.6, pH=6.8,
                             N=240, P=18, K=120, lat=15.85, lon=74.5)
"""
from .data_loader import (
    load_hierarchy, load_lookup, load_potential_yields,
    load_water_data, load_irrigation_data,
)
from .engine import predict_yield

__all__ = ["get_hierarchy", "estimate_yield"]

_hierarchy  = load_hierarchy()
_lookup     = load_lookup()
_potential  = load_potential_yields()
_water      = load_water_data()
_irrigation = load_irrigation_data()


def get_hierarchy():
    """State -> District -> [crop names], for the cascading dropdowns."""
    return _hierarchy


def estimate_yield(district, crop, soc, pH, N, P, K, lat=None, lon=None):
    return predict_yield(
        district, crop, soc, pH, N, P, K,
        potential=_potential, water_data=_water, irrigation_data=_irrigation, lookup=_lookup,
        lat=lat, lon=lon,
    )