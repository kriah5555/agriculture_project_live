"""
add_openlandmap_to_dataset.py
-----------------------------
Reads final_dataset_with_elev.csv, fetches clay %, sand %, and silt %
from Google Earth Engine (OpenLandMap datasets at 250m resolution)
for the topsoil layer (0cm depth), and saves the enriched output.

Usage:
    python add_openlandmap_to_dataset.py           # full run
    python add_openlandmap_to_dataset.py --test    # first 10 rows only
"""

import sys
import time
import os
import ee
import pandas as pd

# ── Configuration ─────────────────────────────────────────────────────────────
PROJECT_ID  = "soilmain"
INPUT_CSV   = "data/processed/final_dataset_with_elev.csv"
OUTPUT_CSV  = "data/processed/final_dataset_enriched.csv"
TEST_CSV    = "data/processed/final_dataset_enriched_test.csv"
SCALE_M     = 250                   # Native resolution for OpenLandMap
DELAY_SECS  = 0.2
TEST_ROWS   = 10

# OpenLandMap datasets are provided at 6 depths: 0, 10, 30, 60, 100, 200 cm
# We use b0 (0cm / surface layer) to match top soil.
DATASETS = {
    "clay": "OpenLandMap/SOL/SOL_CLAY-WFRACTION_USDA-3A1A1A_M/v02",
    "sand": "OpenLandMap/SOL/SOL_SAND-WFRACTION_USDA-3A1A1A_M/v02",
    # Note: OpenLandMap provides clay and sand directly. Silt can be computed as:
    # 100 - clay - sand (since clay+sand+silt = 100%)
}

def init_gee():
    try:
        ee.data.getInfo("projects/earthengine-public/assets/users")
    except ee.EEException:
        ee.Initialize(project=PROJECT_ID)

def get_soil_texture_gee(lat: float, lon: float) -> dict:
    """Return clay, sand, silt % derived from OpenLandMap at 0cm depth."""
    try:
        point = ee.Geometry.Point([lon, lat])
        
        clay_img = ee.Image(DATASETS["clay"]).select('b0')
        sand_img = ee.Image(DATASETS["sand"]).select('b0')
        
        clay_stat = clay_img.reduceRegion(reducer=ee.Reducer.mean(), geometry=point, scale=SCALE_M).getInfo()
        sand_stat = sand_img.reduceRegion(reducer=ee.Reducer.mean(), geometry=point, scale=SCALE_M).getInfo()
        
        clay_val = clay_stat.get('b0')
        sand_val = sand_stat.get('b0')
        
        if clay_val is None or sand_val is None:
            return {"clay_pct": None, "sand_pct": None, "silt_pct": None}
        
        silt_val = max(0, 100 - clay_val - sand_val)
        
        return {
            "clay_pct": round(clay_val, 2),
            "sand_pct": round(sand_val, 2),
            "silt_pct": round(silt_val, 2)
        }
    except Exception as e:
        print(f"  [Error in GEE texture fetching]: {e}")
        return {"clay_pct": None, "sand_pct": None, "silt_pct": None}

def enrich_with_soil_texture(df: pd.DataFrame, output_path: str) -> pd.DataFrame:
    init_gee()
    total   = len(df)
    success = 0
    failed  = 0
    
    clay_list, sand_list, silt_list = [], [], []

    print(f"\nFetching OpenLandMap soil texture (clay/sand/silt) via GEE for {total} locations...\n")

    for i, row in df.iterrows():
        row_num = list(df.index).index(i) + 1
        lat, lon = row["lat"], row["lon"]
        label    = f"{row.get('district', '?')}, {row.get('state', '?')}"

        print(f"[{row_num}/{total}] ({lat:.4f}, {lon:.4f}) - {label}", end="\r")

        texture = get_soil_texture_gee(lat, lon)
        clay_list.append(texture["clay_pct"])
        sand_list.append(texture["sand_pct"])
        silt_list.append(texture["silt_pct"])

        if all(v is not None for v in texture.values()):
            print(f"[{row_num}/{total}] OK  "
                  f"clay={texture['clay_pct']:.1f}%  "
                  f"sand={texture['sand_pct']:.1f}%  "
                  f"silt={texture['silt_pct']:.1f}%  - {label}")
            success += 1
        else:
            print(f"[{row_num}/{total}] PARTIAL / FAIL - {label}")
            failed += 1

        time.sleep(DELAY_SECS)

    df = df.copy()
    df["clay_pct"] = clay_list
    df["sand_pct"] = sand_list
    df["silt_pct"] = silt_list
    df.to_csv(output_path, index=False)

    print(f"\n{'='*50}")
    print("SOIL TEXTURE ENRICHMENT SUMMARY (GEE)")
    print(f"{'='*50}")
    print(f"  Total      : {total}")
    print(f"  Success    : {success}")
    print(f"  Failed     : {failed}")
    print(f"  Coverage   : {success/total*100:.1f}%")
    print(f"  Saved to   : {output_path}")
    print(f"{'='*50}\n")
    return df

def main():
    args = sys.argv[1:]

    print(f"Loading: {INPUT_CSV}")
    try:
        df = pd.read_csv(INPUT_CSV)
    except FileNotFoundError:
        print(f"[ERROR] Not found: {INPUT_CSV}")
        print("  Run add_elevation_to_dataset.py first.")
        return

    df = df.dropna(subset=["lat", "lon"]).reset_index(drop=True)

    if "--test" in args:
        df          = df.head(TEST_ROWS).copy()
        output_path = TEST_CSV
        print(f"[TEST MODE] Processing first {TEST_ROWS} rows.")
    else:
        output_path = OUTPUT_CSV
        print(f"[FULL MODE] Processing all {len(df)} rows.")

    result = enrich_with_soil_texture(df, output_path)

if __name__ == "__main__":
    main()
