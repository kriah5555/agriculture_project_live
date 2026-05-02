"""
predict.py
----------
Standalone inference script for ICAR Soil Intelligence.

Usage:
    python ml_pipeline/predict.py --lat 12.97 --lon 77.59
    python ml_pipeline/predict.py --lat 12.97 --lon 77.59 --state karnataka
    python ml_pipeline/predict.py --batch data/processed/points.csv

Batch CSV format (columns: lat, lon [, state]):
    lat,lon,state
    12.97,77.59,karnataka
    28.61,77.20,delhi

Design rules:
  - Feature engineering EXACTLY mirrors train.py and map_utils.py
  - ICAR range clip applied after every prediction (same ranges as preprocessing.py)
  - log1p / expm1 handled transparently from bundle metadata
  - Fertility score normalised with ICAR ranges (not data-driven min/max)
  - All outputs in real agricultural units (not percentages)
"""

import os
import sys
import math
import pickle
import numpy as np
import pandas as pd
from typing import Optional

# ── Paths ─────────────────────────────────────────────────────────────────────
ROOT      = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODEL_DIR = os.path.join(ROOT, "models")

# ── ICAR post-prediction clip ranges ─────────────────────────────────────────
# Keep in sync with preprocessing.py::ICAR_RANGES and train.py::ICAR_RANGES
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

# Inference order: earlier predictions feed into later targets as cross-features
INFERENCE_ORDER = [
    "ph", "ec", "organic_carbon", "n", "p", "k",
    "s", "fe", "zn", "cu", "b", "mn",
]

# Fertility score weights (must mirror train.py::FERTILITY_WEIGHTS)
FERTILITY_WEIGHTS = {
    "n": 0.25, "p": 0.20, "k": 0.20, "organic_carbon": 0.20,
    "ndvi": 0.10, "rainfall": 0.05,
}

# Units for display
UNITS = {
    "ph": "", "ec": "dS/m", "n": "kg/ha", "p": "kg/ha", "k": "kg/ha",
    "organic_carbon": "%", "s": "ppm", "fe": "ppm", "zn": "ppm",
    "cu": "ppm", "b": "ppm", "mn": "ppm",
}


# ── Feature engineering (must exactly mirror train.py / map_utils.py) ─────────
def _engineer_features(base: dict) -> dict:
    """
    Expand 9 base features into the full engineered feature set.
    base keys: lat, lon, ndvi, temperature, rainfall, elevation,
               clay_pct, sand_pct, silt_pct
    """
    d = dict(base)
    lat, lon    = d["lat"], d["lon"]
    ndvi        = d["ndvi"]
    temperature = d["temperature"]
    rainfall    = d["rainfall"]
    elevation   = d["elevation"]
    clay_pct    = d["clay_pct"]
    sand_pct    = d["sand_pct"]
    silt_pct    = d["silt_pct"]

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


# ── Model loader ──────────────────────────────────────────────────────────────
_MODEL_CACHE: dict = {}

def load_models(model_dir: str = MODEL_DIR) -> dict:
    """Load all lgbm_*.pkl bundles from the model directory."""
    global _MODEL_CACHE
    if _MODEL_CACHE:
        return _MODEL_CACHE

    models = {}
    for target in INFERENCE_ORDER:
        path = os.path.join(model_dir, f"lgbm_{target}.pkl")
        if not os.path.exists(path):
            print(f"  [WARN] Model not found: {path}")
            continue
        with open(path, "rb") as f:
            models[target] = pickle.load(f)
        print(f"  [load] lgbm_{target}.pkl")

    fertility_path = os.path.join(model_dir, "rf_fertility.pkl")
    if os.path.exists(fertility_path):
        with open(fertility_path, "rb") as f:
            models["rf_fertility"] = pickle.load(f)
        print(f"  [load] rf_fertility.pkl")
    else:
        print(f"  [WARN] rf_fertility.pkl not found")

    _MODEL_CACHE = models
    return models


# ── Single-target prediction ──────────────────────────────────────────────────
def _predict_one(bundle, feat_dict: dict, target: str) -> float:
    """
    Run one bundle prediction and apply ICAR clip.
    Handles both v2 stacked bundles and bare LightGBM models.
    """
    if isinstance(bundle, dict):
        feature_cols = bundle["feature_cols"]
        has_state    = bundle.get("has_state", False)
        use_log      = bundle.get("use_log", False)
        global_mean  = bundle.get("global_mean_y", 0.0)

        row = [feat_dict.get(col, 0.0) for col in feature_cols]
        if has_state:
            # Use global mean (no state at inference for API calls)
            row.append(global_mean)

        X         = np.array(row, dtype=np.float64).reshape(1, -1)
        lgb_pred  = bundle["lgbm"].predict(X)[0]
        et_pred   = bundle["et"].predict(X)[0]
        stacked   = bundle["ridge"].predict(np.array([[lgb_pred, et_pred]]))[0]

        value = float(np.expm1(stacked)) if use_log else float(stacked)
    else:
        # Bare LightGBM (v1 compatibility)
        base_order = ["lat", "lon", "ndvi", "temperature", "rainfall",
                      "elevation", "clay_pct", "sand_pct", "silt_pct"]
        row   = [feat_dict.get(k, 0.0) for k in base_order]
        value = float(np.expm1(bundle.predict([row])[0]))

    # ICAR clip (always applied after back-transform)
    if target in ICAR_RANGES:
        lo, hi = ICAR_RANGES[target]
        value  = float(np.clip(value, lo, hi))

    return value


# ── Fertility score ───────────────────────────────────────────────────────────
def _fertility_score(preds: dict, env: dict) -> float:
    """
    Compute normalised fertility score ∈ [0, 100] using ICAR ranges.
    """
    score = 0.0
    merged = {**preds, "ndvi": env.get("ndvi", 0.5), "rainfall": env.get("rainfall", 950.0)}
    for col, weight in FERTILITY_WEIGHTS.items():
        val = merged.get(col)
        if val is None:
            continue
        lo, hi = ICAR_RANGES.get(col, (0, 1))
        rng    = hi - lo
        norm   = float(np.clip((val - lo) / rng, 0, 1)) if rng > 0 else 0.0
        score += weight * norm
    return round(float(np.clip(score * 100, 0, 100)), 2)


def _fertility_label(score: float) -> str:
    if score < 33.33:
        return "Low"
    elif score < 66.67:
        return "Medium"
    return "High"


# ── RF fertility classifier ───────────────────────────────────────────────────
def _classify_fertility_rf(preds: dict, env: dict, rf_model) -> str:
    """Use the trained Random Forest if available."""
    CLASSIFICATION_FEATURES = [
        "ph", "n", "p", "k", "organic_carbon",
        "s", "fe", "zn", "ndvi", "rainfall",
        "elevation", "clay_pct", "sand_pct", "silt_pct",
    ]
    try:
        feat = [
            preds.get("ph",             7.0),
            preds.get("n",              280.0),
            preds.get("p",              16.0),
            preds.get("k",              200.0),
            preds.get("organic_carbon", 0.75),
            preds.get("s",              12.0),
            preds.get("fe",             8.0),
            preds.get("zn",             1.2),
            env.get("ndvi",          0.5),
            env.get("rainfall",      950.0),
            env.get("elevation",     300.0),
            env.get("clay_pct",       30.0),
            env.get("sand_pct",       40.0),
            env.get("silt_pct",       30.0),
        ]
        feat  = [f if f is not None else 0.0 for f in feat]
        label = str(rf_model.predict([feat])[0])
        return {"low": "Low", "medium": "Medium", "high": "High"}.get(
            label.lower(), label.capitalize()
        )
    except Exception as e:
        print(f"  [WARN] RF fertility failed: {e}")
        return None


# ── Main prediction function ──────────────────────────────────────────────────
def predict_point(
    lat: float,
    lon: float,
    models: dict,
    state: Optional[str] = None,
    # Environmental features — if not supplied, sensible defaults are used
    # (in production, these come from GEE / weather APIs via map_utils.py)
    ndvi:        float = 0.55,
    temperature: float = 28.0,
    rainfall:    float = 950.0,
    elevation:   float = 200.0,
    clay_pct:    float = 30.0,
    sand_pct:    float = 40.0,
    silt_pct:    float = 30.0,
) -> dict:
    """
    Run the full soil parameter prediction for one (lat, lon) point.
    Returns a dict with keys: predictions, fertility_score, fertility_label,
                               env_features, units.
    """
    env = {
        "ndvi":        ndvi,
        "temperature": temperature,
        "rainfall":    rainfall,
        "elevation":   elevation,
        "clay_pct":    clay_pct,
        "sand_pct":    sand_pct,
        "silt_pct":    silt_pct,
    }

    base = {"lat": lat, "lon": lon, **env}
    feat_dict = _engineer_features(base)

    preds = {}
    for target in INFERENCE_ORDER:
        bundle = models.get(target)
        if bundle is None:
            preds[target] = None
            continue
        try:
            val = _predict_one(bundle, feat_dict, target)
            preds[target] = round(val, 3)
            # Inject as cross-target feature for subsequent models
            feat_dict[f"oof_{target}"] = val
        except Exception as exc:
            print(f"  [WARN] Prediction failed for {target}: {exc}")
            preds[target] = None

    # Fertility
    score = _fertility_score(preds, env)
    label = _fertility_label(score)
    rf    = models.get("rf_fertility")
    if rf is not None:
        rf_label = _classify_fertility_rf(preds, env, rf)
        if rf_label:
            label = rf_label

    return {
        "predictions":     preds,
        "fertility_score": score,
        "fertility_label": label,
        "env_features":    {k: round(v, 3) for k, v in env.items()},
        "units":           UNITS,
    }


# ── Pretty print ──────────────────────────────────────────────────────────────
def print_results(result: dict, lat: float, lon: float) -> None:
    preds  = result["predictions"]
    units  = result["units"]
    env    = result["env_features"]
    score  = result["fertility_score"]
    label  = result["fertility_label"]

    print(f"\n{'='*60}")
    print(f"  SOIL PREDICTION  —  lat={lat:.4f}  lon={lon:.4f}")
    print(f"{'='*60}")
    print(f"  {'Parameter':<22} {'Value':>10}  Unit")
    print(f"  {'-'*22} {'-'*10}  {'-'*8}")
    for param in INFERENCE_ORDER:
        val = preds.get(param)
        unit = units.get(param, "")
        val_str = f"{val:.3f}" if val is not None else "N/A"
        print(f"  {param:<22} {val_str:>10}  {unit}")

    print(f"\n  Fertility Score : {score:.1f}/100")
    print(f"  Fertility Class : {label}")

    print(f"\n  Environmental Inputs:")
    for k, v in env.items():
        print(f"    {k:<18} {v}")
    print(f"{'='*60}\n")


# ── Batch prediction ──────────────────────────────────────────────────────────
def predict_batch(input_csv: str, output_csv: Optional[str] = None) -> pd.DataFrame:
    """
    Predict for all rows in a CSV file (columns: lat, lon [, state]).
    Writes output CSV alongside the input if output_csv not specified.
    """
    df = pd.read_csv(input_csv)
    models = load_models()

    rows = []
    for _, row in df.iterrows():
        r = predict_point(
            lat=float(row["lat"]),
            lon=float(row["lon"]),
            models=models,
            state=str(row.get("state", "")) or None,
        )
        record = {"lat": row["lat"], "lon": row["lon"]}
        record.update(r["predictions"])
        record["fertility_score"] = r["fertility_score"]
        record["fertility_label"] = r["fertility_label"]
        rows.append(record)

    out_df = pd.DataFrame(rows)
    if output_csv is None:
        base, _ = os.path.splitext(input_csv)
        output_csv = base + "_predictions.csv"
    out_df.to_csv(output_csv, index=False)
    print(f"Batch predictions saved: {output_csv}")
    return out_df


# ── CLI ───────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser(
        description="Predict soil parameters for a lat/lon point."
    )
    ap.add_argument("--lat",    type=float, help="Latitude")
    ap.add_argument("--lon",    type=float, help="Longitude")
    ap.add_argument("--state",  type=str,   default=None, help="State name (optional)")
    ap.add_argument("--batch",  type=str,   default=None,
                    help="Path to CSV with lat/lon columns for batch prediction")
    ap.add_argument("--output", type=str,   default=None,
                    help="Output CSV path for batch mode")
    args = ap.parse_args()

    if args.batch:
        predict_batch(args.batch, args.output)
    elif args.lat is not None and args.lon is not None:
        print("Loading models...")
        models = load_models()
        result = predict_point(args.lat, args.lon, models, state=args.state)
        print_results(result, args.lat, args.lon)
    else:
        ap.print_help()
        sys.exit(1)
