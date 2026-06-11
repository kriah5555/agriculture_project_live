"""
agri_ai.soil
------------
Soil property prediction using LightGBM models.

Usage:
    from agri_ai.soil import load_models, predict_for_point, classify_fertility

    lgbm_models, rf_model = load_models()
    preds, env = predict_for_point(lat, lon, lgbm_models, get_weather, get_ndvi, get_elevation, get_soil_texture)
    fertility  = classify_fertility(preds, env, rf_model)
"""

import os
import pickle

from .inference import predict_for_point, classify_fertility, ICAR_RANGES, INFERENCE_ORDER

_MODEL_DIR = os.path.join(os.path.dirname(__file__), "models")

REGRESSION_TARGETS = [
    "ph", "ec", "n", "p", "k", "organic_carbon",
    "s", "fe", "zn", "cu", "b", "mn",
]


def load_models():
    """
    Load all LightGBM soil-chemistry models and the RF fertility classifier
    from agri_ai/soil/models/.

    Returns
    -------
    lgbm_models : dict  {target_name: model}
    rf_model    : RandomForestClassifier or None
    """
    lgbm_models = {}
    for target in REGRESSION_TARGETS:
        path = os.path.join(_MODEL_DIR, f"lgbm_{target}.pkl")
        if os.path.exists(path):
            with open(path, "rb") as f:
                lgbm_models[target] = pickle.load(f)

    rf_model = None
    rf_path = os.path.join(_MODEL_DIR, "rf_fertility.pkl")
    if os.path.exists(rf_path):
        with open(rf_path, "rb") as f:
            rf_model = pickle.load(f)

    return lgbm_models, rf_model


__all__ = [
    "load_models",
    "predict_for_point",
    "classify_fertility",
    "ICAR_RANGES",
    "INFERENCE_ORDER",
]