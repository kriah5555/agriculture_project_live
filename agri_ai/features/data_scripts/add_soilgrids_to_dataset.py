"""
add_soilgrids_to_dataset.py
----------------------------
Reads final_dataset_with_elev.csv, fetches clay %, sand %, and silt %
from the SoilGrids v2 REST API (no API key required) for the topsoil
layer (0-5 cm depth at each district centroid), and saves the output.

SoilGrids API docs: https://rest.isric.org/soilgrids/v2.0/docs

Usage:
    python add_soilgrids_to_dataset.py           # full run
    python add_soilgrids_to_dataset.py --test    # first 10 rows only
    python add_soilgrids_to_dataset.py --check   # validate saved output
"""

import sys
import time
import os
import requests
import pandas as pd

# ── Configuration ─────────────────────────────────────────────────────────────
INPUT_CSV   = "data/processed/final_dataset_with_elev.csv"
OUTPUT_CSV  = "data/processed/final_dataset_enriched.csv"
TEST_CSV    = "data/processed/final_dataset_enriched_test.csv"

API_URL     = "https://rest.isric.org/soilgrids/v2.0/properties/query"
PROPERTIES  = ["clay", "sand", "silt"]
DEPTH       = "0-5cm"      # topsoil
VALUE       = "mean"
TIMEOUT     = 60
DELAY_SECS  = 2.0          # SoilGrids has rate limits — stay conservative
TEST_ROWS   = 10

# SoilGrids returns values in g/kg; divide by 10 to get %
SCALE_FACTOR = 10.0


# ── Fetch soil texture ────────────────────────────────────────────────────────

def get_soil_texture(lat: float, lon: float) -> dict:
    """
    Returns a dict with clay_pct, sand_pct, silt_pct (0-100 scale)
    for the 0-5 cm depth layer.
    Returns None values on failure.
    """
    result = {"clay_pct": None, "sand_pct": None, "silt_pct": None}
    try:
        params = {
            "lat":   lat,
            "lon":   lon,
            "depth": DEPTH,
            "value": VALUE,
        }
        # SoilGrids expects property as repeated param
        for prop in PROPERTIES:
            params[f"property"] = prop   # override keeps last only for dict
        # Use a list of tuples for repeated params
        param_list = [("lat", lat), ("lon", lon), ("depth", DEPTH), ("value", VALUE)]
        for prop in PROPERTIES:
            param_list.append(("property", prop))

        response = requests.get(API_URL, params=param_list, timeout=TIMEOUT)
        response.raise_for_status()
        data = response.json()

        for layer in data.get("properties", {}).get("layers", []):
            name = layer.get("name")
            if name not in PROPERTIES:
                continue
            for depth_info in layer.get("depths", []):
                if depth_info.get("label") == DEPTH:
                    raw = depth_info.get("values", {}).get(VALUE)
                    if raw is not None:
                        result[f"{name}_pct"] = round(raw / SCALE_FACTOR, 2)
        return result

    except requests.exceptions.Timeout:
        print(f"  [Timeout] SoilGrids for ({lat}, {lon})")
    except requests.exceptions.ConnectionError:
        print(f"  [ConnectionError] for ({lat}, {lon})")
    except requests.exceptions.HTTPError as e:
        print(f"  [HTTPError] {e} for ({lat}, {lon})")
    except Exception as e:
        print(f"  [Error in get_soil_texture]: {e}")
    return result


# ── Enrich ────────────────────────────────────────────────────────────────────

CHECKPOINT_EVERY = 50   # save progress every N rows


def get_soil_texture_with_retry(lat, lon, retries=3, backoff=5):
    """Wrap get_soil_texture with retry-backoff for 503/connection errors."""
    for attempt in range(1, retries + 1):
        result = get_soil_texture(lat, lon)
        if any(v is not None for v in result.values()):
            return result
        if attempt < retries:
            print(f"  [Retry {attempt}/{retries}] waiting {backoff}s...")
            time.sleep(backoff)
            backoff *= 2
    return result


def enrich_with_soil_texture(df: pd.DataFrame, output_path: str) -> pd.DataFrame:
    total   = len(df)
    success = 0
    failed  = 0

    # ── Resume from checkpoint if it exists ──────────────────────────────────
    checkpoint_path = output_path.replace(".csv", "_checkpoint.csv")
    if os.path.exists(checkpoint_path):
        done_df  = pd.read_csv(checkpoint_path)
        done_ids = set(done_df.index.tolist()) if "orig_idx" not in done_df.columns \
                   else set(done_df["orig_idx"].tolist())
        print(f"  [RESUME] Checkpoint found: {len(done_df)} rows already done.")
    else:
        done_df  = pd.DataFrame()
        done_ids = set()

    print(f"\nFetching soil texture (clay/sand/silt) for {total} locations...\n")

    batch_rows = []

    for i, row in df.iterrows():
        row_num = list(df.index).index(i) + 1

        # skip already processed rows
        if i in done_ids:
            print(f"[{row_num}/{total}] SKIP (already done)")
            continue

        lat, lon = row["lat"], row["lon"]
        label    = f"{row.get('district', '?')}, {row.get('state', '?')}"

        print(f"[{row_num}/{total}] ({lat:.4f}, {lon:.4f}) - {label}", end="\r")

        texture = get_soil_texture_with_retry(lat, lon)

        new_row = row.to_dict()
        new_row.update({"orig_idx": i,
                        "clay_pct": texture["clay_pct"],
                        "sand_pct": texture["sand_pct"],
                        "silt_pct": texture["silt_pct"]})
        batch_rows.append(new_row)

        if all(v is not None for v in texture.values()):
            print(f"[{row_num}/{total}] OK  "
                  f"clay={texture['clay_pct']:.1f}%  "
                  f"sand={texture['sand_pct']:.1f}%  "
                  f"silt={texture['silt_pct']:.1f}%  - {label}")
            success += 1
        else:
            print(f"[{row_num}/{total}] PARTIAL - {label}")
            failed += 1

        # ── Save checkpoint every N rows ─────────────────────────────────────
        if len(batch_rows) % CHECKPOINT_EVERY == 0:
            checkpoint_df = pd.concat(
                [done_df, pd.DataFrame(batch_rows)], ignore_index=True
            )
            checkpoint_df.to_csv(checkpoint_path, index=False)
            print(f"  [Checkpoint saved: {len(checkpoint_df)} rows]")

        time.sleep(DELAY_SECS)

    # Merge batch with previously-done rows
    all_rows_df = pd.concat([done_df, pd.DataFrame(batch_rows)], ignore_index=True)

    # Rebuild the output with original column order
    output_df = df.copy()
    merged    = output_df.merge(
        all_rows_df[["orig_idx", "clay_pct", "sand_pct", "silt_pct"]],
        left_index=True, right_on="orig_idx", how="left"
    ).drop(columns=["orig_idx"], errors="ignore")

    merged.to_csv(output_path, index=False)

    # Remove checkpoint now that we have the final file
    if os.path.exists(checkpoint_path):
        os.remove(checkpoint_path)
        print(f"  [Checkpoint removed — final file saved]")

    print(f"\n{'='*50}")
    print("SOIL TEXTURE ENRICHMENT SUMMARY")
    print(f"{'='*50}")
    print(f"  Total      : {total}")
    print(f"  Full OK    : {success}")
    print(f"  Partial/Fail: {failed}")
    if total > 0:
        print(f"  Coverage   : {success/total*100:.1f}%")
    print(f"  Saved to   : {output_path}")
    print(f"{'='*50}\n")
    return merged


# ── Validate ──────────────────────────────────────────────────────────────────

def check_output(path: str):
    if not os.path.exists(path):
        print(f"[ERROR] File not found: {path}")
        return
    df    = pd.read_csv(path)
    total = len(df)
    print(f"\n{'='*50}")
    print(f"VALIDATION: {path}")
    print(f"{'='*50}")
    print(f"  Rows: {total}  |  Columns: {df.columns.tolist()}")

    for col in ["clay_pct", "sand_pct", "silt_pct"]:
        if col not in df.columns:
            print(f"  [ERROR] Column '{col}' missing.")
            continue
        present = df[col].notna().sum()
        vals    = df[col].dropna()
        print(f"\n  {col.upper()}")
        print(f"    Present : {present} / {total} ({present/total*100:.1f}%)")
        if not vals.empty:
            print(f"    Min/Max : {vals.min():.1f}% / {vals.max():.1f}%")
            print(f"    Mean    : {vals.mean():.1f}%")

    print(f"\n  Sample (first 5 with full data):")
    cols = [c for c in ["state","district","clay_pct","sand_pct","silt_pct","elevation"]
            if c in df.columns]
    filled = df[df["clay_pct"].notna()][cols].head(5)
    print(filled.to_string(index=False))
    print(f"{'='*50}\n")


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
    check_output(output_path)


if __name__ == "__main__":
    main()
