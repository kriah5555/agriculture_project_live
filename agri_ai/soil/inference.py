"""
map_utils.py
------------
Inference helpers for the SoilVision API.

Supports both model formats:
  - v1: bare LightGBM model (has .predict directly)
  - v2: dict bundle  {lgbm, et, ridge, feature_cols, has_state, use_log,
                       state_means, global_mean_y, icar_range}

Inference order for v2 models follows the cross-target dependency chain:
  ph -> ec -> organic_carbon -> n -> p -> k -> s -> fe -> zn -> cu -> b -> mn

All predictions are post-clipped to ICAR agronomic ranges.
"""

import math
import numpy as np
from datetime import datetime, timedelta

# ---------------------------------------------------------------------------
# ICAR agronomic clip ranges  (must stay in sync with preprocessing.py / train.py)
# ---------------------------------------------------------------------------
ICAR_RANGES = {
    "ph":             (4.5,  9.0),
    "n":              (0.0,  600.0),
    "p":              (0.0,  50.0),
    "k":              (0.0,  500.0),
    "ec":             (0.0,  4.0),
    "organic_carbon": (0.0,  3.0),
    "s":              (0.0,  60.0),
    "fe":             (0.0,  100.0),
    "zn":             (0.0,  20.0),
    "cu":             (0.0,  15.0),
    "b":              (0.0,  5.0),
    "mn":             (0.0,  50.0),
}

# Fertility score weights (must mirror train.py)
FERTILITY_WEIGHTS_INFER = {
    "n": 0.25, "p": 0.20, "k": 0.20, "organic_carbon": 0.20,
    "ndvi": 0.10, "rainfall": 0.05,
}

# ---------------------------------------------------------------------------
# Cross-target dependency order  (must match train.py)
# ---------------------------------------------------------------------------
INFERENCE_ORDER = ["ph", "ec", "organic_carbon", "n", "p", "k",
                   "s", "fe", "zn", "cu", "b", "mn"]


# ---------------------------------------------------------------------------
# Feature engineering  (must exactly mirror train_model_v2.py)
# ---------------------------------------------------------------------------
def _engineer_features(base: dict) -> dict:
    """
    Expand the 9 base features into the full engineered feature set.
    base keys: lat, lon, ndvi, temperature, rainfall, elevation,
                clay_pct, sand_pct, silt_pct
    """
    d = dict(base)
    lat, lon      = d["lat"], d["lon"]
    ndvi          = d["ndvi"]
    temperature   = d["temperature"]
    rainfall      = d["rainfall"]
    elevation     = d["elevation"]
    clay_pct      = d["clay_pct"]
    sand_pct      = d["sand_pct"]
    silt_pct      = d["silt_pct"]

    d["lat2"]        = lat ** 2
    d["lon2"]        = lon ** 2
    d["lat_lon"]     = lat * lon
    d["ndvi_rain"]   = ndvi * rainfall
    d["temp_elev"]   = temperature * elevation
    d["rain_elev"]   = rainfall * elevation
    d["ndvi_temp"]   = ndvi * temperature
    d["clay_sand"]   = clay_pct / (sand_pct + 1)
    d["silt_clay"]   = silt_pct / (clay_pct + 1)
    d["texture_sum"] = clay_pct + silt_pct
    d["sin_lat"]     = math.sin(math.radians(lat))
    d["cos_lon"]     = math.cos(math.radians(lon))
    return d


# ---------------------------------------------------------------------------
# Single-target prediction (handles both v1 and v2 bundles)
# ---------------------------------------------------------------------------
def _predict_one(model_or_bundle, feat_dict: dict, target: str = "") -> float:
    """
    Run inference for one target, then apply ICAR range clip.
    - v1: model_or_bundle is a bare LightGBM.
    - v2: model_or_bundle is the dict bundle.
    """
    if isinstance(model_or_bundle, dict):
        bundle       = model_or_bundle
        feature_cols = bundle["feature_cols"]
        has_state    = bundle["has_state"]
        use_log      = bundle["use_log"]
        global_mean  = bundle["global_mean_y"]

        # Build feature vector from feature_cols (base + oof cross-target cols)
        row = [feat_dict.get(col, 0.0) for col in feature_cols]

        # state_enc was appended via np.hstack AFTER feature_cols in training —
        # replicate that exactly: use global_mean as fallback (no state at inference)
        if has_state:
            row.append(global_mean)

        X = np.array(row, dtype=np.float64).reshape(1, -1)

        lgb_pred  = bundle["lgbm"].predict(X)[0]
        et_pred   = bundle["et"].predict(X)[0]
        meta_X    = np.array([[lgb_pred, et_pred]])
        stacked   = bundle["ridge"].predict(meta_X)[0]

        value = float(np.expm1(stacked)) if use_log else float(stacked)
    else:
        # v1 bare LightGBM — keep original behaviour
        base_order = ["lat", "lon", "ndvi", "temperature", "rainfall",
                      "elevation", "clay_pct", "sand_pct", "silt_pct"]
        row = [feat_dict.get(k, 0.0) for k in base_order]
        raw = model_or_bundle.predict([row])[0]
        value = float(np.expm1(raw))

    # Post-prediction ICAR clip — always applied after back-transform
    if target and target in ICAR_RANGES:
        lo, hi = ICAR_RANGES[target]
        value  = float(np.clip(value, lo, hi))

    return value


# ---------------------------------------------------------------------------
# Main inference function
# ---------------------------------------------------------------------------
def predict_for_point(lat, lon, lgbm_models,
                      weather_fn, ndvi_fn, elev_fn, texture_fn):
    """
    Fetch environmental features and run all models for one lat/lon point.
    Returns (preds_dict, env_features_dict).
    """
    # -- Fetch environmental inputs ----------------------------------------
    try:
        t, r        = weather_fn(lat, lon)
        temperature = t if t is not None else 28.0
        rainfall    = r if r is not None else 950.0
    except Exception:
        temperature, rainfall = 28.0, 950.0

    try:
        end_dt   = datetime.now() - timedelta(days=7)
        start_dt = end_dt - timedelta(days=365)
        nv       = ndvi_fn(lat, lon,
                           start_dt.strftime("%Y-%m-%d"),
                           end_dt.strftime("%Y-%m-%d"))
        ndvi_val = nv if nv is not None else 0.55
    except Exception:
        ndvi_val = 0.55

    try:
        e         = elev_fn(lat, lon)
        elevation = e if e is not None else 200.0
    except Exception:
        elevation = 200.0

    try:
        tex      = texture_fn(lat, lon)
        clay_pct = tex.get("clay_pct") or 30.0
        sand_pct = tex.get("sand_pct") or 40.0
        silt_pct = tex.get("silt_pct") or 30.0
    except Exception:
        clay_pct, sand_pct, silt_pct = 30.0, 40.0, 30.0

    env_features = {
        "ndvi":           round(ndvi_val, 4),
        "temperature_c":  round(temperature, 1),
        "rainfall_mm":    round(rainfall, 1),
        "elevation_m":    round(elevation, 1),
        "clay_pct":       round(clay_pct, 1),
        "sand_pct":       round(sand_pct, 1),
        "silt_pct":       round(silt_pct, 1),
    }

    # -- Build full feature dict with engineering --------------------------
    base = {
        "lat":         lat,
        "lon":         lon,
        "ndvi":        ndvi_val,
        "temperature": temperature,
        "rainfall":    rainfall,
        "elevation":   elevation,
        "clay_pct":    clay_pct,
        "sand_pct":    sand_pct,
        "silt_pct":    silt_pct,
    }
    feat_dict = _engineer_features(base)

    # -- Run models in dependency order ------------------------------------
    preds = {}
    for target in INFERENCE_ORDER:
        model = lgbm_models.get(target)
        if model is None:
            preds[target] = None
            continue
        try:
            val = _predict_one(model, feat_dict, target)  # ICAR clip inside
            preds[target] = round(val, 3)
            # Store as cross-target feature for subsequent models
            feat_dict[f"oof_{target}"] = val
        except Exception as exc:
            print(f"  [warn] prediction failed for {target}: {exc}")
            preds[target] = None

    return preds, env_features


# ---------------------------------------------------------------------------
# Fertility Classification
# ---------------------------------------------------------------------------
def classify_fertility(preds, env_features, rf_model):
    """
    Compute ICAR-normalised fertility score [0-100] then classify via RF.
    Feature order must match CLASSIFICATION_FEATURES in train.py.
    """
    # Score-based label as fallback
    score  = 0.0
    merged = {
        **preds,
        "ndvi":    env_features.get("ndvi",        0.55),
        "rainfall": env_features.get("rainfall_mm", 950.0),
    }
    for col, weight in FERTILITY_WEIGHTS_INFER.items():
        val = merged.get(col)
        if val is None:
            continue
        lo, hi = ICAR_RANGES.get(col, (0, 1))
        rng    = hi - lo
        norm   = float(np.clip((val - lo) / rng, 0, 1)) if rng > 0 else 0.0
        score += weight * norm
    fertility_score = round(float(np.clip(score * 100, 0, 100)), 2)

    # RF classifier takes priority when available
    try:
        feat_list = [
            preds.get("ph",             7.0),
            preds.get("n",              280.0),
            preds.get("p",              16.0),
            preds.get("k",              200.0),
            preds.get("organic_carbon", 0.75),
            preds.get("s",              12.0),
            preds.get("fe",             8.0),
            preds.get("zn",             1.2),
            env_features.get("ndvi",          0.55),
            env_features.get("rainfall_mm",   950.0),
            env_features.get("elevation_m",   200.0),
            env_features.get("clay_pct",       30.0),
            env_features.get("sand_pct",       40.0),
            env_features.get("silt_pct",       30.0),
        ]
        feat_list = [f if f is not None else 0.0 for f in feat_list]
        result    = rf_model.predict([feat_list])[0]
        label_map = {"low": "Low", "medium": "Medium", "high": "High"}
        return label_map.get(str(result).lower(), str(result).capitalize())
    except Exception as e:
        print(f"Fertility classification error: {e}")
        # Fall back to score-based label
        if fertility_score < 33.33:
            return "Low"
        elif fertility_score < 66.67:
            return "Medium"
        return "High"

