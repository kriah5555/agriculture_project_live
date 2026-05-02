"""
add_weather_to_dataset.py
--------------------------
Reads soil_with_ndvi.csv, fetches weather data (temperature + rainfall)
from the NASA POWER API for each row, and saves enriched output as final_dataset.csv.

Usage:
    python add_weather_to_dataset.py            # Full run (all rows)
    python add_weather_to_dataset.py --test     # Test mode (first 50 rows)
    python add_weather_to_dataset.py --check    # Validate already-saved output
"""

import sys
import time
import pandas as pd
from weather import get_weather

# ── Configuration ─────────────────────────────────────────────────────────────
INPUT_CSV   = "data/processed/soil_with_ndvi.csv"
OUTPUT_CSV  = "data/processed/final_dataset.csv"
TEST_CSV    = "data/processed/final_dataset_test.csv"
DELAY_SECS  = 1      # Pause between API calls
TEST_ROWS   = 50     # Number of rows in --test mode


# ── Helper: Enrich DataFrame with weather data ────────────────────────────────
def enrich_with_weather(df: pd.DataFrame, output_path: str) -> pd.DataFrame:
    total = len(df)
    print(f"\nFetching weather for {total} locations (trailing 365 days)...\n")

    temp_list = []
    rain_list = []
    success, failed = 0, 0

    for i, row in df.iterrows():
        row_num = list(df.index).index(i) + 1
        lat, lon = row["lat"], row["lon"]
        label = f"{row.get('district', '?')}, {row.get('state', '?')}"

        print(f"[{row_num}/{total}] ({lat:.4f}, {lon:.4f}) - {label}")

        avg_temp, total_rain = get_weather(lat, lon)
        temp_list.append(avg_temp)
        rain_list.append(total_rain)

        if avg_temp is not None:
            print(f"  [OK]   Temp={avg_temp:.2f}C  Rain={total_rain:.1f}mm")
            success += 1
        else:
            print(f"  [FAIL] No weather data returned.")
            failed += 1

        time.sleep(DELAY_SECS)

    df = df.copy()
    df["temperature"] = temp_list
    df["rainfall"]    = rain_list
    df.to_csv(output_path, index=False)

    print(f"\n{'='*45}")
    print("WEATHER ENRICHMENT SUMMARY")
    print(f"{'='*45}")
    print(f"  Total rows      : {total}")
    print(f"  [OK] Successful : {success}")
    print(f"  [FAIL] Failed   : {failed}")
    print(f"  Coverage        : {success / total * 100:.1f}%")
    print(f"  Output saved    : {output_path}")
    print(f"{'='*45}\n")

    return df


# ── Helper: Validate saved output ────────────────────────────────────────────
def check_output(path: str):
    import os
    print(f"\n{'='*45}")
    print(f"VALIDATION REPORT: {path}")
    print(f"{'='*45}")

    if not os.path.exists(path):
        print(f"[ERROR] File not found: {path}")
        print("  Run the script without --check to generate the file first.")
        return

    df = pd.read_csv(path)
    total = len(df)

    for col in ["temperature", "rainfall"]:
        if col not in df.columns:
            print(f"[ERROR] Column '{col}' not found in the file.")
            return

        present = df[col].notna().sum()
        missing = df[col].isna().sum()
        vals    = df[col].dropna()

        print(f"\n  Column: {col.upper()}")
        print(f"  Present  : {present} / {total} ({present/total*100:.1f}%)")
        print(f"  Missing  : {missing}")
        print(f"  Min      : {vals.min():.3f}")
        print(f"  Max      : {vals.max():.3f}")
        print(f"  Mean     : {vals.mean():.3f}")

    # Plausibility checks
    print("\n  Plausibility checks:")
    temp_bad = df[(df["temperature"].notna()) & ((df["temperature"] < -10) | (df["temperature"] > 50))]
    rain_bad = df[(df["rainfall"].notna()) & ((df["rainfall"] < 0) | (df["rainfall"] > 5000))]

    print(f"  Temperature in [-10, 50] C  : "
          f"{'[OK] All valid' if temp_bad.empty else f'[WARN] {len(temp_bad)} suspect rows'}")
    print(f"  Rainfall in [0, 5000] mm    : "
          f"{'[OK] All valid' if rain_bad.empty else f'[WARN] {len(rain_bad)} suspect rows'}")

    # Correlations with soil & NDVI columns
    print("\n  Correlation with temperature:")
    corr_cols = [c for c in ["ph", "ec", "n", "p", "k", "organic_carbon", "ndvi"] if c in df.columns]
    for col in corr_cols:
        corr = df["temperature"].corr(df[col])
        print(f"    temperature vs {col:<15}: {corr:+.4f}")

    print("\n  Correlation with rainfall:")
    for col in corr_cols:
        corr = df["rainfall"].corr(df[col])
        print(f"    rainfall    vs {col:<15}: {corr:+.4f}")

    # Preview
    print("\n  Sample rows (first 5 with data):")
    preview_cols = [c for c in ["state", "district", "lat", "lon", "ndvi", "temperature", "rainfall"]
                    if c in df.columns]
    filled = df[df["temperature"].notna()][preview_cols].head(5)
    print(filled.to_string(index=False))
    print(f"\n{'='*45}\n")


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    args = sys.argv[1:]

    # --check mode: validate an already-saved file
    if "--check" in args:
        import os
        path = OUTPUT_CSV if os.path.exists(OUTPUT_CSV) else TEST_CSV
        check_output(path)
        return

    # Load input dataset
    print(f"Loading dataset: {INPUT_CSV}")
    try:
        df = pd.read_csv(INPUT_CSV)
    except FileNotFoundError:
        print(f"[ERROR] File not found: {INPUT_CSV}")
        print("  Run add_ndvi_to_dataset.py first to generate this file.")
        return

    df = df.dropna(subset=["lat", "lon"]).reset_index(drop=True)

    # --test mode
    if "--test" in args:
        df = df.head(TEST_ROWS).copy()
        output_path = TEST_CSV
        print(f"[TEST MODE] Processing first {TEST_ROWS} rows.")
    else:
        output_path = OUTPUT_CSV
        print(f"[FULL MODE] Processing all {len(df)} rows.")

    result_df = enrich_with_weather(df, output_path)
    check_output(output_path)


if __name__ == "__main__":
    main()
