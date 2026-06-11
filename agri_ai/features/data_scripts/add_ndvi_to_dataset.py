"""
add_ndvi_to_dataset.py
----------------------
Reads the soil CSV, fetches NDVI via GEE for each row,
appends the NDVI column, and saves the enriched dataset.

Usage:
    python add_ndvi_to_dataset.py           # Full run (all 621 rows)
    python add_ndvi_to_dataset.py --test    # Test run (first 10 rows only)
    python add_ndvi_to_dataset.py --check   # Validate an already-saved output
"""

import sys
import time
import pandas as pd
from datetime import datetime, timedelta
from ndvi import get_ndvi

# ── Configuration ─────────────────────────────────────────────────────────────
INPUT_CSV   = "data/processed/india_soil_geo.csv"
OUTPUT_CSV  = "data/processed/soil_with_ndvi.csv"
TEST_CSV    = "data/processed/soil_with_ndvi_test.csv"

end_dt = datetime.now() - timedelta(days=7)
start_dt = end_dt - timedelta(days=365)
START_DATE = start_dt.strftime("%Y-%m-%d")
END_DATE = end_dt.strftime("%Y-%m-%d")
DELAY_SECS  = 1          # Pause between API calls to avoid rate limits
TEST_ROWS   = 10         # Number of rows to process in --test mode


# ── Helper: Fetch NDVI for a DataFrame ───────────────────────────────────────
def enrich_with_ndvi(df: pd.DataFrame, output_path: str):
    total = len(df)
    print(f"\nProcessing {total} rows | {START_DATE} to {END_DATE}\n")

    ndvi_values = []
    success, failed = 0, 0

    for i, row in df.iterrows():
        row_num = list(df.index).index(i) + 1
        lat, lon = row["lat"], row["lon"]
        label = f"{row.get('district', '?')}, {row.get('state', '?')}"

        print(f"[{row_num}/{total}] ({lat:.4f}, {lon:.4f}) - {label}")
        ndvi = get_ndvi(lat, lon, START_DATE, END_DATE)
        ndvi_values.append(ndvi)

        if ndvi is not None:
            print(f"  [OK]   NDVI = {ndvi:.4f}")
            success += 1
        else:
            print(f"  [FAIL] NDVI = None")
            failed += 1

        time.sleep(DELAY_SECS)

    df = df.copy()
    df["ndvi"] = ndvi_values
    df.to_csv(output_path, index=False)

    print(f"\n{'='*45}")
    print("NDVI ENRICHMENT SUMMARY")
    print(f"{'='*45}")
    print(f"  Total rows      : {total}")
    print(f"  [OK] Successful : {success}")
    print(f"  [FAIL] Failed   : {failed}")
    print(f"  Coverage        : {success/total*100:.1f}%")
    print(f"  Output saved    : {output_path}")
    print(f"{'='*45}\n")

    return df


# ── Helper: Validate saved output ────────────────────────────────────────────
def check_output(path: str):
    print(f"\n{'='*45}")
    print(f"VALIDATION REPORT: {path}")
    print(f"{'='*45}")

    try:
        df = pd.read_csv(path)
    except FileNotFoundError:
        print(f"[ERROR] File not found: {path}")
        print("  Run without --check first to generate the file.")
        return

    if "ndvi" not in df.columns:
        print("[ERROR] No 'ndvi' column found in the file.")
        return

    total   = len(df)
    present = df["ndvi"].notna().sum()
    missing = df["ndvi"].isna().sum()

    print(f"  Total rows       : {total}")
    print(f"  NDVI present     : {present} ({present/total*100:.1f}%)")
    print(f"  NDVI missing     : {missing} ({missing/total*100:.1f}%)")

    ndvi_col = df["ndvi"].dropna()
    print(f"\n  NDVI Statistics:")
    print(f"    Min    : {ndvi_col.min():.4f}")
    print(f"    Max    : {ndvi_col.max():.4f}")
    print(f"    Mean   : {ndvi_col.mean():.4f}")
    print(f"    Median : {ndvi_col.median():.4f}")

    # Expected NDVI range for Indian agricultural land
    EXPECTED_MIN = -0.1
    EXPECTED_MAX = 0.9
    out_of_range = ndvi_col[(ndvi_col < EXPECTED_MIN) | (ndvi_col > EXPECTED_MAX)]

    print(f"\n  Plausibility Check (expected {EXPECTED_MIN} to {EXPECTED_MAX}):")
    if out_of_range.empty:
        print("  [OK] All NDVI values are within the expected range.")
    else:
        print(f"  [WARN] {len(out_of_range)} values are out of the expected range:")
        suspect_rows = df[df["ndvi"].isin(out_of_range)][["state","district","lat","lon","ndvi"]]
        print(suspect_rows.to_string(index=False))

    # Show a sample preview
    print(f"\n  Sample rows (first 5 with NDVI):")
    preview_cols = [c for c in ["state", "district", "lat", "lon", "ph", "ndvi"] if c in df.columns]
    print(df[df["ndvi"].notna()][preview_cols].head(5).to_string(index=False))

    # Soil correlation hint
    print(f"\n  Correlation of NDVI with soil parameters:")
    soil_cols = [c for c in ["ph", "ec", "n", "p", "k", "organic_carbon"] if c in df.columns]
    for col in soil_cols:
        corr = df["ndvi"].corr(df[col])
        direction = "+" if corr >= 0 else "-"
        print(f"    ndvi vs {col:<15}: {corr:+.4f}  ({direction})")

    print(f"\n{'='*45}\n")


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    args = sys.argv[1:]

    # --check mode: validate already-saved output
    if "--check" in args:
        # Try full output first, then test output
        import os
        path = OUTPUT_CSV if os.path.exists(OUTPUT_CSV) else TEST_CSV
        check_output(path)
        return

    # Load dataset
    print(f"Loading: {INPUT_CSV}")
    df = pd.read_csv(INPUT_CSV)
    df = df.dropna(subset=["lat", "lon"]).reset_index(drop=True)

    # --test mode: process only first N rows
    if "--test" in args:
        df = df.head(TEST_ROWS).copy()
        output_path = TEST_CSV
        print(f"[TEST MODE] Processing first {TEST_ROWS} rows only.")
    else:
        output_path = OUTPUT_CSV
        print(f"[FULL MODE] Processing all {len(df)} rows.")

    result_df = enrich_with_ndvi(df, output_path)

    # Always run validation after enrichment
    check_output(output_path)


if __name__ == "__main__":
    main()
