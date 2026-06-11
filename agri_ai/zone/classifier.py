import math
import logging
import requests

logger = logging.getLogger(__name__)

_NOMINATIM_HEADERS = {"User-Agent": "AgroClimatApp/1.0 (sunil.gangadhar@gpsrenewables.com)"}


# ---------------------------------------------------------------------------
# Data fetching helpers
# ---------------------------------------------------------------------------

def _fetch_json(url, **kwargs):
    resp = requests.get(url, headers=_NOMINATIM_HEADERS, timeout=8, **kwargs)
    resp.raise_for_status()
    return resp.json()


def get_location_details(lat, lon):
    url = (
        f"https://nominatim.openstreetmap.org/reverse"
        f"?lat={lat}&lon={lon}&format=json&accept-language=en"
    )
    try:
        data    = _fetch_json(url)
        address = data.get('address', {})
        parts   = [address.get(k) for k in ('village', 'town', 'city', 'county', 'state', 'country') if address.get(k)]
        return {
            "country":      address.get('country', 'Unknown'),
            "country_code": address.get('country_code', '').upper(),
            "display_name": ", ".join(parts) or data.get('display_name', f"({lat:.4f}, {lon:.4f})"),
            "address":      address,
        }
    except Exception as e:
        logger.warning("Nominatim reverse geocoding failed: %s", e)
        return {"country": "Unknown", "country_code": "", "display_name": f"({lat:.4f}, {lon:.4f})", "address": {}}


def get_climate_details(lat, lon):
    elevation = 0.0
    try:
        wx = _fetch_json(
            f"https://api.open-meteo.com/v1/forecast"
            f"?latitude={lat}&longitude={lon}&current_weather=true"
        )
        elevation = float(wx.get('elevation', 0.0))
    except Exception as e:
        logger.warning("Open-Meteo elevation failed: %s", e)

    try:
        archive = _fetch_json(
            f"https://archive-api.open-meteo.com/v1/archive"
            f"?latitude={lat}&longitude={lon}"
            f"&start_date=2024-01-01&end_date=2024-12-31"
            f"&daily=temperature_2m_mean,precipitation_sum&timezone=auto"
        )
        daily   = archive.get('daily', {})
        temps   = [t for t in daily.get('temperature_2m_mean', []) if t is not None]
        precips = [p for p in daily.get('precipitation_sum',   []) if p is not None]
        if temps and precips:
            avg_t   = sum(temps) / len(temps)
            chunks  = [temps[i * max(1, len(temps) // 12): (i + 1) * max(1, len(temps) // 12)] for i in range(12)]
            monthly = [sum(c) / len(c) for c in chunks if c]
            return {
                "elevation":          elevation,
                "annual_rainfall":    sum(precips),
                "average_temp":       avg_t,
                "min_temp":           min(temps),
                "max_temp":           max(temps),
                "warmest_month_temp": max(monthly) if monthly else avg_t,
                "coldest_month_temp": min(monthly) if monthly else avg_t,
                "data_source":        "Open-Meteo Historical Archive (2024)",
            }
    except Exception as e:
        logger.warning("Open-Meteo archive failed: %s", e)

    # Geographic fallback
    abs_lat  = abs(lat)
    est_temp = max(-10.0, min(35.0, 28.0 - (abs_lat * 0.4) - (elevation * 0.0065)))
    if abs_lat < 20:
        est_rain = 1200.0
    elif abs_lat < 40:
        est_rain = 500.0
    else:
        est_rain = 800.0
    if 15 <= abs_lat <= 30 and (15 <= lon <= 50 or -100 <= lon <= -30):
        est_rain = 80.0
    return {
        "elevation":          elevation,
        "annual_rainfall":    est_rain,
        "average_temp":       est_temp,
        "min_temp":           est_temp - 8,
        "max_temp":           est_temp + 8,
        "warmest_month_temp": est_temp + 4,
        "coldest_month_temp": est_temp - 4,
        "data_source":        "Dynamic Climatic Estimation (Offline Fallback)",
    }


# ---------------------------------------------------------------------------
# Global Köppen-Geiger classifier
# ---------------------------------------------------------------------------

CLIMATE_ZONE_METADATA = {
    "Tropical Rainforest"         : {"id": "Af",  "color": "#006400", "description": "Hot and wet every month (>2000 mm/yr). Deep laterite soils. Two+ harvests/yr. Ideal for coffee, cocoa, rubber, banana.", "soil_types": ["Laterite (Oxisol)", "Alluvial", "Organic Forest Soil"], "ndvi_range": "0.70–0.92", "growing_tips": "Avoid waterlogging. Intercrop with shade-tolerant crops."},
    "Tropical Monsoon"            : {"id": "Am",  "color": "#228B22", "description": "Hot year-round with a short dry season (1200–2000 mm/yr). Productive for rice, jute, coconut, spices.", "soil_types": ["Red Loam", "Alluvial", "Laterite"], "ndvi_range": "0.55–0.85", "growing_tips": "Plan sowing around monsoon onset. Ensure drainage channels."},
    "Tropical Savanna"            : {"id": "Aw",  "color": "#9ACD32", "description": "Hot year-round, pronounced dry season (700–1200 mm/yr). Cotton, sorghum, groundnut and maize thrive here.", "soil_types": ["Black Cotton Soil (Vertisol)", "Red Sandy Loam"], "ndvi_range": "0.40–0.65", "growing_tips": "Store rainwater. Use drought-tolerant varieties in rabi season."},
    "Hot Desert"                  : {"id": "BWh", "color": "#FFD700", "description": "Extremely hot, <200 mm/yr. Only viable with full irrigation. Dates and drought-tolerant cereals possible.", "soil_types": ["Aridisol", "Saline/Sodic Soil"], "ndvi_range": "0.02–0.15", "growing_tips": "Drip irrigation essential. Mulch heavily to reduce evaporation."},
    "Cold Desert"                 : {"id": "BWk", "color": "#DAA520", "description": "Cold winters, hot summers, <200 mm/yr. Hardy cereals and fruit in oases with irrigation.", "soil_types": ["Calcisol", "Gypsisol"], "ndvi_range": "0.02–0.18", "growing_tips": "Cold-hardy irrigated crops. Windbreaks are essential."},
    "Hot Semi-Arid"               : {"id": "BSh", "color": "#FF8C00", "description": "Hot and dry (200–500 mm/yr). Millets, sorghum, groundnut, and pulses are well-suited.", "soil_types": ["Entisol", "Black Cotton Soil"], "ndvi_range": "0.12–0.35", "growing_tips": "Rainwater harvesting critical. Drought-resistant varieties."},
    "Cold Semi-Arid"              : {"id": "BSk", "color": "#CD853F", "description": "Dry (200–500 mm/yr) with cold winters. Wheat, sunflower, and pulses under rain-fed conditions.", "soil_types": ["Chestnut Soil", "Alluvial Loam"], "ndvi_range": "0.15–0.38", "growing_tips": "Winter wheat in October. Stubble mulching to conserve moisture."},
    "Mediterranean"               : {"id": "Cs",  "color": "#FF6347", "description": "Warm dry summers, mild wet winters (300–900 mm/yr). Premier zone for grapes, olives, citrus, wheat.", "soil_types": ["Terra Rossa", "Red Clay (Alfisol)"], "ndvi_range": "0.30–0.58", "growing_tips": "Winter rains for wheat. Summer crops need irrigation."},
    "Humid Subtropical"           : {"id": "Cfa", "color": "#4169E1", "description": "Hot humid summers, mild winters, year-round rain (800–2000 mm/yr). Rice, wheat, cotton, sugarcane, maize.", "soil_types": ["Ultisol", "Alluvial Loam"], "ndvi_range": "0.50–0.80", "growing_tips": "Three-crop rotation: rice–wheat–vegetables. Manage drainage during monsoon."},
    "Oceanic / Maritime Temperate": {"id": "Cfb", "color": "#6495ED", "description": "Mild and moist year-round (600–1500 mm/yr). Potatoes, brassicas, apples, pasture, cool-season veg.", "soil_types": ["Brown Forest Soil", "Cambisol"], "ndvi_range": "0.45–0.75", "growing_tips": "Watch for late blight. Rotating grass/clover builds fertility."},
    "Warm Continental"            : {"id": "Dfb", "color": "#7B68EE", "description": "Warm summers, cold winters (400–800 mm/yr). Wheat, corn, sunflower, sugar beet, potatoes.", "soil_types": ["Chernozem (Black Earth)", "Luvisol"], "ndvi_range": "0.40–0.70", "growing_tips": "Spring wheat in April. Winter wheat in September."},
    "Subarctic / Boreal"          : {"id": "Dfc", "color": "#4B0082", "description": "Long cold winters, short growing season (50–100 days). Barley, oats, rye, potatoes.", "soil_types": ["Podzol", "Histosol (Peat)"], "ndvi_range": "0.20–0.55", "growing_tips": "Short-season cold-hardy varieties. Row covers extend season."},
    "Tundra"                      : {"id": "ET",  "color": "#B0C4DE", "description": "Permafrost. Only low shrubs and mosses. Very limited agriculture.", "soil_types": ["Cryosol", "Gelisol"], "ndvi_range": "0.10–0.35", "growing_tips": "Greenhouse cultivation only."},
    "Polar / Ice Cap"             : {"id": "EF",  "color": "#E0F2FE", "description": "Permanent ice, mean temp always below 0°C. No agriculture possible.", "soil_types": ["Ice / Rock"], "ndvi_range": "0.00–0.08", "growing_tips": "No agricultural activity possible."},
    "Alpine / Highland"           : {"id": "H",   "color": "#708090", "description": "High elevation, short frost-free seasons. Terraced cultivation: potatoes, barley, quinoa, fruit trees.", "soil_types": ["Lithosol", "Andosol (Volcanic)"], "ndvi_range": "0.15–0.55", "growing_tips": "Use terracing. Cold-adapted varieties. Protect from hailstorms."},
}

# Alias for views that reference GLOBAL_ZONE_METADATA directly
GLOBAL_ZONE_METADATA = CLIMATE_ZONE_METADATA


def classify_global_climate_zone(temp, rainfall, elevation):
    if temp < -10                                            : return "Polar / Ice Cap"
    if temp < 0                                              : return "Tundra"
    if temp < 5                                              : return "Subarctic / Boreal"
    if elevation >= 2500 or (elevation >= 1800 and temp < 12): return "Alpine / Highland"
    if rainfall < 200 and temp >= 18                         : return "Hot Desert"
    if rainfall < 200                                        : return "Cold Desert"
    if 200 <= rainfall < 500 and temp >= 18                  : return "Hot Semi-Arid"
    if 200 <= rainfall < 500                                 : return "Cold Semi-Arid"
    if temp >= 22:
        if rainfall >= 2000: return "Tropical Rainforest"
        if rainfall >= 1200: return "Tropical Monsoon"
        return "Tropical Savanna"
    if temp >= 12:
        if 300 <= rainfall < 900: return "Mediterranean"
        if rainfall >= 900:       return "Humid Subtropical"
        return "Hot Semi-Arid"
    if temp >= 8: return "Oceanic / Maritime Temperate"
    return "Warm Continental"


# ---------------------------------------------------------------------------
# Karnataka zone classifier (10 official zones)
# ---------------------------------------------------------------------------

KARNATAKA_ZONE_METADATA = {
    "North Eastern Transition Zone": {"color": "#27ae60", "id": "Zone 1", "description": "Green plains at the extreme north-eastern tip (Bidar, Gulbarga). Rainfall 800-900 mm. Suited for pulses, millets, sugarcane, and oilseeds.", "soil_types": ["Red Sandy Loam", "Shallow Black Soil"], "ndvi_range": "0.45-0.72", "growing_tips": "Excellent for intercropping pigeonpea with pearl millet. Manage iron deficiency in calcareous black soils."},
    "North Eastern Dry Zone":        {"color": "#ba55d3", "id": "Zone 2", "description": "Semi-arid dry plains in the north-east (Gulbarga, Yadgir, Raichur). Rainfall 600-700 mm. Cotton, sorghum, and pulses dominate.", "soil_types": ["Deep Black Clay Soil (Vertisols)", "Sandy Clay Loam"], "ndvi_range": "0.28-0.55", "growing_tips": "Store rain in deep soils. Rabi chickpeas and wheat are highly productive."},
    "Northern Dry Zone":             {"color": "#8b864e", "id": "Zone 3", "description": "Large dry plains (Bijapur, Bagalkot, Gadag, Koppal, Bellary). Rainfall 500-650 mm. Deep black soils for cotton and rabi jowar.", "soil_types": ["Deep Black Soil", "Saline Pockets"], "ndvi_range": "0.20-0.48", "growing_tips": "Drip irrigation recommended. Focus on salt-tolerant varieties."},
    "Central Dry Zone":              {"color": "#708090", "id": "Zone 4", "description": "Dry central plains (Chitradurga, Tumkur, Davanagere). Rainfall 500-700 mm, gravelly red soils. Millets, oilseeds, and coconut.", "soil_types": ["Red Sandy Clay Loam", "Gravelly Soil"], "ndvi_range": "0.22-0.50", "growing_tips": "Suited for finger millet and groundnuts. Contour bunds conserve run-off."},
    "Eastern Dry Zone":              {"color": "#006400", "id": "Zone 5", "description": "South-eastern dry plains (Bangalore, Kolar, Chikkaballapur). Rainfall 700-850 mm, red soils. Horticulture, finger millet, and mulberry.", "soil_types": ["Red Sandy Loam", "Lateritic Gravelly Soil"], "ndvi_range": "0.32-0.62", "growing_tips": "Ideal for drip-irrigated mango and grapes. Excellent for sericulture."},
    "Southern Dry Zone":             {"color": "#ff0000", "id": "Zone 6", "description": "Southern plains (Mysore, Mandya, Chamarajanagar). Rainfall 650-800 mm. Productive under Kaveri canal system for sugarcane and paddy.", "soil_types": ["Red Gravelly Loam", "Alluvial Pockets"], "ndvi_range": "0.38-0.70", "growing_tips": "In canal areas, rotate paddy with sugarcane. In rain-fed areas, sow finger millet and horse gram."},
    "Southern Transition Zone":      {"color": "#ffff00", "id": "Zone 7", "description": "Transition strip in south Karnataka (Hassan, Chikmagalur, Shimoga). Rainfall 800-1000 mm. Mixed crops, coconut, and upland paddy.", "soil_types": ["Red Sandy Clay", "Sandy Loam"], "ndvi_range": "0.45-0.78", "growing_tips": "Favourable for bi-modal rainfall sowing. Grow ginger, maize, and coconut."},
    "Northern Transition Zone":      {"color": "#6495ed", "id": "Zone 8", "description": "Transition strip in north Karnataka (Belgaum, Dharwad, Haveri). Rainfall 800-1000 mm. Tobacco, cotton, soybean, and chillies.", "soil_types": ["Medium Black Soil", "Red Sandy Loam"], "ndvi_range": "0.42-0.75", "growing_tips": "Excellent for soybean followed by winter sorghum."},
    "Hill Zone":                     {"color": "#00008b", "id": "Zone 9", "description": "Western Ghats mountains (Kodagu, Chikmagalur, Shimoga, Uttara Kannada). Rainfall 1500-5000 mm. Premier zone for coffee, tea, cardamom, pepper, arecanut.", "soil_types": ["Lateritic Red Soil", "Acidic Forest Humus"], "ndvi_range": "0.65-0.90", "growing_tips": "Excellent drainage essential. Provide shade cover for coffee and cardamom."},
    "Coastal Zone":                  {"color": "#800000", "id": "Zone 10", "description": "Humid coastal strip along the Arabian Sea (Dakshina Kannada, Udupi, Uttara Kannada). Rainfall 3000-4000 mm. Paddy, coconut, arecanut, cashew, and banana.", "soil_types": ["Coastal Alluvial Sandy Soil", "Lateritic Loam"], "ndvi_range": "0.55-0.85", "growing_tips": "Flood-resistant paddy varieties in Kharif. Cashews grow well on laterite slopes."},
}


def classify_karnataka_zone(lat, lon, climate):
    rain = climate.get("annual_rainfall", 800)
    elev = climate.get("elevation", 500)
    if lon < 74.8 and rain > 2000:             return "Coastal Zone"
    if elev > 750 and rain > 1200:             return "Hill Zone"
    if lon < 75.8 and rain > 1500:             return "Hill Zone"
    if lat >= 17.0 and lon >= 76.8:            return "North Eastern Transition Zone"
    if lat >= 15.8 and lon >= 76.5:            return "North Eastern Dry Zone"
    if lat >= 14.8 and lon < 76.0 and rain >= 750: return "Northern Transition Zone"
    if lat >= 14.8:                            return "Northern Dry Zone"
    if lat < 14.8 and lon < 76.2 and rain >= 800:  return "Southern Transition Zone"
    if 13.2 <= lat < 14.8 and 75.5 <= lon < 77.2: return "Central Dry Zone"
    if lat < 13.8 and lon >= 77.0:             return "Eastern Dry Zone"
    return "Southern Dry Zone"


# ---------------------------------------------------------------------------
# India national zone classifier (15 Planning Commission zones)
# ---------------------------------------------------------------------------

INDIA_NATIONAL_ZONE_METADATA = {
    "Western Himalayan Region":          {"color": "#2e7d32", "id": "ACZ-01", "description": "High mountain terrain of J&K, Himachal, and Uttarakhand. Suited for temperate fruits, saffron, and cool-season vegetables.", "soil_types": ["Mountain Meadow Soil", "Skeletal Soil"], "ndvi_range": "0.35-0.65", "growing_tips": "Apple, peach, walnut thrive here. Short frost-free season — plan accordingly."},
    "Eastern Himalayan Region":          {"color": "#228b22", "id": "ACZ-02", "description": "Sikkim, Darjeeling, and Northeast states. High rainfall and humidity. Tea, paddy, citrus, and bamboo.", "soil_types": ["Red Lateritic Soil", "Acidic Forest Soil"], "ndvi_range": "0.60-0.90", "growing_tips": "Tea and large cardamom are premium cash crops. Terracing essential on steep slopes."},
    "Lower Gangetic Plains Region":      {"color": "#3cb371", "id": "ACZ-03", "description": "Plains of West Bengal. Highly fertile alluvial soil. Double cropped paddy, jute, mustard, and potato.", "soil_types": ["New Alluvial Soil", "Deltaic Clay"], "ndvi_range": "0.50-0.80", "growing_tips": "Boro rice in dry season. Jute requires well-drained loamy soils."},
    "Middle Gangetic Plains Region":     {"color": "#00fa9a", "id": "ACZ-04", "description": "Eastern UP and Bihar plains. Fertile river basin. Paddy, sugarcane, maize, wheat, and pulses.", "soil_types": ["Alluvial Loam", "Sandy Clay Loam"], "ndvi_range": "0.45-0.75", "growing_tips": "Rice-wheat rotation dominates. Manage waterlogging in low-lying areas."},
    "Upper Gangetic Plains Region":      {"color": "#8fbc8f", "id": "ACZ-05", "description": "Central and Western UP. High irrigation potential. Wheat, sugarcane, paddy, mustard, and potato.", "soil_types": ["Alluvial Sandy Clay Loam"], "ndvi_range": "0.42-0.72", "growing_tips": "Wheat after paddy is the backbone crop rotation. Sugarcane requires deep irrigation."},
    "Trans-Gangetic Plains Region":      {"color": "#20b2aa", "id": "ACZ-06", "description": "Punjab, Haryana, Delhi, and north Rajasthan. Highly irrigated green-revolution belt. Wheat, paddy, cotton, and mustard.", "soil_types": ["Alluvial Loam", "Calcareous Sandy Soil"], "ndvi_range": "0.40-0.75", "growing_tips": "Diversify beyond wheat-rice to legumes to restore soil nitrogen."},
    "Eastern Plateau and Hills Region":  {"color": "#66c547", "id": "ACZ-07", "description": "Chhota Nagpur plateau, Chhattisgarh, Jharkhand, Odisha. High forest cover, rain-fed agriculture. Paddy, niger, pulses, and oilseeds.", "soil_types": ["Red and Yellow Soil", "Lateritic Soil"], "ndvi_range": "0.45-0.78", "growing_tips": "Water harvesting tanks are essential for rabi crops."},
    "Central Plateau and Hills Region":  {"color": "#b5a642", "id": "ACZ-08", "description": "Bundelkhand, Malwa plateau, eastern Rajasthan. Water-scarce plateau. Soybean, wheat, chickpea, sorghum, and mustard.", "soil_types": ["Mixed Red and Black Soil"], "ndvi_range": "0.30-0.58", "growing_tips": "Soybean in kharif and chickpea in rabi is the standard rotation."},
    "Western Plateau and Hills Region":  {"color": "#cd853f", "id": "ACZ-09", "description": "Deccan Trap (Maharashtra). Deep black clay, high water-holding capacity. Cotton, soybean, sorghum, sugarcane, and grapes.", "soil_types": ["Deep Black Clay Soil (Vertisols)"], "ndvi_range": "0.32-0.62", "growing_tips": "Deep black soils retain moisture well. Good for cotton and soybean without irrigation."},
    "Southern Plateau and Hills Region": {"color": "#d2691e", "id": "ACZ-10", "description": "Inland dry zones of the southern peninsula (Karnataka dry zones, Andhra, Tamil Nadu). Finger millet, groundnut, sunflower, cotton, and pulses.", "soil_types": ["Red Gravelly Loam", "Sandy Clay Loam"], "ndvi_range": "0.28-0.55", "growing_tips": "Rainwater harvesting is critical. Groundnut and finger millet are reliable kharif crops."},
    "East Coast Plains and Hills Region":{"color": "#008080", "id": "ACZ-11", "description": "Coastal plains of Odisha, Andhra, and Tamil Nadu. Productive delta agriculture. Paddy, coconut, groundnut, and tobacco.", "soil_types": ["Coastal Alluvium", "Sandy Clay"], "ndvi_range": "0.42-0.75", "growing_tips": "Delta paddy systems are highly productive. Cyclone-resistant crop planning required."},
    "West Coast Plains and Ghats Region":{"color": "#004c00", "id": "ACZ-12", "description": "West coast of India (Kerala, Konkan, coastal Karnataka). Extremely high monsoon rainfall. Plantation crops: rubber, tea, coffee, spices, arecanut, and coconut.", "soil_types": ["Lateritic Soil", "Alluvial Sandy Loam"], "ndvi_range": "0.65-0.90", "growing_tips": "Rubber and coconut are mainstays. Excellent for high-value spices like black pepper."},
    "Gujarat Plains and Hills Region":   {"color": "#e69900", "id": "ACZ-13", "description": "Gujarat plains. Arid to semi-arid. Cotton, groundnut, castor, tobacco, and bajra.", "soil_types": ["Sandy Loam (Goradu)", "Medium Black Soil"], "ndvi_range": "0.28-0.58", "growing_tips": "Cotton on black soils and groundnut on sandy loam are most profitable."},
    "Western Dry Region":                {"color": "#ffd300", "id": "ACZ-14", "description": "Thar Desert (Western Rajasthan). Extremely arid, hot summer. Rainfed pearl millet and cluster beans only.", "soil_types": ["Desert Sandy Soil (Aridisols)"], "ndvi_range": "0.05-0.22", "growing_tips": "Pearl millet is the only reliable kharif crop. Windbreaks reduce sand erosion."},
    "Islands Region":                    {"color": "#00a9e6", "id": "ACZ-15", "description": "Andaman & Nicobar and Lakshadweep. Humid tropical island climate. Coconut, arecanut, spices, and tropical fruits.", "soil_types": ["Sandy Alluvium", "Lateritic Soil"], "ndvi_range": "0.55-0.85", "growing_tips": "Coconut and spices are the primary crops. Soil salinity management near coast is essential."},
}


def classify_india_national_zone(lat, lon, climate):
    rain = climate.get("annual_rainfall", 800)
    elev = climate.get("elevation", 300)
    if (8.0 <= lat <= 14.0 and 92.0 <= lon <= 94.0) or (8.0 <= lat <= 12.0 and 72.0 <= lon <= 74.0):
        return "Islands Region"
    if elev >= 1000 or lat >= 29.5:
        return "Western Himalayan Region" if lon < 80.5 else "Eastern Himalayan Region"
    if lon < 74.0 and lat > 24.0 and rain < 400:
        return "Western Dry Region"
    if 20.0 <= lat <= 24.5 and 68.0 <= lon <= 74.5:
        return "Gujarat Plains and Hills Region"
    if lon < 76.2 and lat < 20.0 and rain >= 1400:
        return "West Coast Plains and Ghats Region"
    if lat >= 24.5 and lon >= 74.0:
        if lon < 77.5:   return "Trans-Gangetic Plains Region"
        elif lon < 81.0: return "Upper Gangetic Plains Region"
        elif lon < 85.0: return "Middle Gangetic Plains Region"
        else:            return "Lower Gangetic Plains Region"
    if lon > 79.5 and lat < 21.0 and rain >= 900:
        return "East Coast Plains and Hills Region"
    if 15.5 <= lat <= 22.0 and 72.5 <= lon <= 80.5:
        return "Western Plateau and Hills Region"
    if lat < 15.5 and 75.0 <= lon <= 79.5:
        return "Southern Plateau and Hills Region"
    if 21.0 <= lat <= 25.0 and 73.5 <= lon <= 80.5:
        return "Central Plateau and Hills Region"
    return "Eastern Plateau and Hills Region"


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def classify_zone(lat, lon):
    """
    Determine the best zone name + metadata for a lat/lon.
    Returns (zone_name, zone_meta, climate_data, location_data).
    """
    location = get_location_details(lat, lon)
    climate  = get_climate_details(lat, lon)

    address      = location.get('address', {})
    state        = address.get('state', '')
    country_code = location.get('country_code', '')

    is_india     = country_code == 'IN' or (8.0 <= lat <= 38.0 and 68.0 <= lon <= 98.0)
    is_karnataka = (state == 'Karnataka') or (is_india and 11.5 <= lat <= 18.5 and 74.0 <= lon <= 78.5)

    if is_india and is_karnataka:
        zone_name = classify_karnataka_zone(lat, lon, climate)
        zone_meta = KARNATAKA_ZONE_METADATA.get(zone_name, {})
    elif is_india:
        zone_name = classify_india_national_zone(lat, lon, climate)
        zone_meta = INDIA_NATIONAL_ZONE_METADATA.get(zone_name, {})
    else:
        zone_name = classify_global_climate_zone(
            climate["average_temp"], climate["annual_rainfall"], climate["elevation"]
        )
        zone_meta = CLIMATE_ZONE_METADATA.get(zone_name, {})

    return zone_name, zone_meta, climate, location