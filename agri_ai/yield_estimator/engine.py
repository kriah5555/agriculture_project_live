from agri_ai.gee.service import get_point_ndvi


def soil_score(soc, pH, N, P, K):
    s_soc = min(25, (soc / 1.0) * 25)
    s_pH  = max(0, 25 - abs(pH - 7.0) * 8)
    s_N   = min(20, (N / 280.0) * 20)
    s_P   = min(15, (P / 40.0) * 15)
    s_K   = min(15, (K / 200.0) * 15)
    total = s_soc + s_pH + s_N + s_P + s_K
    if total >= 80:
        grade = "Excellent"
    elif total >= 65:
        grade = "Good"
    elif total >= 50:
        grade = "Fair"
    elif total >= 35:
        grade = "Poor"
    else:
        grade = "Critical"
    return {
        "total": round(total, 1), "soc": round(s_soc, 1), "pH": round(s_pH, 1),
        "N": round(s_N, 1), "P": round(s_P, 1), "K": round(s_K, 1), "grade": grade,
    }


def predict_yield(district, crop, soc, pH, N, P, K, potential, water_data, irrigation_data, lookup,
                   lat=None, lon=None):
    """
    predicted_yield = potential_yield * soil_factor * water_factor * ndvi_factor

    potential/water_data/irrigation_data/lookup are the loaded JSON tables
    (see data_loader.py). NDVI is fetched live from GEE using lat/lon when
    given, else defaults to 0.7 (same fallback as the source prototype).
    """
    pot_key = f"{district}|{crop}"
    if pot_key not in potential:
        district_matches = [d for d in lookup["districts"] if d.lower() == district.lower()]
        crop_matches      = [c for c in lookup["crops"] if c.lower() == crop.lower()]
        msg = "No yield history found for this district-crop pair."
        if district_matches and crop_matches:
            msg = f"'{district_matches[0]}' and '{crop_matches[0]}' exist but have no shared data."
        return {"status": "not_available", "message": msg}

    pot             = potential[pot_key]
    potential_yield = pot["mean"]

    soil        = soil_score(soc, pH, N, P, K)
    soil_factor = soil["total"] / 100.0

    wd         = water_data.get(district, {})
    hist_water = wd.get("hist_water_factor", 0.5)
    raw_water  = wd.get("water_factor", 0.5)

    irr       = irrigation_data.get(district, {})
    irr_score = irr.get("irrigation_score", 0.0)

    water_factor = round(min(1.0, hist_water + irr_score * (1.0 - hist_water)), 4)

    ndvi_factor = 0.7
    ndvi_raw    = 0
    ndvi_source = ""
    ndvi_data   = get_point_ndvi(lat, lon) if lat and lon else None
    if ndvi_data:
        ndvi_factor = ndvi_data["ndvi_factor"]
        ndvi_raw    = ndvi_data["ndvi_raw"]
        ndvi_source = ndvi_data["source"]

    predicted = potential_yield * soil_factor * water_factor * ndvi_factor

    return {
        "status": "available",
        "data": {
            "district": district, "crop": crop,
            "potential_yield": round(potential_yield, 1),
            "soil": soil, "soil_factor": round(soil_factor, 4),
            "rain_water_factor": round(raw_water, 4),
            "hist_water_factor": round(hist_water, 4),
            "irrigation_score": round(irr_score, 3),
            "water_factor": water_factor,
            "precip_mm": wd.get("precip_mm", 0),
            "hist_precip_mm": wd.get("hist_precip_mm", 0),
            "et0_mm": wd.get("et0_mm", 0),
            "ndvi_factor": round(ndvi_factor, 4),
            "ndvi_raw": ndvi_raw,
            "ndvi_source": ndvi_source,
            "gee_authenticated": bool(ndvi_data),
            "predicted_yield": round(predicted, 1),
            "n_years": pot["n"], "max_yield": pot["max"], "p90_yield": pot["p90"],
        },
    }