"""
data_ingestor.py
----------------
Utility for validating and ingesting user-uploaded CSV / Excel files
into the live soil dataset used for incremental model retraining.

Responsibilities
----------------
1. Accept a file path (CSV or XLSX/XLS).
2. Detect and remap common column name aliases to canonical names.
3. Validate that required columns exist and have sensible numeric values.
4. Deduplicate against the existing live CSV (by lat/lon/timestamp proximity).
5. Append valid rows to `data/processed/india_soil_live.csv`.
6. Return a summary dict with counts of accepted/rejected rows and reasons.

Called by the Django `upload_data` view.
"""

import os
import re
import hashlib
from datetime import datetime

import numpy as np
import pandas as pd

# ── Canonical column names ─────────────────────────────────────────────────────
#  The enriched training dataset uses these exact names.
CANONICAL_FEATURES = [
    "lat", "lon",
    "ph", "ec",
    "n", "p", "k",
    "organic_carbon",
    "s", "fe", "zn", "cu", "b", "mn",
    # Environmental (optional — filled from APIs during retrain if missing)
    "ndvi", "temperature", "rainfall",
    "elevation", "clay_pct", "sand_pct", "silt_pct",
    # Administrative (optional)
    "state", "district",
]

REQUIRED_COLUMNS = {"lat", "lon"}

# At least ONE soil chemistry column must be present
SOIL_CHEM_COLUMNS = {"ph", "ec", "n", "p", "k", "organic_carbon",
                     "s", "fe", "zn", "cu", "b", "mn"}

# ── Alias mapping  (aliases → canonical) ──────────────────────────────────────
#  Case-insensitive; strip whitespace before matching.
COLUMN_ALIASES: dict[str, str] = {
    # Latitude / Longitude
    "latitude":          "lat",
    "lat.":              "lat",
    "longitude":         "lon",
    "long":              "lon",
    "lng":               "lon",
    "lon.":              "lon",
    # pH
    "ph_value":          "ph",
    "soil_ph":           "ph",
    # EC
    "electrical_conductivity": "ec",
    "conductivity":      "ec",
    "ec_ds":             "ec",
    "ec (ds/m)":         "ec",
    # Nitrogen
    "nitrogen":          "n",
    "total_n":           "n",
    "n (kg/ha)":         "n",
    # Phosphorus
    "phosphorus":        "p",
    "phosphorous":       "p",
    "p (kg/ha)":         "p",
    # Potassium
    "potassium":         "k",
    "k (kg/ha)":         "k",
    # Organic carbon
    "oc":                "organic_carbon",
    "organic carbon":    "organic_carbon",
    "org_carbon":        "organic_carbon",
    "org. carbon":       "organic_carbon",
    # Sulphur
    "sulphur":           "s",
    "sulfur":            "s",
    "s (ppm)":           "s",
    # Micro-nutrients
    "iron":              "fe",
    "fe (ppm)":          "fe",
    "zinc":              "zn",
    "zn (ppm)":          "zn",
    "copper":            "cu",
    "cu (ppm)":          "cu",
    "boron":             "b",
    "b (ppm)":           "b",
    "manganese":         "mn",
    "mn (ppm)":          "mn",
    # Environmental
    "ndvi_value":        "ndvi",
    "temp":              "temperature",
    "temperature_c":     "temperature",
    "temp_c":            "temperature",
    "rain":              "rainfall",
    "rainfall_mm":       "rainfall",
    "precip":            "rainfall",
    "elev":              "elevation",
    "elevation_m":       "elevation",
    "altitude":          "elevation",
    "clay":              "clay_pct",
    "clay_%":            "clay_pct",
    "sand":              "sand_pct",
    "sand_%":            "sand_pct",
    "silt":              "silt_pct",
    "silt_%":            "silt_pct",
    # Administrative
    "state_name":        "state",
    "district_name":     "district",
    "block":             "district",
}

# ── ICAR-aligned value range guards ───────────────────────────────────────────
#
# These ranges mirror preprocessing.py::ICAR_RANGES and train.py::ICAR_RANGES.
# Uploaded sensor data MUST be in real agricultural units, NOT percentages.
# Any value outside these bounds is rejected so the training set stays clean.
#
# Units:
#   ph             : 0-14 (dimensionless)
#   ec             : dS/m
#   n, p, k        : kg/ha
#   organic_carbon : %
#   s, fe, zn, cu, b, mn : ppm (mg/kg)
#   ndvi           : -1 to 1
#   temperature    : °C
#   rainfall       : mm/year
#   elevation      : m above sea level
#   clay/sand/silt : % (0-100)
COLUMN_RANGES: dict[str, tuple] = {
    "lat":            (6.5,   38.5),
    "lon":            (68.0,  97.5),
    # Soil chemistry — ICAR agronomic limits
    "ph":             (4.5,   9.0),
    "ec":             (0.0,   4.0),
    "n":              (0.0,   600.0),
    "p":              (0.0,   50.0),
    "k":              (0.0,   500.0),
    "organic_carbon": (0.0,   3.0),
    "s":              (0.0,   60.0),
    "fe":             (0.0,   100.0),
    "zn":             (0.0,   20.0),
    "cu":             (0.0,   15.0),
    "b":              (0.0,   5.0),
    "mn":             (0.0,   50.0),
    # Environmental
    "ndvi":           (-1.0,  1.0),
    "temperature":    (-10.0, 55.0),
    "rainfall":       (0.0,   10000.0),
    "elevation":      (-500.0, 9000.0),
    "clay_pct":       (0.0,   100.0),
    "sand_pct":       (0.0,   100.0),
    "silt_pct":       (0.0,   100.0),
}


# ── Helpers ────────────────────────────────────────────────────────────────────

def _normalise_col(name: str) -> str:
    """Lower-case, strip, collapse spaces → used for alias matching."""
    return re.sub(r"\s+", " ", str(name).strip().lower())


def _remap_columns(df: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    """
    Rename columns using COLUMN_ALIASES.
    Returns (renamed_df, list_of_rename_notes).
    """
    rename_map = {}
    notes = []
    for col in df.columns:
        norm = _normalise_col(col)
        if norm in COLUMN_ALIASES:
            canonical = COLUMN_ALIASES[norm]
            if canonical not in df.columns:          # avoid collision
                rename_map[col] = canonical
                if col != canonical:
                    notes.append(f"'{col}' → '{canonical}'")
    if rename_map:
        df = df.rename(columns=rename_map)
    return df, notes


def _validate_row(row: pd.Series, errors: list[str]) -> bool:
    """Return True if row passes all guards; append reasons to errors."""
    ok = True
    for col, (lo, hi) in COLUMN_RANGES.items():
        if col not in row.index:
            continue
        val = row[col]
        if pd.isna(val):
            continue                               # NaN is allowed; APIs fill it
        try:
            v = float(val)
        except (ValueError, TypeError):
            errors.append(f"{col}='{val}' not numeric")
            ok = False
            continue
        if not (lo <= v <= hi):
            errors.append(f"{col}={v:.4g} out of range [{lo}, {hi}]")
            ok = False
    return ok


# ── Public API ────────────────────────────────────────────────────────────────

def ingest_file(
    file_path: str,
    live_csv_path: str,
    overwrite_live: bool = False,
) -> dict:
    """
    Read *file_path* (CSV or Excel), validate rows, and append accepted rows
    to *live_csv_path*.

    Parameters
    ----------
    file_path      : Path to the uploaded CSV/XLSX/XLS file.
    live_csv_path  : Path to `india_soil_live.csv`.
    overwrite_live : If True, replace the live CSV rather than append to it.

    Returns
    -------
    dict with keys:
        total_rows, accepted, rejected, skipped_duplicate,
        column_renames, rejected_details, snapshot_path
    """
    result = {
        "total_rows":        0,
        "accepted":          0,
        "rejected":          0,
        "skipped_duplicate": 0,
        "column_renames":    [],
        "rejected_details":  [],
        "snapshot_path":     None,
        "columns_found":     [],
        "columns_missing":   [],
    }

    # ── 1. Read file ──────────────────────────────────────────────────────────
    ext = os.path.splitext(file_path)[1].lower()
    try:
        if ext in (".xlsx", ".xls"):
            df = pd.read_excel(file_path, engine="openpyxl" if ext == ".xlsx" else "xlrd")
        elif ext == ".csv":
            df = pd.read_csv(file_path)
        else:
            raise ValueError(f"Unsupported file type: {ext}. Use .csv, .xlsx, or .xls")
    except Exception as e:
        raise ValueError(f"Could not read file: {e}") from e

    if df.empty:
        raise ValueError("Uploaded file contains no data rows.")

    result["total_rows"] = len(df)

    # ── 2. Remap columns ──────────────────────────────────────────────────────
    df, renames = _remap_columns(df)
    result["column_renames"] = renames

    # ── 3. Check required columns ─────────────────────────────────────────────
    missing_required = REQUIRED_COLUMNS - set(df.columns)
    if missing_required:
        raise ValueError(
            f"Required column(s) missing: {missing_required}. "
            f"File has: {list(df.columns)}"
        )

    has_soil_chem = bool(SOIL_CHEM_COLUMNS & set(df.columns))
    if not has_soil_chem:
        raise ValueError(
            "No soil chemistry columns found "
            f"({', '.join(sorted(SOIL_CHEM_COLUMNS))}). "
            "Please include at least one."
        )

    # Report which canonical columns were found / absent
    result["columns_found"]   = sorted(set(CANONICAL_FEATURES) & set(df.columns))
    result["columns_missing"]  = sorted(set(CANONICAL_FEATURES) - set(df.columns))

    # ── 4. Coerce numeric columns ─────────────────────────────────────────────
    numeric_candidates = [c for c in COLUMN_RANGES if c in df.columns]
    for col in numeric_candidates:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    # ── 5. Load existing live data for deduplication ──────────────────────────
    existing_keys: set[str] = set()
    if os.path.exists(live_csv_path) and not overwrite_live:
        try:
            df_live = pd.read_csv(live_csv_path)
            for _, r in df_live.iterrows():
                lat_r  = round(float(r.get("lat", 0)), 4)
                lon_r  = round(float(r.get("lon", 0)), 4)
                ts_raw = str(r.get("timestamp", ""))[:10]   # date part only
                existing_keys.add(f"{lat_r}|{lon_r}|{ts_raw}")
        except Exception:
            pass   # ignore; dedup won't work but ingestion continues

    # ── 6. Validate each row ──────────────────────────────────────────────────
    accepted_rows  = []
    today_str      = datetime.now().strftime("%Y-%m-%d")

    for idx, row in df.iterrows():
        # Dedup check
        lat_r = round(float(row.get("lat", 0)), 4)
        lon_r = round(float(row.get("lon", 0)), 4)
        ts_raw = str(row.get("timestamp", today_str))[:10]
        key = f"{lat_r}|{lon_r}|{ts_raw}"
        if key in existing_keys:
            result["skipped_duplicate"] += 1
            continue

        row_errors: list[str] = []
        if not _validate_row(row, row_errors):
            result["rejected"] += 1
            result["rejected_details"].append({"row": int(idx) + 2, "reasons": row_errors})
            continue

        # Stamp a timestamp if absent
        row_dict = row.to_dict()
        row_dict.setdefault("timestamp", datetime.now().isoformat())
        accepted_rows.append(row_dict)
        existing_keys.add(key)

    result["accepted"] = len(accepted_rows)

    # ── 7. Append to live CSV ─────────────────────────────────────────────────
    if accepted_rows:
        df_new = pd.DataFrame(accepted_rows)

        if overwrite_live or not os.path.exists(live_csv_path):
            df_new.to_csv(live_csv_path, index=False)
        else:
            df_existing = pd.read_csv(live_csv_path)
            df_combined = pd.concat([df_existing, df_new], ignore_index=True)
            df_combined.to_csv(live_csv_path, index=False)

        # Save a dated snapshot for auditability
        snap_dir  = os.path.dirname(live_csv_path)
        ts_stamp  = datetime.now().strftime("%Y%m%d_%H%M%S")
        snap_path = os.path.join(snap_dir, f"upload_snapshot_{ts_stamp}.csv")
        df_new.to_csv(snap_path, index=False)
        result["snapshot_path"] = snap_path

    return result
