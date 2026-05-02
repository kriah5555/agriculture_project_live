"""
train.py
--------
Production-grade training pipeline for ICAR Soil Intelligence.

Reads: data/processed/final_cleaned_dataset.csv
       (output of preprocessing.py -- real ICAR parameter values, NOT percentages)

Outputs:
  models/lgbm_<param>.pkl           -- stacked ensemble bundle per regression target
  models/rf_fertility.pkl           -- Random Forest fertility classifier
  models/eval_regression.csv        -- MAE, RMSE, R², MAPE per target
  models/eval_classification.txt    -- Fertility classifier report
  models/best_hyperparams.json      -- Cached Optuna params for fast retraining

Design choices:
  - NO log-transform on ph, n, p, k, organic_carbon, ec
  - log1p ONLY on fe, zn, cu, mn, s, b  (right-skewed micronutrient ppm)
  - Strict ICAR post-prediction clipping (same ranges as preprocessing.py)
  - Same feature engineering as map_utils.py (no train/inference mismatch)
  - Ensemble: LightGBM + ExtraTrees → Ridge meta-model (stacking)
  - Cross-target OOF features in dependency order
  - State target-encoding (in-fold, no leakage)
  - Optuna TPE, 80 trials full / 30 trials fast-retrain
"""

import os
import sys
import json
import pickle
import warnings
import numpy as np
import pandas as pd
import lightgbm as lgb
import optuna

from sklearn.ensemble import ExtraTreesRegressor, RandomForestClassifier
from sklearn.linear_model import Ridge
from sklearn.model_selection import KFold, train_test_split
from sklearn.metrics import (
    mean_absolute_error, mean_squared_error, r2_score,
    accuracy_score, classification_report,
)
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

warnings.filterwarnings("ignore")
optuna.logging.set_verbosity(optuna.logging.WARNING)

# -- Paths ---------------------------------------------------------------------
ROOT          = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INPUT_CSV     = os.path.join(ROOT, "data", "processed", "final_cleaned_dataset.csv")
MODEL_DIR     = os.path.join(ROOT, "models")
BEST_HP_JSON  = os.path.join(MODEL_DIR, "best_hyperparams.json")
RANDOM_SEED   = 42
N_FOLDS       = 5
OPTUNA_TRIALS = 80

os.makedirs(MODEL_DIR, exist_ok=True)

# -- ICAR Post-Prediction Clip Ranges -----------------------------------------
# MUST stay in sync with preprocessing.py::ICAR_RANGES
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

# -- Feature / target definitions ----------------------------------------------
BASE_FEATURES = [
    "lat", "lon", "ndvi", "temperature", "rainfall",
    "elevation", "clay_pct", "sand_pct", "silt_pct",
]

# Cross-target cascade order (must mirror map_utils.py::INFERENCE_ORDER)
CROSS_TARGET_ORDER = [
    "ph", "ec", "organic_carbon", "n", "p", "k",
    "s", "fe", "zn", "cu", "b", "mn",
]

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

# log1p ONLY for right-skewed micronutrients measured in ppm
# NEVER apply log to ph, n, p, k, organic_carbon, ec
LOG_TARGETS = {"fe", "s", "mn", "cu", "b", "zn"}

CLASSIFICATION_FEATURES = [
    "ph", "n", "p", "k", "organic_carbon",
    "s", "fe", "zn", "ndvi", "rainfall",
    "elevation", "clay_pct", "sand_pct", "silt_pct",
]

# Normalised fertility score weights (sum = 1.0)
FERTILITY_WEIGHTS = {
    "n": 0.25, "p": 0.20, "k": 0.20, "organic_carbon": 0.20,
    "ndvi": 0.10, "rainfall": 0.05,
}


# -- Feature engineering (MUST exactly mirror map_utils.py::_engineer_features) -
def engineer_features(df: pd.DataFrame) -> pd.DataFrame:
    """Add polynomial and interaction features derived from base features only."""
    d = df.copy()
    d["lat2"]        = d["lat"] ** 2
    d["lon2"]        = d["lon"] ** 2
    d["lat_lon"]     = d["lat"] * d["lon"]
    d["ndvi_rain"]   = d["ndvi"] * d["rainfall"]
    d["temp_elev"]   = d["temperature"] * d["elevation"]
    d["rain_elev"]   = d["rainfall"] * d["elevation"]
    d["ndvi_temp"]   = d["ndvi"] * d["temperature"]
    d["clay_sand"]   = d["clay_pct"] / (d["sand_pct"] + 1)
    d["silt_clay"]   = d["silt_pct"] / (d["clay_pct"] + 1)
    d["texture_sum"] = d["clay_pct"] + d["silt_pct"]
    d["sin_lat"]     = np.sin(np.deg2rad(d["lat"]))
    d["cos_lon"]     = np.cos(np.deg2rad(d["lon"]))
    return d


def _non_feature_cols(regression_targets):
    return set(regression_targets + ["state", "district", "timestamp"])


def get_base_feature_names(df: pd.DataFrame, regression_targets: list) -> list:
    """Return all non-target, non-admin, non-oof columns."""
    drop = _non_feature_cols(regression_targets)
    return [c for c in df.columns if c not in drop and not c.startswith("oof_")]


# -- State target encoding (in-fold, no data leakage) -------------------------
def add_state_encoding(X_tr_df, X_val_df, y_tr, col="state_enc"):
    state_map   = y_tr.groupby(X_tr_df["state"]).mean()
    global_mean = y_tr.mean()
    X_tr_df  = X_tr_df.copy()
    X_val_df = X_val_df.copy()
    X_tr_df[col]  = X_tr_df["state"].map(state_map).fillna(global_mean).values
    X_val_df[col] = X_val_df["state"].map(state_map).fillna(global_mean).values
    return X_tr_df, X_val_df


# -- Optuna LightGBM objective -------------------------------------------------
def _lgb_objective(X, y, splits, seed):
    def objective(trial):
        params = {
            "objective":         "regression",
            "metric":            "rmse",
            "verbosity":         -1,
            "n_jobs":            -1,
            "random_state":      seed,
            "n_estimators":      2000,
            "learning_rate":     trial.suggest_float("learning_rate", 0.01, 0.15, log=True),
            "num_leaves":        trial.suggest_int("num_leaves", 20, 80),
            "min_child_samples": trial.suggest_int("min_child_samples", 5, 40),
            "subsample":         trial.suggest_float("subsample", 0.5, 1.0),
            "colsample_bytree":  trial.suggest_float("colsample_bytree", 0.5, 1.0),
            "reg_alpha":         trial.suggest_float("reg_alpha", 1e-5, 2.0, log=True),
            "reg_lambda":        trial.suggest_float("reg_lambda", 1e-5, 2.0, log=True),
            "min_split_gain":    trial.suggest_float("min_split_gain", 0.0, 0.5),
        }
        rmses = []
        for tr_idx, val_idx in splits:
            m = lgb.LGBMRegressor(**params)
            m.fit(
                X[tr_idx], y[tr_idx],
                eval_set=[(X[val_idx], y[val_idx])],
                callbacks=[lgb.early_stopping(50, verbose=False),
                           lgb.log_evaluation(period=-1)]
            )
            rmses.append(np.sqrt(mean_squared_error(y[val_idx], m.predict(X[val_idx]))))
        return np.mean(rmses)
    return objective


# -- Hyperparameter cache (for fast retraining) --------------------------------
def _save_hp(target: str, params: dict):
    store = {}
    if os.path.exists(BEST_HP_JSON):
        try:
            with open(BEST_HP_JSON) as f:
                store = json.load(f)
        except Exception:
            pass
    keep = ["learning_rate", "num_leaves", "min_child_samples",
            "subsample", "colsample_bytree", "reg_alpha", "reg_lambda"]
    store[target] = {k: params[k] for k in keep if k in params}
    with open(BEST_HP_JSON, "w") as f:
        json.dump(store, f, indent=2)


# -- Clip prediction to ICAR range --------------------------------------------
def clip_prediction(target: str, value: float) -> float:
    """Enforce ICAR agronomic limits on model output."""
    if target in ICAR_RANGES:
        lo, hi = ICAR_RANGES[target]
        return float(np.clip(value, lo, hi))
    return float(max(0.0, value))


# -- Train one target ----------------------------------------------------------
def train_target(target, df_eng, oof_predictions, n_trials=OPTUNA_TRIALS):
    """
    Stacked ensemble (LightGBM + ExtraTrees → Ridge) for one regression target.
    Returns (bundle, metrics, oof_series) or (None, None, None).
    """
    print(f"\n  -- [{target.upper()}] {'-'*45}")

    all_targets = list(ICAR_RANGES.keys())
    base_cols   = get_base_feature_names(df_eng, all_targets)

    # Add only the cross-target OOF columns this target depends on
    oof_col_names = []
    for src in CROSS_TARGET_MAP.get(target, []):
        if src in oof_predictions and src not in base_cols:
            col = f"oof_{src}"
            oof_col_names.append(col)
            if col not in df_eng.columns:
                df_eng[col] = oof_predictions[src]

    feature_cols = base_cols + oof_col_names

    has_state  = "state" in df_eng.columns
    state_cols = ["state"] if has_state else []
    sub        = df_eng[feature_cols + state_cols + [target]].dropna(subset=[target])
    print(f"  Rows: {len(sub)}")

    if len(sub) < 30:
        print("  [SKIP] Not enough rows.")
        return None, None, None

    use_log = target in LOG_TARGETS
    y_raw   = sub[target].values
    y       = np.log1p(np.clip(y_raw, 0, None)) if use_log else y_raw

    kf     = KFold(n_splits=N_FOLDS, shuffle=True, random_state=RANDOM_SEED)
    splits = list(kf.split(sub))
    X_no_state = sub[feature_cols].values

    # -- Optuna tuning -----------------------------------------------------
    print(f"  [Optuna] {n_trials} trials...")
    study = optuna.create_study(
        direction="minimize",
        sampler=optuna.samplers.TPESampler(seed=RANDOM_SEED)
    )
    study.optimize(
        _lgb_objective(X_no_state, y, splits, RANDOM_SEED),
        n_trials=n_trials,
        show_progress_bar=False
    )
    best_params = {
        **study.best_params,
        "objective": "regression", "metric": "rmse",
        "verbosity": -1, "n_jobs": -1,
        "random_state": RANDOM_SEED, "n_estimators": 2000,
    }
    print(f"  Best Optuna RMSE: {study.best_value:.4f}")
    _save_hp(target, best_params)

    # -- OOF with best params + state encoding -----------------------------
    oof_lgb = np.zeros(len(sub))
    oof_et  = np.zeros(len(sub))

    for tr_idx, val_idx in splits:
        X_tr_df  = sub.iloc[tr_idx][feature_cols + state_cols]
        X_val_df = sub.iloc[val_idx][feature_cols + state_cols]
        y_tr     = y[tr_idx]

        if has_state:
            X_tr_df, X_val_df = add_state_encoding(
                X_tr_df, X_val_df,
                pd.Series(y_tr, index=X_tr_df.index)
            )
            feat_with_enc = feature_cols + ["state_enc"]
        else:
            feat_with_enc = feature_cols

        X_tr  = X_tr_df[feat_with_enc].values
        X_val = X_val_df[feat_with_enc].values

        lgb_m = lgb.LGBMRegressor(**best_params)
        lgb_m.fit(X_tr, y_tr,
                  eval_set=[(X_val, y[val_idx])],
                  callbacks=[lgb.early_stopping(50, verbose=False),
                             lgb.log_evaluation(period=-1)])
        oof_lgb[val_idx] = lgb_m.predict(X_val)

        et_m = ExtraTreesRegressor(n_estimators=300, random_state=RANDOM_SEED, n_jobs=-1)
        et_m.fit(X_tr, y_tr)
        oof_et[val_idx] = et_m.predict(X_val)

    # -- Ridge meta-model -------------------------------------------------
    meta_X = np.column_stack([oof_lgb, oof_et])
    ridge  = Ridge(alpha=1.0)
    ridge.fit(meta_X, y)
    oof_stacked = ridge.predict(meta_X)

    # Back-transform
    y_real   = np.expm1(y)      if use_log else y
    oof_real = np.expm1(oof_stacked) if use_log else oof_stacked

    # Post-prediction clip
    oof_real = np.array([clip_prediction(target, v) for v in oof_real])

    mae  = mean_absolute_error(y_real, oof_real)
    rmse = np.sqrt(mean_squared_error(y_real, oof_real))
    r2   = r2_score(y_real, oof_real)
    mape = np.mean(np.abs((y_real - oof_real) / (np.abs(y_real) + 1e-6))) * 100

    print(f"  OOF MAE={mae:.4f}  RMSE={rmse:.4f}  R²={r2:.4f}  MAPE={mape:.1f}%")

    # -- Final full-data retrain -------------------------------------------
    if has_state:
        global_mean = y.mean()
        state_means = pd.Series(y, index=sub.index).groupby(sub["state"].values).mean()
        enc = sub["state"].map(state_means).fillna(global_mean).values.reshape(-1, 1)
        X_full = np.hstack([X_no_state, enc])
    else:
        X_full      = X_no_state
        global_mean = y.mean()
        state_means = pd.Series(dtype=float)

    final_params = {**best_params, "n_estimators": 600}
    final_lgb    = lgb.LGBMRegressor(**final_params)
    final_lgb.fit(X_full, y)
    final_et = ExtraTreesRegressor(n_estimators=300, random_state=RANDOM_SEED, n_jobs=-1)
    final_et.fit(X_full, y)

    bundle = {
        "lgbm":          final_lgb,
        "et":            final_et,
        "ridge":         ridge,
        "feature_cols":  feature_cols,
        "has_state":     has_state,
        "use_log":       use_log,
        "state_means":   state_means.to_dict() if has_state else {},
        "global_mean_y": float(global_mean),
        # Store ICAR range so predict.py can clip without importing train.py
        "icar_range":    ICAR_RANGES.get(target, (0, None)),
    }
    model_path = os.path.join(MODEL_DIR, f"lgbm_{target}.pkl")
    with open(model_path, "wb") as f:
        pickle.dump(bundle, f)
    print(f"  Saved: {model_path}")

    metrics = {
        "target": target, "rows": len(sub),
        "MAE": round(mae, 4), "RMSE": round(rmse, 4),
        "R2": round(r2, 4), "MAPE_pct": round(mape, 1),
    }
    return bundle, metrics, pd.Series(oof_real, index=sub.index)


# -- Fertility score (ICAR-normalised, 0–100) ----------------------------------
def compute_fertility_score(df: pd.DataFrame) -> pd.Series:
    """
    Normalise each soil parameter to [0,1] using its ICAR agronomic range
    (not data-driven min/max), then compute weighted sum → scale to [0,100].
    """
    score = pd.Series(0.0, index=df.index)
    for col, weight in FERTILITY_WEIGHTS.items():
        if col not in df.columns:
            continue
        lo, hi = ICAR_RANGES.get(col, (df[col].min(), df[col].max()))
        rng    = hi - lo
        norm   = np.clip((df[col] - lo) / rng, 0, 1) if rng > 0 else 0.0
        score += weight * norm
    return (score * 100).clip(0, 100).round(2)


def classify_fertility(score: pd.Series) -> pd.Series:
    return pd.cut(score,
                  bins=[-0.01, 33.33, 66.66, 100.01],
                  labels=["low", "medium", "high"]).astype(str)


# -- Fertility classifier (Phase 2) --------------------------------------------
def train_fertility_classifier(df: pd.DataFrame) -> None:
    print("\n" + "=" * 55)
    print("PHASE 2 -- Fertility Classification (Random Forest)")
    print("=" * 55)

    avail = [f for f in CLASSIFICATION_FEATURES if f in df.columns]
    sub   = df[avail].dropna().copy()
    sub["fertility_score"] = compute_fertility_score(sub)
    sub["fertility_class"] = classify_fertility(sub["fertility_score"])
    print(f"\n  Rows: {len(sub)}")
    print("  Classes:\n  " +
          sub["fertility_class"].value_counts().to_string().replace("\n", "\n  "))

    X = sub[avail].values
    y = sub["fertility_class"].to_numpy(dtype=str)
    X_tr, X_te, y_tr, y_te = train_test_split(
        X, y, test_size=0.2, random_state=RANDOM_SEED, stratify=y
    )

    rf = RandomForestClassifier(n_estimators=300, min_samples_leaf=2,
                                random_state=RANDOM_SEED, n_jobs=-1)
    rf.fit(X_tr, y_tr)
    acc    = accuracy_score(y_te, rf.predict(X_te))
    report = classification_report(y_te, rf.predict(X_te))
    print(f"\n  Accuracy: {acc:.4f} ({acc*100:.1f}%)")
    print("  " + report.replace("\n", "\n  "))

    with open(os.path.join(MODEL_DIR, "rf_fertility.pkl"), "wb") as f:
        pickle.dump(rf, f)
    with open(os.path.join(MODEL_DIR, "eval_classification.txt"), "w") as f:
        f.write(f"RANDOM FOREST (ICAR-normalised fertility)\nAccuracy: {acc:.4f}\n\n{report}\n")
    print("  Classifier saved.")


# -- Main ----------------------------------------------------------------------
def main(n_trials: int = OPTUNA_TRIALS):
    if not os.path.exists(INPUT_CSV):
        sys.exit(
            f"\n[ERROR] Input dataset not found: {INPUT_CSV}\n"
            "  Run preprocessing.py first:\n"
            "    python ml_pipeline/preprocessing.py\n"
        )

    print(f"Loading: {INPUT_CSV}")
    df = pd.read_csv(INPUT_CSV)
    print(f"  Shape: {df.shape}  |  Columns: {df.columns.tolist()}")

    # Fill any remaining NaNs with column median before training
    num_cols = df.select_dtypes(include=[np.number]).columns
    df[num_cols] = df[num_cols].fillna(df[num_cols].median())

    # Feature engineering
    df_eng = engineer_features(df)
    print(f"  After engineering: {df_eng.shape[1]} columns")

    print("\n" + "=" * 55)
    print("PHASE 1 -- Regression (LightGBM + ExtraTrees Ensemble)")
    print("=" * 55)

    eval_rows       = []
    oof_predictions = {}

    for target in CROSS_TARGET_ORDER:
        if target not in df_eng.columns:
            print(f"  [SKIP] {target} not in dataset columns.")
            continue
        bundle, metrics, oof_series = train_target(
            target, df_eng, oof_predictions, n_trials=n_trials
        )
        if metrics:
            eval_rows.append(metrics)
        if oof_series is not None:
            oof_predictions[target] = oof_series

    # Save regression eval
    eval_df = pd.DataFrame(eval_rows)
    eval_df.to_csv(os.path.join(MODEL_DIR, "eval_regression.csv"), index=False)

    print("\n\n" + "=" * 55)
    print("REGRESSION SUMMARY")
    print("=" * 55)
    print(eval_df.to_string(index=False))

    # Phase 2 -- Fertility classifier
    train_fertility_classifier(df_eng)

    print("\n" + "=" * 55)
    print("ALL DONE -- models saved to:", MODEL_DIR)
    print("=" * 55)


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="Train soil intelligence models on ICAR data.")
    ap.add_argument("--trials", type=int, default=OPTUNA_TRIALS,
                    help=f"Optuna trials per target (default: {OPTUNA_TRIALS})")
    args = ap.parse_args()
    main(n_trials=args.trials)
