"""
retrain.py
----------
Incremental / on-demand retraining pipeline.

Flow:
  1. Load the base enriched dataset (final_dataset_enriched.csv)
  2. Load live sensor data (india_soil_live.csv) if it exists
  3. Enrich live rows with NDVI, weather, elevation, soil texture (via GEE / APIs)
  4. Merge live data into the base dataset and save a new versioned snapshot
  5. Retrain all LightGBM regression models + RF fertility classifier
  6. Write a retrain log (models/retrain_log.json)

Usage:
    python retrain.py                  # Retrain on all available data
    python retrain.py --skip-enrich    # Skip API enrichment (use raw sensor values as-is)
    python retrain.py --dry-run        # Show what would happen without retraining

Called by the Django API endpoint POST /api/retrain/
"""

import os
import sys
import json
import pickle
import warnings
import argparse
import numpy as np
import pandas as pd
import lightgbm as lgb
import optuna
from datetime import datetime
from sklearn.ensemble import ExtraTreesRegressor, RandomForestClassifier
from sklearn.linear_model import Ridge
from sklearn.model_selection import KFold
from sklearn.metrics import (
    mean_absolute_error, mean_squared_error, r2_score, accuracy_score
)

warnings.filterwarnings("ignore")
optuna.logging.set_verbosity(optuna.logging.WARNING)

# ── Paths ─────────────────────────────────────────────────────────────────────
ROOT          = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# Canonical ICAR-converted dataset (output of preprocessing.py)
BASE_CSV      = os.path.join(ROOT, "data", "processed", "final_cleaned_dataset.csv")
FALLBACK_CSV  = os.path.join(ROOT, "data", "processed", "final_cleaned_dataset.csv")  # same file
LIVE_CSV      = os.path.join(ROOT, "data", "processed", "india_soil_live.csv")
MERGED_DIR    = os.path.join(ROOT, "data", "processed")
MODEL_DIR     = os.path.join(ROOT, "models")
LOG_PATH      = os.path.join(MODEL_DIR, "retrain_log.json")
BEST_PARAMS_JSON = os.path.join(MODEL_DIR, "best_hyperparams.json")

os.makedirs(MODEL_DIR, exist_ok=True)
os.makedirs(MERGED_DIR, exist_ok=True)


# ── Model config (mirrors train.py) ───────────────────────────────────────────
RANDOM_SEED   = 42
N_FOLDS       = 5
OPTUNA_TRIALS = 30   # Fewer trials for speed during incremental retraining

# ICAR agronomic clip ranges — MUST stay in sync with preprocessing.py & train.py
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

# log1p ONLY for right-skewed micronutrients (ppm)
# NEVER log-transform ph, n, p, k, organic_carbon, ec
LOG_TARGETS = {"fe", "s", "mn", "cu", "b", "zn"}

# Pre-tuned defaults used in fast mode when no cached Optuna params exist
FAST_DEFAULT_PARAMS = {
    "learning_rate":     0.05,
    "num_leaves":        40,
    "min_child_samples": 15,
    "subsample":         0.8,
    "colsample_bytree":  0.8,
    "reg_alpha":         0.1,
    "reg_lambda":        0.1,
}

BASE_FEATURES = [
    "lat", "lon", "ndvi", "temperature", "rainfall",
    "elevation", "clay_pct", "sand_pct", "silt_pct",
]

REGRESSION_TARGETS = [
    "ph", "ec", "organic_carbon", "n", "p", "k",
    "s", "fe", "zn", "cu", "b", "mn"
]

CLASSIFICATION_FEATURES = [
    "ph", "n", "p", "k", "organic_carbon",
    "s", "fe", "zn", "ndvi", "rainfall",
    "elevation", "clay_pct", "sand_pct", "silt_pct"
]

FERTILITY_WEIGHTS = {
    "n": 0.25, "p": 0.20, "k": 0.20, "organic_carbon": 0.20,
    "ndvi": 0.10, "rainfall": 0.05,
}

CROSS_TARGET_MAP = {
    "n":              ["ph", "ec", "organic_carbon"],
    "p":              ["ph", "ec", "organic_carbon", "n"],
    "k":              ["ph", "ec", "n", "p"],
    "organic_carbon": ["ph", "ndvi", "rainfall"],
    "s":              ["ph", "organic_carbon"],
    "fe":             ["ph", "organic_carbon"],
    "zn":             ["ph", "fe"],
    "cu":             ["ph", "organic_carbon"],
    "b":              ["ph", "rainfall"],
    "mn":             ["ph", "fe", "zn"],
}


# ── Cached hyperparameter helpers ─────────────────────────────────────────────

def _save_best_params(target: str, params: dict):
    """Persist the best Optuna params for *target* to the JSON cache."""
    all_params = {}
    if os.path.exists(BEST_PARAMS_JSON):
        try:
            with open(BEST_PARAMS_JSON) as f:
                all_params = json.load(f)
        except Exception:
            pass
    tunable_keys = ["learning_rate", "num_leaves", "min_child_samples",
                    "subsample", "colsample_bytree", "reg_alpha", "reg_lambda"]
    all_params[target] = {k: params[k] for k in tunable_keys if k in params}
    with open(BEST_PARAMS_JSON, "w") as f:
        json.dump(all_params, f, indent=2)


def _load_best_params(target: str) -> dict:
    """Return cached best params for *target*, falling back to FAST_DEFAULT_PARAMS."""
    if os.path.exists(BEST_PARAMS_JSON):
        try:
            with open(BEST_PARAMS_JSON) as f:
                all_params = json.load(f)
            if target in all_params:
                return dict(all_params[target])
        except Exception:
            pass
    return dict(FAST_DEFAULT_PARAMS)


# ── Feature engineering ───────────────────────────────────────────────────────

def engineer_features(df: pd.DataFrame) -> pd.DataFrame:
    d = df.copy()
    d["lat2"]       = d["lat"] ** 2
    d["lon2"]       = d["lon"] ** 2
    d["lat_lon"]    = d["lat"] * d["lon"]
    d["ndvi_rain"]  = d["ndvi"] * d["rainfall"]
    d["temp_elev"]  = d["temperature"] * d["elevation"]
    d["rain_elev"]  = d["rainfall"] * d["elevation"]
    d["ndvi_temp"]  = d["ndvi"] * d["temperature"]
    d["clay_sand"]  = d["clay_pct"] / (d["sand_pct"] + 1)
    d["silt_clay"]  = d["silt_pct"] / (d["clay_pct"] + 1)
    d["texture_sum"]= d["clay_pct"] + d["silt_pct"]
    d["sin_lat"]    = np.sin(np.deg2rad(d["lat"]))
    d["cos_lon"]    = np.cos(np.deg2rad(d["lon"]))
    return d


# ── Enrich a live-data row with satellite / API features ─────────────────────

def enrich_live_row(row: dict) -> dict:
    """
    Given a dict with at least lat/lon (and optionally some soil params),
    fetch missing environmental features via the same APIs used in production.
    Returns an enriched dict ready to be appended to the training set.
    """
    sys.path.insert(0, os.path.join(ROOT, "ml_pipeline"))

    lat, lon = float(row["lat"]), float(row["lon"])

    # Weather
    try:
        import weather as weather_mod
        t, r = weather_mod.get_weather(lat, lon)
        row.setdefault("temperature", t if t else 28.0)
        row.setdefault("rainfall",    r if r else 950.0)
    except Exception:
        row.setdefault("temperature", 28.0)
        row.setdefault("rainfall",    950.0)

    # NDVI
    try:
        import ndvi as ndvi_mod
        from datetime import timedelta
        end_dt   = datetime.now() - timedelta(days=7)
        start_dt = end_dt - timedelta(days=365)
        nv = ndvi_mod.get_ndvi(lat, lon,
                               start_dt.strftime("%Y-%m-%d"),
                               end_dt.strftime("%Y-%m-%d"))
        row.setdefault("ndvi", nv if nv else 0.55)
    except Exception:
        row.setdefault("ndvi", 0.55)

    # Elevation
    try:
        import add_elevation_to_dataset as elev_mod
        elev_mod.init_gee()
        e = elev_mod.get_elevation(lat, lon)
        row.setdefault("elevation", e if e else 200.0)
    except Exception:
        row.setdefault("elevation", 200.0)

    # Soil texture
    try:
        import add_soilgrids_to_dataset as tex_mod
        tex = tex_mod.get_soil_texture(lat, lon)
        row.setdefault("clay_pct", tex.get("clay_pct") or 30.0)
        row.setdefault("sand_pct", tex.get("sand_pct") or 40.0)
        row.setdefault("silt_pct", tex.get("silt_pct") or 30.0)
    except Exception:
        row.setdefault("clay_pct", 30.0)
        row.setdefault("sand_pct", 40.0)
        row.setdefault("silt_pct", 30.0)

    return row


# ── Merge live data into base dataset ────────────────────────────────────────

def load_and_merge(skip_enrich: bool = False) -> pd.DataFrame:
    """Load base + live CSVs, enrich live rows, return merged DataFrame."""
    csv_path = BASE_CSV if os.path.exists(BASE_CSV) else FALLBACK_CSV
    print(f"[retrain] Base dataset : {csv_path}")
    df_base = pd.read_csv(csv_path)
    print(f"           Rows        : {len(df_base)}")

    if not os.path.exists(LIVE_CSV):
        print("[retrain] No live data found — retraining on base dataset only.")
        return df_base

    df_live = pd.read_csv(LIVE_CSV)
    # Drop rows that have no lat/lon
    df_live = df_live.dropna(subset=["lat", "lon"]).reset_index(drop=True)
    print(f"[retrain] Live data    : {LIVE_CSV}  ({len(df_live)} rows)")

    if not skip_enrich:
        print("[retrain] Enriching live rows with satellite data...")
        enriched_rows = []
        for _, row in df_live.iterrows():
            enriched = enrich_live_row(row.to_dict())
            enriched_rows.append(enriched)
        df_live = pd.DataFrame(enriched_rows)

    # Remove timestamp column (not a model feature)
    df_live = df_live.drop(columns=["timestamp"], errors="ignore")

    # Align columns — only keep columns present in base
    shared_cols = [c for c in df_base.columns if c in df_live.columns]
    df_live_aligned = df_live[shared_cols]

    df_merged = pd.concat([df_base, df_live_aligned], ignore_index=True)
    print(f"[retrain] Merged rows  : {len(df_merged)}")

    # Save versioned snapshot
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    snapshot_path = os.path.join(MERGED_DIR, f"training_snapshot_{ts}.csv")
    df_merged.to_csv(snapshot_path, index=False)
    print(f"[retrain] Snapshot saved: {snapshot_path}")

    return df_merged


# ── Single-target training (simplified from v2) ───────────────────────────────

def train_one_target(target, df_eng, oof_predictions):
    """
    Train LightGBM + ExtraTrees stacked ensemble for one target.
    Returns (bundle_dict, metrics_dict, oof_series) or (None, None, None).
    """
    non_feature_cols = set(REGRESSION_TARGETS + ["state", "district", "timestamp"])
    base_cols = [c for c in df_eng.columns
                 if c not in non_feature_cols and not c.startswith("oof_")]

    oof_col_names = []
    for src in CROSS_TARGET_MAP.get(target, []):
        if src in oof_predictions and src not in base_cols:
            col = f"oof_{src}"
            oof_col_names.append(col)
            if col not in df_eng.columns:
                df_eng[col] = oof_predictions[src]

    feature_cols = base_cols + oof_col_names
    sub = df_eng[feature_cols + [target]].dropna(subset=[target])

    if len(sub) < 30:
        print(f"  [{target.upper()}] Skipped — only {len(sub)} rows.")
        return None, None, None

    use_log = target in LOG_TARGETS
    y_raw   = sub[target].values
    y       = np.log1p(np.clip(y_raw, 0, None)) if use_log else y_raw
    X       = sub[feature_cols].values

    kf     = KFold(n_splits=N_FOLDS, shuffle=True, random_state=RANDOM_SEED)
    splits = list(kf.split(X))

    # Optuna
    def objective(trial):
        params = {
            "objective": "regression", "metric": "rmse",
            "verbosity": -1, "n_jobs": -1, "random_state": RANDOM_SEED,
            "n_estimators": 1000,
            "learning_rate":     trial.suggest_float("lr", 0.01, 0.15, log=True),
            "num_leaves":        trial.suggest_int("nl", 20, 60),
            "min_child_samples": trial.suggest_int("mcs", 5, 30),
            "subsample":         trial.suggest_float("ss", 0.6, 1.0),
            "colsample_bytree":  trial.suggest_float("cs", 0.6, 1.0),
            "reg_alpha":         trial.suggest_float("ra", 1e-5, 1.0, log=True),
            "reg_lambda":        trial.suggest_float("rl", 1e-5, 1.0, log=True),
        }
        rmses = []
        for tr, val in splits:
            m = lgb.LGBMRegressor(**params)
            m.fit(X[tr], y[tr],
                  eval_set=[(X[val], y[val])],
                  callbacks=[lgb.early_stopping(30, verbose=False),
                             lgb.log_evaluation(period=-1)])
            rmses.append(np.sqrt(mean_squared_error(y[val], m.predict(X[val]))))
        return np.mean(rmses)

    study = optuna.create_study(direction="minimize",
                                sampler=optuna.samplers.TPESampler(seed=RANDOM_SEED))
    study.optimize(objective, n_trials=OPTUNA_TRIALS, show_progress_bar=False)

    best_params = {
        **study.best_params,
        "objective": "regression", "metric": "rmse",
        "verbosity": -1, "n_jobs": -1,
        "random_state": RANDOM_SEED, "n_estimators": 1000,
    }
    # Remap trial param names back
    best_params["learning_rate"]     = best_params.pop("lr", best_params.get("learning_rate"))
    best_params["num_leaves"]        = best_params.pop("nl", best_params.get("num_leaves"))
    best_params["min_child_samples"] = best_params.pop("mcs", best_params.get("min_child_samples"))
    best_params["subsample"]         = best_params.pop("ss", best_params.get("subsample"))
    best_params["colsample_bytree"]  = best_params.pop("cs", best_params.get("colsample_bytree"))
    best_params["reg_alpha"]         = best_params.pop("ra", best_params.get("reg_alpha"))
    best_params["reg_lambda"]        = best_params.pop("rl", best_params.get("reg_lambda"))

    # OOF
    oof_lgb = np.zeros(len(sub))
    oof_et  = np.zeros(len(sub))
    for tr, val in splits:
        m = lgb.LGBMRegressor(**best_params)
        m.fit(X[tr], y[tr],
              eval_set=[(X[val], y[val])],
              callbacks=[lgb.early_stopping(30, verbose=False),
                         lgb.log_evaluation(period=-1)])
        oof_lgb[val] = m.predict(X[val])
        et = ExtraTreesRegressor(n_estimators=200, random_state=RANDOM_SEED, n_jobs=-1)
        et.fit(X[tr], y[tr])
        oof_et[val] = et.predict(X[val])

    ridge = Ridge(alpha=1.0)
    ridge.fit(np.column_stack([oof_lgb, oof_et]), y)
    oof_stacked = ridge.predict(np.column_stack([oof_lgb, oof_et]))
    y_real   = np.expm1(y) if use_log else y
    oof_real = np.expm1(oof_stacked) if use_log else oof_stacked
    # Post-prediction ICAR clip
    if target in ICAR_RANGES:
        lo, hi = ICAR_RANGES[target]
        oof_real = np.clip(oof_real, lo, hi)

    mae  = mean_absolute_error(y_real, oof_real)
    rmse = np.sqrt(mean_squared_error(y_real, oof_real))
    r2   = r2_score(y_real, oof_real)
    print(f"  [{target.upper()}]  MAE={mae:.3f}  RMSE={rmse:.3f}  R²={r2:.3f}  rows={len(sub)}")

    # Final full-data retrain
    final_lgb = lgb.LGBMRegressor(**{**best_params, "n_estimators": 600})
    final_lgb.fit(X, y)
    final_et  = ExtraTreesRegressor(n_estimators=200, random_state=RANDOM_SEED, n_jobs=-1)
    final_et.fit(X, y)

    # ── Persist best params for fast-retrain reuse ───────────────────────────────
    _save_best_params(target, best_params)

    bundle = {
        "lgbm":          final_lgb,
        "et":            final_et,
        "ridge":         ridge,
        "feature_cols":  feature_cols,
        "has_state":     False,
        "use_log":       use_log,
        "state_means":   {},
        "global_mean_y": float(y.mean()),
        "icar_range":    ICAR_RANGES.get(target, (0, None)),
    }
    model_path = os.path.join(MODEL_DIR, f"lgbm_{target}.pkl")
    with open(model_path, "wb") as f:
        pickle.dump(bundle, f)

    metrics = {
        "target": target, "rows": len(sub),
        "MAE": round(mae, 4), "RMSE": round(rmse, 4), "R2": round(r2, 4),
    }
    return bundle, metrics, pd.Series(oof_real, index=sub.index)


# ── Fast incremental retrain (no Optuna, 3-fold, cached params) ───────────────────

def train_one_target_fast(target, df_eng, oof_predictions):
    """
    Incremental retrain for one target.
    - Skips Optuna: uses cached best hyperparams (from previous full run)
      or pre-tuned defaults if no cache exists.
    - 3-fold CV instead of 5 (3x faster OOF).
    - n_estimators = 400 instead of 1000.
    - Keeps LightGBM + ExtraTrees + Ridge stacking so prediction bundles
      stay fully compatible with map_utils.predict_for_point.

    Typical speedup vs full retrain: ~10–15× per target.
    """
    non_feature_cols = set(REGRESSION_TARGETS + ["state", "district", "timestamp"])
    base_cols = [c for c in df_eng.columns
                 if c not in non_feature_cols and not c.startswith("oof_")]

    oof_col_names = []
    for src in CROSS_TARGET_MAP.get(target, []):
        if src in oof_predictions and src not in base_cols:
            col = f"oof_{src}"
            oof_col_names.append(col)
            if col not in df_eng.columns:
                df_eng[col] = oof_predictions[src]

    feature_cols = base_cols + oof_col_names
    sub = df_eng[feature_cols + [target]].dropna(subset=[target])

    if len(sub) < 30:
        print(f"  [{target.upper()}] Skipped — only {len(sub)} rows.")
        return None, None, None

    use_log = target in LOG_TARGETS
    y_raw   = sub[target].values
    y       = np.log1p(np.clip(y_raw, 0, None)) if use_log else y_raw
    X       = sub[feature_cols].values

    # Load cached params (from a previous full Optuna run) or use defaults
    tuned = _load_best_params(target)
    fast_params = {
        **tuned,
        "objective":     "regression",
        "metric":        "rmse",
        "verbosity":     -1,
        "n_jobs":        -1,
        "random_state":  RANDOM_SEED,
        "n_estimators":  400,      # reduced from 1000 for speed
    }

    kf     = KFold(n_splits=3, shuffle=True, random_state=RANDOM_SEED)  # 3-fold
    splits = list(kf.split(X))

    oof_lgb = np.zeros(len(sub))
    oof_et  = np.zeros(len(sub))
    for tr, val in splits:
        m = lgb.LGBMRegressor(**fast_params)
        m.fit(X[tr], y[tr],
              eval_set=[(X[val], y[val])],
              callbacks=[lgb.early_stopping(20, verbose=False),
                         lgb.log_evaluation(period=-1)])
        oof_lgb[val] = m.predict(X[val])
        et = ExtraTreesRegressor(n_estimators=100, random_state=RANDOM_SEED, n_jobs=-1)
        et.fit(X[tr], y[tr])
        oof_et[val] = et.predict(X[val])

    ridge = Ridge(alpha=1.0)
    ridge.fit(np.column_stack([oof_lgb, oof_et]), y)
    oof_stacked = ridge.predict(np.column_stack([oof_lgb, oof_et]))
    y_real   = np.expm1(y) if use_log else y
    oof_real = np.expm1(oof_stacked) if use_log else oof_stacked
    # Post-prediction ICAR clip
    if target in ICAR_RANGES:
        lo, hi = ICAR_RANGES[target]
        oof_real = np.clip(oof_real, lo, hi)

    mae  = mean_absolute_error(y_real, oof_real)
    rmse = np.sqrt(mean_squared_error(y_real, oof_real))
    r2   = r2_score(y_real, oof_real)
    print(f"  [{target.upper()}] FAST  MAE={mae:.3f}  RMSE={rmse:.3f}  R²={r2:.3f}  rows={len(sub)}")

    # Final full-data fit
    final_lgb = lgb.LGBMRegressor(**{**fast_params, "n_estimators": 400})
    final_lgb.fit(X, y)
    final_et  = ExtraTreesRegressor(n_estimators=100, random_state=RANDOM_SEED, n_jobs=-1)
    final_et.fit(X, y)

    bundle = {
        "lgbm":          final_lgb,
        "et":            final_et,
        "ridge":         ridge,
        "feature_cols":  feature_cols,
        "has_state":     False,
        "use_log":       use_log,
        "state_means":   {},
        "global_mean_y": float(y.mean()),
        "icar_range":    ICAR_RANGES.get(target, (0, None)),
    }
    model_path = os.path.join(MODEL_DIR, f"lgbm_{target}.pkl")
    with open(model_path, "wb") as f:
        pickle.dump(bundle, f)

    metrics = {
        "target": target, "rows": len(sub),
        "MAE": round(mae, 4), "RMSE": round(rmse, 4), "R2": round(r2, 4),
        "mode": "fast",
    }
    return bundle, metrics, pd.Series(oof_real, index=sub.index)


# ── Fertility classifier ──────────────────────────────────────────────────────

def retrain_fertility_classifier(df):
    avail = [f for f in CLASSIFICATION_FEATURES if f in df.columns]
    sub   = df[avail].dropna().copy()
    if len(sub) < 30:
        print("[retrain] Not enough rows for fertility classifier.")
        return

    score = pd.Series(0.0, index=sub.index)
    for col, w in FERTILITY_WEIGHTS.items():
        if col not in sub.columns:
            continue
        # Use ICAR agronomic range for normalisation (not data-driven min/max)
        lo, hi = ICAR_RANGES.get(col, (sub[col].min(), sub[col].max()))
        rng    = hi - lo
        norm   = np.clip((sub[col] - lo) / rng, 0, 1) if rng > 0 else 0.0
        score += w * norm

    import pandas as _pd
    sub["fertility_class"] = _pd.cut(
        score * 100,
        bins=[-0.01, 33.33, 66.66, 100.01],
        labels=["low", "medium", "high"]
    ).astype(str)

    X = sub[avail].values
    y = sub["fertility_class"].to_numpy(dtype=str)
    rf = RandomForestClassifier(n_estimators=300, min_samples_leaf=2,
                                random_state=RANDOM_SEED, n_jobs=-1)
    rf.fit(X, y)
    with open(os.path.join(MODEL_DIR, "rf_fertility.pkl"), "wb") as f:
        pickle.dump(rf, f)
    print(f"[retrain] Fertility classifier saved. ({len(sub)} rows)")


# ── Main ──────────────────────────────────────────────────────────────────────

def run_retrain(skip_enrich: bool = False, dry_run: bool = False, fast: bool = False):
    """
    Run a full or fast incremental retrain.

    fast=True  : Skip Optuna, use cached/default params, 3-fold CV.
                 Cuts time from ~30-60 min to ~3-6 min.
                 Use this for upload-triggered retrains.
    fast=False : Full Optuna-tuned retrain (original behaviour).
                 Saves best params for future fast runs.
    """
    start_time = datetime.now()
    mode_label = "FAST" if fast else "FULL"
    print("=" * 60)
    print(f"[retrain] Mode: {mode_label} | Started at {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    df = load_and_merge(skip_enrich=skip_enrich)

    # Fill numeric NaNs
    num_cols = df.select_dtypes(include=[np.number]).columns
    df[num_cols] = df[num_cols].fillna(df[num_cols].median())

    if dry_run:
        print(f"[retrain] DRY RUN — would train on {len(df)} rows. Exiting.")
        return {"status": "dry_run", "rows": len(df)}

    df_eng = engineer_features(df)
    print(f"[retrain] Feature engineering done. Shape: {df_eng.shape}")

    eval_rows       = []
    oof_predictions = {}

    train_fn = train_one_target_fast if fast else train_one_target

    for target in REGRESSION_TARGETS:
        if target not in df_eng.columns:
            continue
        bundle, metrics, oof_series = train_fn(target, df_eng, oof_predictions)
        if metrics:
            eval_rows.append(metrics)
        if oof_series is not None:
            oof_predictions[target] = oof_series

    retrain_fertility_classifier(df_eng)

    eval_df = pd.DataFrame(eval_rows)
    eval_df.to_csv(os.path.join(MODEL_DIR, "eval_regression.csv"), index=False)

    end_time = datetime.now()
    elapsed  = (end_time - start_time).total_seconds()

    log = {
        "retrain_time":    end_time.isoformat(),
        "elapsed_seconds": round(elapsed, 1),
        "mode":            mode_label,
        "training_rows":   len(df),
        "live_data_rows":  len(pd.read_csv(LIVE_CSV)) if os.path.exists(LIVE_CSV) else 0,
        "models_updated":  [r["target"] for r in eval_rows],
        "metrics":         eval_rows,
    }
    with open(LOG_PATH, "w") as f:
        json.dump(log, f, indent=2)

    print("=" * 60)
    print(f"[retrain] Done in {elapsed:.1f}s ({mode_label}) | {len(eval_rows)} models updated")
    print("=" * 60)
    return log


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Retrain soil models on new data.")
    parser.add_argument("--skip-enrich", action="store_true",
                        help="Skip satellite enrichment for live rows.")
    parser.add_argument("--dry-run",     action="store_true",
                        help="Show merge summary without retraining.")
    parser.add_argument("--fast",        action="store_true",
                        help="Skip Optuna; use cached params + 3-fold CV. ~10x faster.")
    args = parser.parse_args()
    run_retrain(skip_enrich=args.skip_enrich, dry_run=args.dry_run, fast=args.fast)
