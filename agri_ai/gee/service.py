"""
agri_ai/gee/service.py
======================
GEE service layer for SAR crop detection and NDVI timeline.

Public API:
  get_crop_map(lat, lon, radius_km, season)  → dict
  get_sar_timeline(polygon_coords, radius_km, season)  → dict

Authentication (in priority order):
  1. Service-account JSON key file (set SAR_GEE_SA_KEY env-var to path)
  2. Application Default Credentials (earthengine authenticate)

Set GEE_PROJECT env-var to your Google Cloud project ID.
"""

import ee
import os
import math
import logging
from datetime import datetime, timedelta
from pathlib import Path
from dotenv import dotenv_values

_ENV_FILE = Path(__file__).resolve().parent.parent.parent / ".env"

logger = logging.getLogger(__name__)

_GEE_AVAILABLE    = False
_GEE_INITIALIZED  = False
_GEE_INIT_SIG     = ""   # "project|sa_key" used in the last successful/failed init
_GEE_PROJECT      = ""
_SA_KEY_PATH      = ""
_RF_ASSET_ID      = ""


def _read_env() -> tuple[str, str, str]:
    """Read GEE config directly from .env file every time — no os.environ caching."""
    env = dotenv_values(_ENV_FILE)
    return (
        env.get("GEE_PROJECT", "")              or "",
        env.get("SAR_GEE_SA_KEY", "")           or "",
        env.get("GEE_RF_CLASSIFIER_ASSET", "")  or "",
    )


def _try_init_gee() -> bool:
    global _GEE_AVAILABLE, _GEE_INITIALIZED, _GEE_INIT_SIG
    global _GEE_PROJECT, _SA_KEY_PATH, _RF_ASSET_ID

    project, sa_key, rf_asset = _read_env()
    sig = f"{project}|{sa_key}"

    # Return cached result only if we already tried with these exact values
    if _GEE_INITIALIZED and sig == _GEE_INIT_SIG:
        return _GEE_AVAILABLE

    _GEE_INITIALIZED = True
    _GEE_INIT_SIG    = sig
    _GEE_PROJECT     = project
    _SA_KEY_PATH     = sa_key
    _RF_ASSET_ID     = rf_asset

    try:
        if sa_key and os.path.isfile(sa_key):
            credentials = ee.ServiceAccountCredentials(email=None, key_file=sa_key)
            ee.Initialize(credentials, project=project)
            logger.info("GEE initialised via service account key.")
        elif project:
            ee.Initialize(project=project)
            logger.info("GEE initialised via Application Default Credentials.")
        else:
            logger.warning("GEE_PROJECT not set in .env — GEE skipped.")
            _GEE_AVAILABLE = False
            return False
        _GEE_AVAILABLE = True
    except Exception as exc:
        logger.warning(f"GEE unavailable: {exc}")
        _GEE_AVAILABLE = False
    return _GEE_AVAILABLE


CROP_CATALOG = {
    "paddy":     ("Paddy / Rice",      "#22c55e", "🌾", "kharif"),
    "wheat":     ("Wheat",             "#eab308", "🌾", "rabi"),
    "sugarcane": ("Sugarcane",         "#15803d", "🎋", "all"),
    "maize":     ("Maize (Corn)",      "#f97316", "🌽", "kharif"),
    "cotton":    ("Cotton",            "#e5e7eb", "🌿", "kharif"),
    "soybean":   ("Soybean",           "#84cc16", "🫘", "kharif"),
    "groundnut": ("Groundnut/Peanut",  "#a16207", "🥜", "kharif"),
    "mustard":   ("Mustard/Rapeseed",  "#fbbf24", "🌻", "rabi"),
    "fallow":    ("Fallow / Bare Soil","#9ca3af", "🏜️", "all"),
}

SEASON_WINDOWS = {
    "kharif": ("06-01", "11-30"),
    "rabi":   ("10-01", "04-30"),
    "zaid":   ("03-01", "06-30"),
    "all":    ("01-01", "12-31"),
}

CLASS_PALETTE = [
    "9ca3af", "22c55e", "eab308", "15803d",
    "f97316", "e5e7eb", "84cc16", "a16207", "fbbf24",
]

CLASS_INDEX = {
    0: "fallow", 1: "paddy", 2: "wheat", 3: "sugarcane",
    4: "maize",  5: "cotton", 6: "soybean", 7: "groundnut", 8: "mustard",
}


def _season_dates(season: str):
    today = datetime.utcnow()
    s_md, e_md = SEASON_WINDOWS.get(season, SEASON_WINDOWS["all"])
    if season == "rabi":
        if today.month >= 10:
            start_str = f"{today.year}-{s_md}"
            end_str   = f"{today.year + 1}-{e_md}"
        else:
            start_str = f"{today.year - 1}-{s_md}"
            end_str   = f"{today.year}-{e_md}"
    else:
        start_str = f"{today.year}-{s_md}"
        end_str   = f"{today.year}-{e_md}"
        if end_str > today.strftime("%Y-%m-%d"):
            end_str = today.strftime("%Y-%m-%d")
    return start_str, end_str


def _build_s1_feature_stack(roi, start_str: str, end_str: str):
    s1 = (
        ee.ImageCollection("COPERNICUS/S1_GRD")
        .filterBounds(roi).filterDate(start_str, end_str)
        .filter(ee.Filter.eq("instrumentMode", "IW"))
        .filter(ee.Filter.eq("orbitProperties_pass", "DESCENDING"))
        .filter(ee.Filter.listContains("transmitterReceiverPolarisation", "VH"))
        .filter(ee.Filter.listContains("transmitterReceiverPolarisation", "VV"))
        .select(["VH", "VV"])
    )
    vh_col  = s1.select("VH")
    vv_col  = s1.select("VV")
    vh_mean = vh_col.mean().rename("VH_mean")
    vv_mean = vv_col.mean().rename("VV_mean")
    vh_var  = vh_col.reduce(ee.Reducer.variance()).rename("VH_variance")
    vh_min  = vh_col.min().rename("VH_min")
    vh_max  = vh_col.max().rename("VH_max")
    ratio   = vh_mean.subtract(vv_mean).rename("ratio_VH_VV")
    start_ms = ee.Date(start_str).millis()
    def add_time_band(img):
        days = img.date().millis().subtract(start_ms).divide(86_400_000)
        return img.addBands(ee.Image.constant(days).float().rename("time"))
    s1_timed = vh_col.map(add_time_band)
    vh_slope = s1_timed.select(["time", "VH"]).reduce(ee.Reducer.linearFit()).select("scale").rename("VH_slope")
    feature_stack = ee.Image.cat([vh_mean, vv_mean, ratio, vh_var, vh_slope, vh_min, vh_max]).clip(roi)
    return feature_stack, s1.size()


def _apply_rule_based_classifier(features):
    vh  = features.select("VH_mean")
    vv  = features.select("VV_mean")
    var = features.select("VH_variance")
    slp = features.select("VH_slope")
    rto = features.select("ratio_VH_VV")

    fallow    = vh.lt(-20).And(var.lt(3)).Or(vh.lt(-18).And(var.lt(1.5)))
    paddy     = vh.lt(-16).And(var.gt(4)).And(slp.gt(0.01)).Or(vh.lt(-18).And(slp.gt(0.02)))
    wheat     = (vh.gt(-18).And(vh.lt(-13)).And(var.gt(2)).And(slp.gt(0.005))
                 .And(fallow.Not()).And(paddy.Not()))
    sugarcane = (vh.gt(-13).And(var.lt(4)).And(slp.abs().lt(0.02))
                 .And(fallow.Not()).And(paddy.Not()))
    maize     = (vh.gt(-16).And(slp.gt(0.03))
                 .And(fallow.Not()).And(paddy.Not()).And(sugarcane.Not()))
    cotton    = (vh.gt(-18).And(vh.lt(-14)).And(var.gt(1.5)).And(var.lt(5))
                 .And(fallow.Not()).And(paddy.Not()).And(sugarcane.Not()).And(maize.Not()))
    soybean   = (vh.gt(-17).And(vh.lt(-13)).And(slp.gt(0.01))
                 .And(fallow.Not()).And(paddy.Not()).And(sugarcane.Not())
                 .And(maize.Not()).And(cotton.Not()))
    groundnut = (vh.gt(-19).And(vh.lt(-15)).And(var.lt(3))
                 .And(fallow.Not()).And(paddy.Not())
                 .And(maize.Not()).And(cotton.Not()).And(soybean.Not()))
    mustard   = (vh.gt(-16).And(vv.gt(-12))
                 .And(fallow.Not()).And(paddy.Not()).And(sugarcane.Not())
                 .And(wheat.Not()).And(maize.Not()))

    return (
        ee.Image(0).where(paddy, 1).where(wheat, 2).where(sugarcane, 3)
        .where(maize, 4).where(cotton, 5).where(soybean, 6)
        .where(groundnut, 7).where(mustard, 8)
    ).rename("crop_class").uint8()


def _apply_rf_classifier(features, roi):
    if not _RF_ASSET_ID:
        return None, False
    try:
        classifier = ee.Classifier.load(_RF_ASSET_ID)
        class_img  = features.classify(classifier).rename("crop_class").uint8()
        return class_img, True
    except Exception as exc:
        logger.warning(f"RF classifier failed ({exc}); using rule-based fallback.")
        return None, False


def _compute_class_areas(class_img, roi, scale: int = 30):
    try:
        hist  = class_img.reduceRegion(
            reducer=ee.Reducer.frequencyHistogram(), geometry=roi,
            scale=scale, maxPixels=1e9, bestEffort=True,
        ).getInfo()
        raw   = hist.get("crop_class", {})
        total = sum(raw.values()) if raw else 1
        return {CLASS_INDEX[int(k)]: round(v / total, 4) for k, v in raw.items() if int(k) in CLASS_INDEX}
    except Exception as exc:
        logger.warning(f"Class area computation failed: {exc}")
        return {}


def _get_tile_url(ee_image, vis_params: dict) -> str:
    try:
        map_id = ee_image.getMapId(vis_params)
        return f"https://earthengine.googleapis.com/v1/{map_id['mapid']}/tiles/{{z}}/{{x}}/{{y}}"
    except Exception as exc:
        logger.error(f"getMapId failed: {exc}")
        return ""


# ── Public API ────────────────────────────────────────────────────────────────

def get_crop_map(lat: float, lon: float, radius_km: int = 10, season: str = "kharif") -> dict:
    if not _try_init_gee():
        logger.warning("GEE unavailable — crop map skipped.")
        return {"status": "unavailable", "error": "GEE not configured or unreachable"}
    try:
        start_str, end_str = _season_dates(season)
        roi = ee.Geometry.Point([lon, lat]).buffer(radius_km * 1000)
        feature_stack, _ = _build_s1_feature_stack(roi, start_str, end_str)
        class_img, used_rf = _apply_rf_classifier(feature_stack, roi)
        if class_img is None:
            class_img        = _apply_rule_based_classifier(feature_stack)
            classifier_used  = "rule_based"
        else:
            classifier_used  = "rf"
        fractions      = _compute_class_areas(class_img, roi, scale=30)
        composite_tile = _get_tile_url(class_img, {"min": 0, "max": 8, "palette": CLASS_PALETTE})
        crop_layers = []
        for class_idx, crop_key in CLASS_INDEX.items():
            if crop_key == "fallow":
                continue
            label, color, icon, crop_season = CROP_CATALOG[crop_key]
            if season != "all" and crop_season not in (season, "all"):
                continue
            crop_mask = class_img.eq(class_idx).selfMask()
            tile_url  = _get_tile_url(crop_mask, {"min": 0, "max": 1, "palette": [color.lstrip("#")], "opacity": 0.75})
            crop_layers.append({
                "crop": crop_key, "label": label, "tile_url": tile_url,
                "color": f"#{color.lstrip('#')}", "icon": icon,
                "coverage_pct": round(fractions.get(crop_key, 0.0) * 100, 2),
            })
        crop_layers.sort(key=lambda x: x["coverage_pct"], reverse=True)
        bounds  = roi.bounds().getInfo()["coordinates"][0]
        return {
            "status": "success", "crop_layers": crop_layers,
            "composite_tile_url": composite_tile,
            "bbox": [min(p[0] for p in bounds), min(p[1] for p in bounds),
                     max(p[0] for p in bounds), max(p[1] for p in bounds)],
            "period": {"start": start_str, "end": end_str},
            "season": season, "classifier": classifier_used,
        }
    except Exception as exc:
        logger.exception("get_crop_map failed")
        return {"status": "error", "error": str(exc)}



def get_sar_timeline(polygon_coords: list, radius_km: int = 2, season: str = "kharif") -> dict | None:
    """
    Returns SAR + NDVI timeline dict when GEE is available, or None if GEE is offline.
    Callers should treat None as "crop detection unavailable".
    """
    if not _try_init_gee():
        logger.warning("GEE unavailable — crop/SAR timeline skipped.")
        return None

    if season in SEASON_WINDOWS:
        start_str, end_str = _season_dates(season)
    else:
        end_date   = datetime.utcnow()
        start_date = end_date - timedelta(days=180)
        start_str  = start_date.strftime("%Y-%m-%d")
        end_str    = end_date.strftime("%Y-%m-%d")

    start_date = datetime.strptime(start_str, "%Y-%m-%d")
    end_date   = datetime.strptime(end_str,   "%Y-%m-%d")
    today      = datetime.utcnow()
    if end_date > today:
        end_date = today
        end_str  = today.strftime("%Y-%m-%d")

    try:
        ring = [[c[0], c[1]] for c in polygon_coords]
        roi  = ee.Geometry.Polygon([ring])
        s1   = (
            ee.ImageCollection("COPERNICUS/S1_GRD")
            .filterBounds(roi).filterDate(start_str, end_str)
            .filter(ee.Filter.eq("instrumentMode", "IW"))
            .filter(ee.Filter.listContains("transmitterReceiverPolarisation", "VH"))
            .select("VH")
        )
        s2 = (
            ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
            .filterBounds(roi).filterDate(start_str, end_str)
            .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", 30))
        )
        timeline      = []
        num_intervals = (end_date - start_date).days // 15
        for i in range(num_intervals):
            t_start = start_date + timedelta(days=i * 15)
            t_end   = t_start    + timedelta(days=15)
            ts, te  = t_start.strftime("%Y-%m-%d"), t_end.strftime("%Y-%m-%d")
            vh_val = ndvi_val = None
            try:
                stats  = s1.filterDate(ts, te).mean().reduceRegion(ee.Reducer.mean(), roi, scale=10, maxPixels=1e8).getInfo()
                vh_val = stats.get("VH")
            except Exception:
                pass
            try:
                ndvi_img = s2.filterDate(ts, te).median().normalizedDifference(["B8", "B4"])
                stats2   = ndvi_img.reduceRegion(ee.Reducer.mean(), roi, scale=10, maxPixels=1e8).getInfo()
                ndvi_val = stats2.get("nd")
            except Exception:
                pass
            timeline.append({
                "date":       t_start.strftime("%d %b"),
                "vh":         round(float(vh_val),   2) if vh_val   is not None else None,
                "ndvi":       round(float(ndvi_val), 2) if ndvi_val is not None else None,
                "date_range": f"{t_start.strftime('%d %b')} – {t_end.strftime('%d %b %Y')}",
            })
    except Exception as exc:
        logger.error(f"SAR timeline GEE query failed: {exc}")
        return None

    valid_vh   = [t["vh"]   for t in timeline if t["vh"]   is not None]
    valid_ndvi = [t["ndvi"] for t in timeline if t["ndvi"] is not None]
    detected_crop = "Fallow / Bare Soil"
    confidence    = 70
    description   = "No active vegetation detected. The soil appears fallow or bare."
    icon          = "🏜️"

    if len(valid_vh) >= 4 and len(valid_ndvi) >= 4:
        mean_vh    = sum(valid_vh)   / len(valid_vh)
        mean_ndvi  = sum(valid_ndvi) / len(valid_ndvi)
        min_vh     = min(valid_vh)
        max_ndvi   = max(valid_ndvi)
        min_ndvi   = min(valid_ndvi)
        min_vh_idx = valid_vh.index(min_vh)
        rise_vh = 0.0
        if min_vh_idx < len(valid_vh) - 1:
            rise_vh = max(valid_vh[min_vh_idx:]) - min_vh

        if min_vh < -20.0 and rise_vh > 5.0 and max_ndvi > 0.4:
            detected_crop = "Paddy / Rice"
            confidence    = int(min(98, 70 + rise_vh * 5 + max_ndvi * 20))
            description   = f"Paddy signature: VH dropped to {min_vh} dB (flooding) then rose {rise_vh:.1f} dB. Peak NDVI {max_ndvi:.2f}."
            icon          = "🌾"
        elif mean_vh > -14.5 and mean_ndvi > 0.52 and (max_ndvi - min_ndvi) < 0.25:
            detected_crop = "Sugarcane"
            confidence    = int(min(95, 65 + mean_ndvi * 30))
            description   = f"Sugarcane: stable high SAR (mean VH {mean_vh:.1f} dB) and sustained NDVI {mean_ndvi:.2f}."
            icon          = "🎋"
        elif max_ndvi > 0.55 and valid_ndvi[-1] < 0.35 and (max_ndvi - valid_ndvi[-1]) > 0.25:
            detected_crop = "Wheat"
            confidence    = int(min(92, 60 + max_ndvi * 30))
            description   = f"Wheat: greenness peaked at NDVI {max_ndvi:.2f} then dropped to {valid_ndvi[-1]:.2f} at harvest."
            icon          = "🌾"
        elif max_ndvi > 0.50 and mean_vh > -16.5:
            detected_crop = "Maize (Corn) / Cotton"
            confidence    = int(min(88, 55 + max_ndvi * 30))
            description   = f"Warm-season row crop: peak NDVI {max_ndvi:.2f}, moderate backscatter (mean VH {mean_vh:.1f} dB)."
            icon          = "🌽"

    return {
        "timeline":      timeline,
        "detected_crop": detected_crop,
        "confidence":    confidence,
        "description":   description,
        "icon":          icon,
        "source":        "Sentinel-1 SAR (VH) & Sentinel-2 (NDVI) 15-Day Composites",
        "period":        f"{start_date.strftime('%b %Y')} – {end_date.strftime('%b %Y')}",
        "is_simulated":  False,
    }


# ── Crop Coverage Map (pixel-level, radius-based) ─────────────────────────────

def _build_crop_mask(vh_min, vh_max, vh_mean, vh_diff, ndvi, crop: str):
    """Returns binary ee.Image (1 = crop pixel) for the given crop key."""
    if crop == "paddy":
        return vh_min.lt(-20.0).And(vh_diff.gt(5.0)).And(ndvi.gt(0.4))
    elif crop == "wheat":
        return (vh_mean.gt(-18.0).And(vh_mean.lt(-13.0))
                .And(vh_diff.gt(3.0)).And(ndvi.gt(0.45)))
    elif crop == "sugarcane":
        return vh_mean.gt(-14.0).And(vh_diff.lt(4.0)).And(ndvi.gt(0.55))
    elif crop == "maize":
        return vh_mean.gt(-16.5).And(vh_diff.gt(3.0)).And(ndvi.gt(0.45))
    elif crop == "cotton":
        return (vh_mean.gt(-18.0).And(vh_mean.lt(-14.0)).And(ndvi.gt(0.3)))
    elif crop == "soybean":
        return (vh_mean.gt(-17.0).And(vh_mean.lt(-13.0)).And(ndvi.gt(0.4)))
    elif crop == "groundnut":
        return (vh_mean.gt(-19.0).And(vh_mean.lt(-15.0))
                .And(vh_diff.lt(3.0)).And(ndvi.gt(0.3)))
    elif crop == "mustard":
        return vh_mean.gt(-16.0).And(ndvi.gt(0.35))
    return None



def get_crop_coverage_map(lat: float, lon: float, radius_km: float,
                          crop: str, months_back: int) -> dict:
    """
    Detect pixels of a specific crop within radius_km of (lat,lon)
    using Sentinel-1 SAR VH + Sentinel-2 NDVI over the last months_back months.
    Returns a GEE tile URL for map overlay + area stats.
    """
    if not _try_init_gee():
        logger.warning("GEE unavailable — crop coverage map skipped.")
        return {"status": "unavailable", "error": "GEE not configured or unreachable"}

    try:
        end_dt    = datetime.utcnow()
        start_dt  = end_dt - timedelta(days=months_back * 30)
        start_str = start_dt.strftime("%Y-%m-%d")
        end_str   = end_dt.strftime("%Y-%m-%d")

        roi = ee.Geometry.Point([lon, lat]).buffer(radius_km * 1000)

        # ── Sentinel-1 VH stack ────────────────────────────────────────────
        s1 = (
            ee.ImageCollection("COPERNICUS/S1_GRD")
            .filterBounds(roi).filterDate(start_str, end_str)
            .filter(ee.Filter.eq("instrumentMode", "IW"))
            .filter(ee.Filter.eq("orbitProperties_pass", "DESCENDING"))
            .filter(ee.Filter.listContains("transmitterReceiverPolarisation", "VH"))
            .select("VH")
        )
        n_intervals = max(1, (end_dt - start_dt).days // 15)
        start_ee    = ee.Date(start_str)
        date_seq    = ee.List.sequence(0, n_intervals - 1)

        def make_composite(i):
            s = start_ee.advance(ee.Number(i).multiply(15), "day")
            e = s.advance(15, "day")
            return s1.filterDate(s, e).mean().set("system:time_start", s.millis())

        composites = ee.ImageCollection.fromImages(date_seq.map(make_composite))
        stack      = composites.toBands().clip(roi)

        vh_min  = stack.reduce(ee.Reducer.min()).rename("VH_min")
        vh_max  = stack.reduce(ee.Reducer.max()).rename("VH_max")
        vh_mean = stack.reduce(ee.Reducer.mean()).rename("VH_mean")
        vh_diff = vh_max.subtract(vh_min).rename("VH_diff")

        # ── Sentinel-2 NDVI ───────────────────────────────────────────────
        s2   = (
            ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
            .filterBounds(roi).filterDate(start_str, end_str)
            .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", 20))
            .median()
        )
        ndvi = s2.normalizedDifference(["B8", "B4"]).rename("ndvi")

        # ── Crop mask ─────────────────────────────────────────────────────
        crop_mask = _build_crop_mask(vh_min, vh_max, vh_mean, vh_diff, ndvi, crop)
        if crop_mask is None:
            return {"status": "error", "error": f"Unknown crop: {crop}"}

        crop_img = crop_mask.rename(crop).clip(roi)

        label, color_hex, icon, _ = CROP_CATALOG.get(crop, (crop, "22c55e", "🌾", "all"))
        color = color_hex.lstrip("#")

        tile_url = _get_tile_url(
            crop_img.updateMask(crop_img),
            {"min": 0, "max": 1, "palette": [color], "opacity": 0.8},
        )

        # ── Area calculation ──────────────────────────────────────────────
        area_result = (
            crop_img.multiply(ee.Image.pixelArea())
            .reduceRegion(reducer=ee.Reducer.sum(), geometry=roi,
                          scale=10, maxPixels=1e13)
            .getInfo()
        )
        area_sqm = float(area_result.get(crop) or 0)
        area_ha  = round(area_sqm / 10000, 2)

        total_sqm = math.pi * (radius_km * 1000) ** 2
        coverage_pct = round((area_sqm / max(total_sqm, 1)) * 100, 2)

        return {
            "status":       "success",
            "crop":         crop,
            "label":        label,
            "icon":         icon,
            "color":        f"#{color}",
            "tile_url":     tile_url,
            "area_ha":      area_ha,
            "coverage_pct": coverage_pct,
            "period":       {"start": start_str, "end": end_str},
            "months_back":  months_back,
            "radius_km":    radius_km,
            "is_simulated": False,
        }
    except Exception as exc:
        logger.exception("get_crop_coverage_map failed")
        return {"status": "error", "error": str(exc)}


# ── Point NDVI (yield estimator) ──────────────────────────────────────────────

def get_point_ndvi(lat: float, lon: float) -> dict | None:
    """
    Mean MODIS NDVI over the trailing 365 days at a single point.
    Returns None if GEE is unavailable or no NDVI value could be read.
    """
    if not _try_init_gee():
        logger.warning("GEE unavailable — point NDVI skipped.")
        return None
    try:
        end_dt   = datetime.utcnow()
        start_dt = end_dt - timedelta(days=365)
        point    = ee.Geometry.Point([lon, lat])
        modis    = ee.ImageCollection("MODIS/061/MOD13A2").select("NDVI")
        img      = modis.filterDate(start_dt.strftime("%Y-%m-%d"), end_dt.strftime("%Y-%m-%d")).mean()
        raw      = img.reduceRegion(ee.Reducer.mean(), point, 1000).get("NDVI").getInfo()
        if raw is None:
            return None
        return {
            "ndvi_raw":    round(raw, 1),
            "ndvi_factor": round(min(1.0, raw / 7000.0), 4),
            "source":      "MODIS_MOD13A2_trailing_365d",
        }
    except Exception as exc:
        logger.warning(f"get_point_ndvi failed: {exc}")
        return None