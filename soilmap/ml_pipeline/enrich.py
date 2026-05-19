"""
enrich.py
---------
Adds environmental features (NDVI, weather, elevation, soil texture)
to final_cleaned_dataset.csv using the existing GEE / API helper modules.

MUST be run AFTER preprocessing.py and BEFORE train.py.

Usage:
    python ml_pipeline/enrich.py              # Full run (all 618 rows)
    python ml_pipeline/enrich.py --test       # First 10 rows only
    python ml_pipeline/enrich.py --skip-gee   # Skip GEE (NDVI/elev/texture) — use NASA POWER + defaults
    python ml_pipeline/enrich.py --fast       # Skip ALL APIs, use India-wide defaults (instant)

Steps:
    1. weather   — temperature (C) + rainfall (mm) via NASA POWER API
    2. ndvi      — 1-year median NDVI via GEE Sentinel-2
    3. elevation — elevation (m) via GEE SRTM
    4. texture   — clay/sand/silt (%) via SoilGrids / GEE OpenLandMap

All failed API calls fall back to climatically-plausible Indian defaults
so the dataset always has 100% feature coverage.

Output: overwrites data/processed/final_cleaned_dataset.csv in-place.
"""

import os
import sys
import time
import argparse
import numpy as np
import pandas as pd
from datetime import datetime, timedelta

# ── Paths ─────────────────────────────────────────────────────────────────────
ROOT      = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INPUT_CSV = os.path.join(ROOT, "data", "processed", "final_cleaned_dataset.csv")
ML_DIR    = os.path.join(ROOT, "ml_pipeline")

if ML_DIR not in sys.path:
    sys.path.insert(0, ML_DIR)

# ── Sensible India-wide fallback defaults ─────────────────────────────────────
# Used when API calls fail — derived from IMDAA climatology / SoilGrids medians
INDIA_DEFAULTS = {
    "temperature":  27.5,   # °C  (annual mean across agri belt)
    "rainfall":     950.0,  # mm  (mean annual precipitation)
    "ndvi":         0.45,   # Indian cropland median
    "elevation":    300.0,  # m   (Indo-Gangetic Plain avg)
    "clay_pct":     28.0,   # %   (typical Vertisol / Alfisol)
    "sand_pct":     42.0,   # %
    "silt_pct":     30.0,   # %
}

DELAY_SECS = 0.8   # pause between API calls to stay within rate limits

# ── NDVI date range: last 12 months ──────────────────────────────────────────
END_DT   = datetime.now() - timedelta(days=7)
START_DT = END_DT - timedelta(days=365)
NDVI_START = START_DT.strftime("%Y-%m-%d")
NDVI_END   = END_DT.strftime("%Y-%m-%d")


# ── Step 1: Weather (NASA POWER — free, no auth) ──────────────────────────────
def add_weather(df: pd.DataFrame, skip: bool = False) -> pd.DataFrame:
    print("\n[Enrich] WEATHER via NASA POWER API...")
    if skip:
        print("  [skip] Using India-wide defaults for weather.")
        df["temperature"] = INDIA_DEFAULTS["temperature"]
        df["rainfall"]    = INDIA_DEFAULTS["rainfall"]
        return df

    try:
        from weather import get_weather
        has_mod = True
    except ImportError:
        print("  [WARN] weather module not found. Using defaults.")
        has_mod = False

    temps, rains = [], []
    ok, fail = 0, 0

    for i, row in df.iterrows():
        if has_mod:
            try:
                t, r = get_weather(float(row["lat"]), float(row["lon"]))
                if t is None:
                    raise ValueError("None returned")
                temps.append(float(t))
                rains.append(float(r))
                ok += 1
            except Exception:
                temps.append(INDIA_DEFAULTS["temperature"])
                rains.append(INDIA_DEFAULTS["rainfall"])
                fail += 1
        else:
            temps.append(INDIA_DEFAULTS["temperature"])
            rains.append(INDIA_DEFAULTS["rainfall"])

        if (i + 1) % 50 == 0:
            print(f"  [{i+1}/{len(df)}] weather...")
        time.sleep(DELAY_SECS)

    df["temperature"] = temps
    df["rainfall"]    = rains
    print(f"  Done: OK={ok}  Fallback={fail}  Coverage={ok/len(df)*100:.1f}%")
    return df


# ── Step 2: NDVI (GEE Sentinel-2) ─────────────────────────────────────────────
def add_ndvi(df: pd.DataFrame, skip_gee: bool = False) -> pd.DataFrame:
    print(f"\n[Enrich] NDVI via GEE ({NDVI_START} to {NDVI_END})...")
    if skip_gee:
        print("  [skip] --skip-gee flag set. Using defaults.")
        df["ndvi"] = INDIA_DEFAULTS["ndvi"]
        return df

    try:
        from ndvi import get_ndvi
        has_mod = True
    except ImportError:
        print("  [WARN] ndvi module not found. Using defaults.")
        has_mod = False

    ndvi_vals = []
    ok, fail = 0, 0

    for i, row in df.iterrows():
        if has_mod:
            try:
                nv = get_ndvi(float(row["lat"]), float(row["lon"]),
                              NDVI_START, NDVI_END)
                if nv is None:
                    raise ValueError("None returned")
                ndvi_vals.append(float(nv))
                ok += 1
            except Exception:
                ndvi_vals.append(INDIA_DEFAULTS["ndvi"])
                fail += 1
        else:
            ndvi_vals.append(INDIA_DEFAULTS["ndvi"])

        if (i + 1) % 50 == 0:
            print(f"  [{i+1}/{len(df)}] ndvi...")
        time.sleep(DELAY_SECS)

    df["ndvi"] = ndvi_vals
    print(f"  Done: OK={ok}  Fallback={fail}  Coverage={ok/len(df)*100:.1f}%")
    return df


# ── Step 3: Elevation (GEE SRTM) ─────────────────────────────────────────────
def add_elevation(df: pd.DataFrame, skip_gee: bool = False) -> pd.DataFrame:
    print("\n[Enrich] ELEVATION via GEE SRTM...")
    if skip_gee:
        print("  [skip] --skip-gee flag set. Using defaults.")
        df["elevation"] = INDIA_DEFAULTS["elevation"]
        return df

    try:
        import add_elevation_to_dataset as elev_mod
        try:
            elev_mod.init_gee()
        except Exception:
            pass
        has_mod = True
    except ImportError:
        print("  [WARN] add_elevation_to_dataset not found. Using defaults.")
        has_mod = False

    elev_vals = []
    ok, fail = 0, 0

    for i, row in df.iterrows():
        if has_mod:
            try:
                e = elev_mod.get_elevation(float(row["lat"]), float(row["lon"]))
                if e is None:
                    raise ValueError("None returned")
                elev_vals.append(float(e))
                ok += 1
            except Exception:
                elev_vals.append(INDIA_DEFAULTS["elevation"])
                fail += 1
        else:
            elev_vals.append(INDIA_DEFAULTS["elevation"])

        if (i + 1) % 50 == 0:
            print(f"  [{i+1}/{len(df)}] elevation...")
        time.sleep(DELAY_SECS * 0.5)

    df["elevation"] = elev_vals
    print(f"  Done: OK={ok}  Fallback={fail}  Coverage={ok/len(df)*100:.1f}%")
    return df


# ── Step 4: Soil texture (SoilGrids / GEE OpenLandMap) ───────────────────────
def add_texture(df: pd.DataFrame, skip_gee: bool = False) -> pd.DataFrame:
    print("\n[Enrich] SOIL TEXTURE via SoilGrids / GEE...")
    if skip_gee:
        print("  [skip] --skip-gee flag set. Using defaults.")
        df["clay_pct"] = INDIA_DEFAULTS["clay_pct"]
        df["sand_pct"] = INDIA_DEFAULTS["sand_pct"]
        df["silt_pct"] = INDIA_DEFAULTS["silt_pct"]
        return df

    try:
        import add_soilgrids_to_dataset as tex_mod
        has_mod = True
    except ImportError:
        print("  [WARN] add_soilgrids_to_dataset not found. Using defaults.")
        has_mod = False

    clays, sands, silts = [], [], []
    ok, fail = 0, 0

    for i, row in df.iterrows():
        if has_mod:
            try:
                tex = tex_mod.get_soil_texture(float(row["lat"]), float(row["lon"]))
                clay = tex.get("clay_pct") or INDIA_DEFAULTS["clay_pct"]
                sand = tex.get("sand_pct") or INDIA_DEFAULTS["sand_pct"]
                silt = tex.get("silt_pct") or INDIA_DEFAULTS["silt_pct"]
                clays.append(float(clay))
                sands.append(float(sand))
                silts.append(float(silt))
                ok += 1
            except Exception:
                clays.append(INDIA_DEFAULTS["clay_pct"])
                sands.append(INDIA_DEFAULTS["sand_pct"])
                silts.append(INDIA_DEFAULTS["silt_pct"])
                fail += 1
        else:
            clays.append(INDIA_DEFAULTS["clay_pct"])
            sands.append(INDIA_DEFAULTS["sand_pct"])
            silts.append(INDIA_DEFAULTS["silt_pct"])

        if (i + 1) % 50 == 0:
            print(f"  [{i+1}/{len(df)}] texture...")
        time.sleep(DELAY_SECS * 0.5)

    df["clay_pct"] = clays
    df["sand_pct"] = sands
    df["silt_pct"] = silts
    print(f"  Done: OK={ok}  Fallback={fail}  Coverage={ok/len(df)*100:.1f}%")
    return df


# ── Validation ─────────────────────────────────────────────────────────────────
def validate(df: pd.DataFrame) -> None:
    ENV_COLS = ["ndvi", "temperature", "rainfall", "elevation",
                "clay_pct", "sand_pct", "silt_pct"]
    print("\n" + "=" * 60)
    print("ENRICHMENT VALIDATION")
    print("=" * 60)
    print(f"  {'Column':<18} {'Min':>8} {'Max':>8} {'Mean':>8} {'Nulls':>6}")
    print(f"  {'-'*18} {'-'*8} {'-'*8} {'-'*8} {'-'*6}")
    for c in ENV_COLS:
        if c in df.columns:
            s = df[c].dropna()
            nulls = df[c].isna().sum()
            print(f"  {c:<18} {s.min():>8.3f} {s.max():>8.3f} {s.mean():>8.3f} {nulls:>6}")
        else:
            print(f"  {c:<18} {'MISSING':>30}")
    print(f"\n  Rows: {len(df)}  |  Columns: {len(df.columns)}")
    print("=" * 60)


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    ap = argparse.ArgumentParser(
        description="Enrich final_cleaned_dataset.csv with environmental features."
    )
    ap.add_argument("--test",     action="store_true",
                    help="Process only the first 10 rows.")
    ap.add_argument("--skip-gee", action="store_true",
                    help="Skip GEE calls (NDVI/elevation/texture). Use India-wide defaults.")
    ap.add_argument("--fast",     action="store_true",
                    help="Skip ALL APIs (Weather + GEE). Use India-wide defaults for everything.")
    args = ap.parse_args()

    if args.fast:
        args.skip_gee = True

    if not os.path.exists(INPUT_CSV):
        sys.exit(
            f"\n[ERROR] Input not found: {INPUT_CSV}\n"
            "  Run preprocessing.py first:\n"
            "    python ml_pipeline/preprocessing.py\n"
        )

    print(f"Loading: {INPUT_CSV}")
    df = pd.read_csv(INPUT_CSV)
    print(f"  Shape: {df.shape}")

    if args.test:
        df = df.head(10).copy()
        print(f"  [TEST MODE] Processing first 10 rows only.")

    df = add_weather(df, skip=args.fast)
    df = add_ndvi(df, skip_gee=args.skip_gee)
    df = add_elevation(df, skip_gee=args.skip_gee)
    df = add_texture(df, skip_gee=args.skip_gee)

    # Fill any remaining NaN env features with India defaults
    for col, default in INDIA_DEFAULTS.items():
        if col in df.columns:
            na_count = df[col].isna().sum()
            if na_count > 0:
                print(f"  [fill] {col}: {na_count} NaNs -> {default}")
                df[col] = df[col].fillna(default)

    validate(df)

    if not args.test:
        df.to_csv(INPUT_CSV, index=False)
        print(f"\n[OUTPUT] Saved (enriched): {INPUT_CSV}  ({len(df)} rows)")
    else:
        test_out = INPUT_CSV.replace(".csv", "_test_enriched.csv")
        df.to_csv(test_out, index=False)
        print(f"\n[TEST OUTPUT] Saved: {test_out}")

    print("\n[DONE] Enrichment complete. Run train.py next.\n")


if __name__ == "__main__":
    main()
