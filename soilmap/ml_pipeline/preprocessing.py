"""
preprocessing.py
----------------
ICAR-Aligned Soil Data Preprocessing Pipeline.

Converts Soil Health Card percentage distributions -> real soil parameter values.
Applies strict ICAR agronomic range validation, cleans data, and outputs
the canonical dataset used for all training and inference.

ICAR References:
  - Nitrogen   : Low<240, Medium 240-480, High>480 kg/ha
  - Phosphorus : Low<11,  Medium 11-22,   High>22  kg/ha
  - Potassium  : Low<110, Medium 110-280, High>280 kg/ha
  - EC         : NonSaline<2, Saline>=2 dS/m
  - OC         : Low<0.5, Medium 0.5-0.75, High>0.75 %

Output: data/processed/final_cleaned_dataset.csv
"""

import os
import sys
import glob
import shutil
import warnings
import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")

# ── Paths ─────────────────────────────────────────────────────────────────────
ROOT         = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW_DIR      = os.path.join(ROOT, "data", "raw", "soilcard")
PROCESSED    = os.path.join(ROOT, "data", "processed")
OUTPUT_CSV   = os.path.join(PROCESSED, "final_cleaned_dataset.csv")
COORDS_CSV   = os.path.join(PROCESSED, "district_coords.csv")

os.makedirs(PROCESSED, exist_ok=True)

# ── ICAR-aligned parameter ranges (for np.clip after conversion) ──────────────
ICAR_RANGES = {
    "ph":             (4.5,  9.0),
    "n":              (0.0,  600.0),
    "p":              (0.0,  50.0),
    "k":              (0.0,  500.0),
    "ec":             (0.0,  4.0),
    "organic_carbon": (0.0,  3.0),
    # Micronutrients (ppm)
    "s":              (0.0,  60.0),
    "fe":             (0.0,  100.0),
    "zn":             (0.0,  20.0),
    "cu":             (0.0,  15.0),
    "b":              (0.0,  5.0),
    "mn":             (0.0,  50.0),
}

# Agronomic midpoints for micronutrients (ppm)
# Sufficient ≈ adequate supply, Deficient ≈ low available
MICRO_MIDPOINTS = {
    "s":  {"sufficient": 20.0, "deficient": 6.0},   # Critical 10 mg/kg
    "fe": {"sufficient": 10.0, "deficient": 2.5},   # Critical 4.5 mg/kg
    "zn": {"sufficient": 1.5,  "deficient": 0.5},   # Critical 0.6 mg/kg
    "cu": {"sufficient": 1.5,  "deficient": 0.3},   # Critical 0.2 mg/kg
    "b":  {"sufficient": 0.8,  "deficient": 0.2},   # Critical 0.5 mg/kg
    "mn": {"sufficient": 8.0,  "deficient": 1.5},   # Critical 2.0 mg/kg
}

# Stale intermediate datasets to remove (Task 4)
STALE_DATASETS = [
    "final_dataset.csv",
    "final_dataset_enriched.csv",
    "final_dataset_enriched_test.csv",
    "final_dataset_with_elev.csv",
    "final_dataset_with_elev_test.csv",
    "india_soil_geo.csv",
    "soil_with_ndvi.csv",
    "soil_with_ndvi_test.csv",
]


# ── Step 1: Load all raw soilcard CSVs ────────────────────────────────────────
def load_raw_soilcard(raw_dir: str) -> pd.DataFrame:
    """
    Load and merge all per-state soilcard CSVs, excluding All_State.csv.
    The actual state name is extracted from the filename because the
    'State' column inside the CSV contains district-level values, not state.
    """
    files = glob.glob(os.path.join(raw_dir, "*.csv"))
    dfs = []
    for fpath in sorted(files):
        fname = os.path.basename(fpath)
        if fname.lower() == "all_state.csv":
            continue
        try:
            df = pd.read_csv(fpath)
            # State name = filename without extension (e.g., "KARNATAKA")
            state_name = os.path.splitext(fname)[0].strip().upper()
            df["state_from_file"] = state_name
            dfs.append(df)
            print(f"  [load] {fname:45s}  rows={len(df)}")
        except Exception as e:
            print(f"  [WARN] Failed to load {fname}: {e}")

    if not dfs:
        raise FileNotFoundError(f"No soilcard CSVs found in {raw_dir}")

    merged = pd.concat(dfs, ignore_index=True)
    print(f"\n  [load] Total raw rows: {len(merged)}  |  Columns: {merged.columns.tolist()}\n")
    return merged


# ── Step 2: Normalise column names ────────────────────────────────────────────
def normalise_columns(df: pd.DataFrame) -> pd.DataFrame:
    """
    Strip whitespace, lowercase all column names.
    The soilcard CSVs have:
      - 'State' col  : actually contains district names (confusingly)
      - 'District' col : also contains district names
      - 'state_from_file' : the real state name from filename
    Strategy:
      1. Drop the in-file 'State' col (redundant with District).
      2. Rename 'District' -> 'district'.
      3. Rename 'state_from_file' -> 'state'.
    """
    df.columns = [c.strip().lower() for c in df.columns]

    # Drop the in-file 'state' col — it duplicates 'district' content
    if "state" in df.columns and "state_from_file" in df.columns:
        df = df.drop(columns=["state"])

    # Rename state_from_file -> state (real state name)
    if "state_from_file" in df.columns:
        df = df.rename(columns={"state_from_file": "state"})

    # If there's a 'district' column already and also renamed state->district,
    # keep the one that was originally called 'District'
    alias = {
        "oc_high":       "oc_high",
        "oc_medium":     "oc_medium",
        "oc_low":        "oc_low",
        "ph_alkaline":   "ph_alkaline",
        "ph_acidic":     "ph_acidic",
        "ph_neutral":    "ph_neutral",
        "ec_nonsaline":  "ec_nonsaline",
        "ec_saline":     "ec_saline",
        "s_sufficient":  "s_sufficient",
        "s_deficient":   "s_deficient",
        "fe_sufficient": "fe_sufficient",
        "fe_deficient":  "fe_deficient",
        "zn_sufficient": "zn_sufficient",
        "zn_deficient":  "zn_deficient",
        "cu_sufficient": "cu_sufficient",
        "cu_deficient":  "cu_deficient",
        "b_sufficient":  "b_sufficient",
        "b_deficient":   "b_deficient",
        "mn_sufficient": "mn_sufficient",
        "mn_deficient":  "mn_deficient",
    }
    df = df.rename(columns={k: v for k, v in alias.items() if k in df.columns})
    return df


# ── Step 3: Convert % distributions -> real parameter values ──────────────────
def convert_percentages_to_real(df: pd.DataFrame) -> pd.DataFrame:
    """
    ICAR-aligned weighted-midpoint conversion of distribution % -> real values.
    All input columns are 0–100 distribution percentages summing to ~100.

    pH (0–14):
      ph = (pH_Acidic*5.5 + pH_Neutral*7.0 + pH_Alkaline*8.5) / 100

    Nitrogen (kg/ha): Low<240, Med 240-480, High>480
      midpoints: Low=120, Med=360, High=600

    Phosphorus (kg/ha): Low<11, Med 11-22, High>22
      midpoints: Low=5, Med=16, High=30

    Potassium (kg/ha): Low<110, Med 110-280, High>280
      midpoints: Low=80, Med=200, High=400

    EC (dS/m): NonSaline<2, Saline>=2
      midpoints: NonSaline=0.5, Saline=3.0

    OC (%): Low<0.5, Med 0.5-0.75, High>0.75
      midpoints: Low=0.3, Med=0.75, High=1.5

    Micronutrients (ppm): Sufficient / Deficient
    """
    d = df.copy()

    # -- pH ------------------------------------------------------------------
    if all(c in d.columns for c in ["ph_acidic", "ph_neutral", "ph_alkaline"]):
        d["ph"] = (
            d["ph_acidic"]   * 5.5 +
            d["ph_neutral"]  * 7.0 +
            d["ph_alkaline"] * 8.5
        ) / 100.0
    else:
        print("  [WARN] pH distribution columns missing; ph will be NaN")
        d["ph"] = np.nan

    # -- Nitrogen (N, kg/ha) -------------------------------------------------
    if all(c in d.columns for c in ["n_low", "n_medium", "n_high"]):
        d["n"] = (
            d["n_low"]    * 120 +
            d["n_medium"] * 360 +
            d["n_high"]   * 600
        ) / 100.0
    else:
        print("  [WARN] N distribution columns missing; n will be NaN")
        d["n"] = np.nan

    # -- Phosphorus (P, kg/ha) -----------------------------------------------
    if all(c in d.columns for c in ["p_low", "p_medium", "p_high"]):
        d["p"] = (
            d["p_low"]    * 5  +
            d["p_medium"] * 16 +
            d["p_high"]   * 30
        ) / 100.0
    else:
        print("  [WARN] P distribution columns missing; p will be NaN")
        d["p"] = np.nan

    # -- Potassium (K, kg/ha) ------------------------------------------------
    if all(c in d.columns for c in ["k_low", "k_medium", "k_high"]):
        d["k"] = (
            d["k_low"]    * 80  +
            d["k_medium"] * 200 +
            d["k_high"]   * 400
        ) / 100.0
    else:
        print("  [WARN] K distribution columns missing; k will be NaN")
        d["k"] = np.nan

    # -- Electrical Conductivity (EC, dS/m) ----------------------------------
    if all(c in d.columns for c in ["ec_nonsaline", "ec_saline"]):
        d["ec"] = (
            d["ec_nonsaline"] * 0.5 +
            d["ec_saline"]    * 3.0
        ) / 100.0
    else:
        print("  [WARN] EC distribution columns missing; ec will be NaN")
        d["ec"] = np.nan

    # -- Organic Carbon (OC, %) ----------------------------------------------
    if all(c in d.columns for c in ["oc_low", "oc_medium", "oc_high"]):
        d["organic_carbon"] = (
            d["oc_low"]    * 0.30 +
            d["oc_medium"] * 0.75 +
            d["oc_high"]   * 1.50
        ) / 100.0
    else:
        print("  [WARN] OC distribution columns missing; organic_carbon will be NaN")
        d["organic_carbon"] = np.nan

    # -- Micronutrients (ppm) ------------------------------------------------
    for micro, pts in MICRO_MIDPOINTS.items():
        suf_col = f"{micro}_sufficient"
        def_col = f"{micro}_deficient"
        if suf_col in d.columns and def_col in d.columns:
            d[micro] = (
                d[suf_col] * pts["sufficient"] +
                d[def_col] * pts["deficient"]
            ) / 100.0
        else:
            print(f"  [WARN] {micro} distribution columns missing; {micro} will be NaN")
            d[micro] = np.nan

    return d


# ── Step 4: Drop all percentage / raw columns after conversion ────────────────
PERCENT_COLS = [
    "ph_acidic", "ph_neutral", "ph_alkaline",
    "n_low", "n_medium", "n_high",
    "p_low", "p_medium", "p_high",
    "k_low", "k_medium", "k_high",
    "oc_low", "oc_medium", "oc_high",
    "ec_nonsaline", "ec_saline",
    "s_sufficient", "s_deficient",
    "fe_sufficient", "fe_deficient",
    "zn_sufficient", "zn_deficient",
    "cu_sufficient", "cu_deficient",
    "b_sufficient", "b_deficient",
    "mn_sufficient", "mn_deficient",
    # Extra soilcard administrative columns
    "scheme", "cycle",
]

def drop_percent_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Drop all source percentage/distribution columns after conversion."""
    to_drop = [c for c in PERCENT_COLS if c in df.columns]
    df = df.drop(columns=to_drop)
    print(f"  [clean] Dropped {len(to_drop)} percentage/admin columns.")
    return df


# ── Step 5: Merge with district coordinates ───────────────────────────────────
def merge_coordinates(df: pd.DataFrame, coords_csv: str) -> pd.DataFrame:
    """
    Merge soil data with pre-computed district lat/lon centroids.

    district_coords.csv has 'state' in UPPERCASE (from GeoJSON stname field).
    Soilcard 'state' is also UPPERCASE from filename (e.g., 'KARNATAKA').
    Soilcard 'district' is UPPERCASE from the CSV District column.
    Coords 'district' is Title-Case (e.g., 'Bagalkot').

    Strategy: normalise both sides to lowercase for the merge.
    """
    if not os.path.exists(coords_csv):
        print(f"  [WARN] district_coords.csv not found at {coords_csv}. lat/lon will be NaN.")
        return df

    coords = pd.read_csv(coords_csv)

    # Normalise both sides to lowercase-stripped for matching
    df2 = df.copy()
    df2["state_key"]    = df2["state"].astype(str).str.strip().str.lower()
    df2["district_key"] = df2["district"].astype(str).str.strip().str.lower()

    coords2 = coords.copy()
    coords2["state_key"]    = coords2["state"].astype(str).str.strip().str.lower()
    coords2["district_key"] = coords2["district"].astype(str).str.strip().str.lower()

    # Common district name corrections (soilcard name -> GeoJSON name)
    district_corrections = {
        "bangalore rural": "bengaluru rural",
        "bangalore urban": "bengaluru urban",
        "bangalore": "bengaluru",
        "mysore": "mysuru",
        "belgaum": "belagavi",
        "gulbarga": "kalaburagi",
        "mangalore": "mangaluru",
        "shimoga": "shivamogga",
        "hubli": "hubballi",
        "tumkur": "tumakuru",
        "bijapur": "vijayapura",
        "bellary": "ballari",
        "chitradurga": "chitradurga",
        "ahmadabad": "ahmedabad",
        "vadodra": "vadodara",
        "nashik": "nashik",
        "aurangabad": "chhatrapati sambhajinagar",
    }
    df2["district_key"] = df2["district_key"].replace(district_corrections)

    merged = pd.merge(
        df2, coords2[["state_key", "district_key", "lat", "lon"]],
        on=["state_key", "district_key"], how="left"
    )
    merged = merged.drop(columns=["state_key", "district_key"])

    matched   = merged["lat"].notna().sum()
    unmatched = merged["lat"].isna().sum()
    print(f"  [merge] Rows with coords: {matched}  | Unmatched: {unmatched}")

    if unmatched > 0:
        # Show a sample of unmatched pairs to help debug
        unk = df2.loc[merged["lat"].isna(), ["state", "district"]].drop_duplicates()
        sample = unk.head(10)
        print(f"  [merge] Unmatched sample (first 10):")
        for _, r in sample.iterrows():
            print(f"           {r['state']} / {r['district']}")

    merged = merged.dropna(subset=["lat", "lon"])
    return merged


# ── Step 6: Strict ICAR range validation + clipping ──────────────────────────
def apply_icar_ranges(df: pd.DataFrame) -> pd.DataFrame:
    """
    Clip all converted soil parameters to scientifically valid ICAR ranges.
    Also ensures no negative values exist.
    """
    for col, (lo, hi) in ICAR_RANGES.items():
        if col in df.columns:
            before_min = df[col].min()
            before_max = df[col].max()
            df[col] = np.clip(df[col], lo, hi)
            # Ensure no negatives
            df[col] = df[col].clip(lower=0.0) if lo == 0.0 else df[col]
            after_min = df[col].min()
            after_max = df[col].max()
            if abs(before_min - after_min) > 0.001 or abs(before_max - after_max) > 0.001:
                print(f"  [clip] {col:20s}  before=[{before_min:.3f},{before_max:.3f}]"
                      f"  after=[{after_min:.3f},{after_max:.3f}]  range=({lo},{hi})")
    return df


# ── Step 7: Data cleaning ─────────────────────────────────────────────────────
def clean_data(df: pd.DataFrame) -> pd.DataFrame:
    """
    - Remove duplicate rows
    - Fill missing numeric values with column median
    - Ensure no negative values in soil parameters
    """
    n_before = len(df)
    df = df.drop_duplicates()
    print(f"  [clean] Duplicates removed: {n_before - len(df)}")

    num_cols = df.select_dtypes(include=[np.number]).columns
    medians = df[num_cols].median()
    missing_before = df[num_cols].isna().sum().sum()
    df[num_cols] = df[num_cols].fillna(medians)
    print(f"  [clean] NaN values filled with median: {missing_before}")

    # Ensure soil parameter columns are non-negative
    for col in ICAR_RANGES.keys():
        if col in df.columns:
            neg_count = (df[col] < 0).sum()
            if neg_count > 0:
                print(f"  [clean] Zeroing {neg_count} negative values in {col}")
                df[col] = df[col].clip(lower=0.0)

    return df


# ── Step 8: Validate final dataset ───────────────────────────────────────────
def validate_dataset(df: pd.DataFrame) -> None:
    """Print a validation summary for all converted columns."""
    print("\n" + "=" * 65)
    print("VALIDATION SUMMARY (ICAR Ranges)")
    print("=" * 65)
    print(f"  {'Column':<22} {'Min':>8} {'Max':>8} {'Mean':>8} {'Nulls':>6}  Range OK?")
    print(f"  {'-'*22} {'-'*8} {'-'*8} {'-'*8} {'-'*6}  {'-'*9}")

    for col, (lo, hi) in ICAR_RANGES.items():
        if col not in df.columns:
            continue
        cmin  = df[col].min()
        cmax  = df[col].max()
        cmean = df[col].mean()
        nulls = df[col].isna().sum()
        ok    = "✓" if cmin >= lo - 0.001 and cmax <= hi + 0.001 else "✗ OUT OF RANGE"
        print(f"  {col:<22} {cmin:>8.3f} {cmax:>8.3f} {cmean:>8.3f} {nulls:>6}  {ok}")

    print(f"\n  Final rows: {len(df)}  |  Columns: {len(df.columns)}")
    print("=" * 65)


# ── Step 9: Delete stale intermediate datasets ────────────────────────────────
def remove_stale_datasets(processed_dir: str, stale_list: list,
                           dry_run: bool = False) -> None:
    """Delete outdated CSVs that were built on the old (incorrect) percentage values."""
    print("\n" + "=" * 65)
    print("REMOVING STALE INTERMEDIATE DATASETS")
    print("=" * 65)
    for fname in stale_list:
        fpath = os.path.join(processed_dir, fname)
        if os.path.exists(fpath):
            if dry_run:
                print(f"  [dry-run] Would delete: {fname}")
            else:
                os.remove(fpath)
                print(f"  [deleted] {fname}")
        else:
            print(f"  [skip]    {fname} (not found)")


# ── Step 10: Remove stale models ─────────────────────────────────────────────
def remove_stale_models(model_dir: str, dry_run: bool = False) -> None:
    """
    Delete .pkl model files trained on percentage-based (wrong) data.
    Evaluation/log files are also removed so there is no stale metric confusion.
    """
    model_dir = os.path.join(ROOT, "models")
    stale_patterns = ["lgbm_*.pkl", "rf_fertility.pkl",
                      "eval_regression*.csv", "eval_classification.txt",
                      "feature_importance.csv"]
    print("\n" + "=" * 65)
    print("REMOVING STALE MODELS (trained on percentage values)")
    print("=" * 65)
    for pattern in stale_patterns:
        for fpath in glob.glob(os.path.join(model_dir, pattern)):
            fname = os.path.basename(fpath)
            if dry_run:
                print(f"  [dry-run] Would delete: {fname}")
            else:
                os.remove(fpath)
                print(f"  [deleted] {fname}")


# ── Main ─────────────────────────────────────────────────────────────────────
def main(dry_run: bool = False):
    print("=" * 65)
    print("ICAR SOIL DATA PREPROCESSING PIPELINE")
    print("=" * 65)

    # 1. Load
    print("\n[STEP 1] Loading raw soilcard CSVs...")
    df = load_raw_soilcard(RAW_DIR)

    # 2. Normalise columns
    print("[STEP 2] Normalising column names...")
    df = normalise_columns(df)

    # 3. Convert % -> real values
    print("[STEP 3] Converting percentage distributions -> real ICAR values...")
    df = convert_percentages_to_real(df)

    # 4. Drop percentage columns
    print("[STEP 4] Dropping percentage/admin columns...")
    df = drop_percent_columns(df)

    # 5. Merge coordinates
    print("[STEP 5] Merging district coordinates...")
    df = merge_coordinates(df, COORDS_CSV)

    # 6. ICAR range clipping
    print("[STEP 6] Applying ICAR agronomic range clips...")
    df = apply_icar_ranges(df)

    # 7. Data cleaning
    print("[STEP 7] Cleaning data (dedup, median fill, no negatives)...")
    df = clean_data(df)

    # 8. Validate
    validate_dataset(df)

    # 9. Save canonical output
    if not dry_run:
        df.to_csv(OUTPUT_CSV, index=False)
        print(f"\n[OUTPUT] Saved: {OUTPUT_CSV}  ({len(df)} rows)")
    else:
        print(f"\n[dry-run] Would save to: {OUTPUT_CSV}")

    # 10. Remove stale intermediate datasets and models
    remove_stale_datasets(PROCESSED, STALE_DATASETS, dry_run=dry_run)
    remove_stale_models(os.path.join(ROOT, "models"), dry_run=dry_run)

    print("\n[DONE] Preprocessing complete.\n")
    return df


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="ICAR soil preprocessing pipeline.")
    ap.add_argument("--dry-run", action="store_true",
                    help="Show what would happen without writing/deleting files.")
    args = ap.parse_args()
    main(dry_run=args.dry_run)
