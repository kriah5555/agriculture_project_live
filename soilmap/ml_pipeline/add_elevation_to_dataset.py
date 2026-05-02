"""
add_elevation_to_dataset.py
---------------------------
Reads final_dataset.csv, fetches SRTM elevation (metres) from Google Earth
Engine for every district centroid, and saves the enriched file.

Usage:
    python add_elevation_to_dataset.py           # full run
    python add_elevation_to_dataset.py --test    # first 10 rows only
    python add_elevation_to_dataset.py --check   # validate saved output
"""

import sys
import time
import os
import ee
import pandas as pd

# ── Configuration ─────────────────────────────────────────────────────────────
PROJECT_ID  = "soilmain"
INPUT_CSV   = "data/processed/final_dataset.csv"
OUTPUT_CSV  = "data/processed/final_dataset_with_elev.csv"
TEST_CSV    = "data/processed/final_dataset_with_elev_test.csv"
COLLECTION  = "USGS/SRTMGL1_003"   # 30 m SRTM DEM, global coverage
SCALE_M     = 30                    # native resolution
DELAY_SECS  = 0.3                   # GEE point queries are fast
TEST_ROWS   = 10


# ── Earth Engine init ─────────────────────────────────────────────────────────

def init_gee():
    try:
        ee.data.getInfo("projects/earthengine-public/assets/users")
    except ee.EEException:
        ee.Initialize(project=PROJECT_ID)


# ── Elevation fetch ───────────────────────────────────────────────────────────

def get_elevation(lat: float, lon: float) -> float | None:
    """Return SRTM elevation in metres for a given point."""
    try:
        point  = ee.Geometry.Point([lon, lat])
        srtm   = ee.Image(COLLECTION)
        stats  = srtm.select("elevation").reduceRegion(
            reducer  = ee.Reducer.mean(),
            geometry = point,
            scale    = SCALE_M,
        ).getInfo()
        val = stats.get("elevation")
        return round(val, 2) if val is not None else None
    except Exception as e:
        print(f"  [Error in get_elevation]: {e}")
        return None


# ── Enrich ────────────────────────────────────────────────────────────────────

def enrich_with_elevation(df: pd.DataFrame, output_path: str) -> pd.DataFrame:
    init_gee()
    total                = len(df)
    elev_list            = []
    success, failed      = 0, 0

    print(f"\nFetching elevation for {total} locations...\n")

    for i, row in df.iterrows():
        row_num = list(df.index).index(i) + 1
        lat, lon = row["lat"], row["lon"]
        label    = f"{row.get('district', '?')}, {row.get('state', '?')}"

        print(f"[{row_num}/{total}] ({lat:.4f}, {lon:.4f}) - {label}", end="\r")

        elev = get_elevation(lat, lon)
        elev_list.append(elev)

        if elev is not None:
            print(f"[{row_num}/{total}] OK   elev={elev:.1f} m  - {label}")
            success += 1
        else:
            print(f"[{row_num}/{total}] FAIL              - {label}")
            failed += 1

        time.sleep(DELAY_SECS)

    df = df.copy()
    df["elevation"] = elev_list
    df.to_csv(output_path, index=False)

    print(f"\n{'='*45}")
    print("ELEVATION ENRICHMENT SUMMARY")
    print(f"{'='*45}")
    print(f"  Total      : {total}")
    print(f"  Successful : {success}")
    print(f"  Failed     : {failed}")
    print(f"  Coverage   : {success/total*100:.1f}%")
    print(f"  Saved to   : {output_path}")
    print(f"{'='*45}\n")
    return df


# ── Validate ──────────────────────────────────────────────────────────────────

def check_output(path: str):
    if not os.path.exists(path):
        print(f"[ERROR] File not found: {path}")
        return
    df    = pd.read_csv(path)
    total = len(df)
    col   = "elevation"
    if col not in df.columns:
        print(f"[ERROR] Column '{col}' not found.")
        return
    present = df[col].notna().sum()
    vals    = df[col].dropna()
    print(f"\n{'='*45}")
    print(f"VALIDATION: {path}")
    print(f"{'='*45}")
    print(f"  Rows        : {total}")
    print(f"  Present     : {present} ({present/total*100:.1f}%)")
    print(f"  Min elevation : {vals.min():.1f} m")
    print(f"  Max elevation : {vals.max():.1f} m")
    print(f"  Mean elevation: {vals.mean():.1f} m")
    print(f"\n  Sample:")
    cols = [c for c in ["state", "district", "lat", "lon", "elevation"] if c in df.columns]
    print(df[df[col].notna()][cols].head(5).to_string(index=False))
    print(f"{'='*45}\n")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    args = sys.argv[1:]

    if "--check" in args:
        path = OUTPUT_CSV if os.path.exists(OUTPUT_CSV) else TEST_CSV
        check_output(path)
        return

    print(f"Loading: {INPUT_CSV}")
    try:
        df = pd.read_csv(INPUT_CSV)
    except FileNotFoundError:
        print(f"[ERROR] Not found: {INPUT_CSV}")
        return

    df = df.dropna(subset=["lat", "lon"]).reset_index(drop=True)

    if "--test" in args:
        df          = df.head(TEST_ROWS).copy()
        output_path = TEST_CSV
        print(f"[TEST MODE] Processing first {TEST_ROWS} rows.")
    else:
        output_path = OUTPUT_CSV
        print(f"[FULL MODE] Processing all {len(df)} rows.")

    result = enrich_with_elevation(df, output_path)
    check_output(output_path)


if __name__ == "__main__":
    main()
