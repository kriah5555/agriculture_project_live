"""
weather.py
----------
Module to fetch weather data (temperature & rainfall) using the
NASA POWER API — no API key required.

API docs: https://power.larc.nasa.gov/api/
"""

import requests
from datetime import datetime, timedelta

# ── Configuration ─────────────────────────────────────────────────────────────
NASA_POWER_URL = "https://power.larc.nasa.gov/api/temporal/daily/point"

# Dynamically fetch the last 365 days (ending 7 days ago to ensure NASA has processed the data)
end_dt = datetime.now() - timedelta(days=7)
start_dt = end_dt - timedelta(days=365)
START_DATE = start_dt.strftime("%Y%m%d")
END_DATE = end_dt.strftime("%Y%m%d")

PARAMETERS     = "T2M,PRECTOTCORR"   # Temperature & Corrected Precipitation
COMMUNITY      = "AG"                 # Agricultural community dataset
TIMEOUT_SECS   = 30


def get_weather(lat: float, lon: float):
    """
    Fetch average temperature (°C) and total rainfall (mm) for a location
    using the NASA POWER API (year 2023).

    Parameters
    ----------
    lat : float — Latitude  (e.g. 17.385)
    lon : float — Longitude (e.g. 78.486)

    Returns
    -------
    (avg_temperature, total_rainfall) : (float, float) or (None, None)
    """
    params = {
        "parameters": PARAMETERS,
        "community":  COMMUNITY,
        "longitude":  lon,
        "latitude":   lat,
        "start":      START_DATE,
        "end":        END_DATE,
        "format":     "JSON",
    }

    try:
        response = requests.get(NASA_POWER_URL, params=params, timeout=TIMEOUT_SECS)
        response.raise_for_status()
        data = response.json()

        # Navigate the JSON structure
        properties   = data["properties"]["parameter"]
        temp_daily   = properties.get("T2M", {})
        rain_daily   = properties.get("PRECTOTCORR", {})

        # Filter out NASA POWER fill values (-999)
        valid_temps  = [v for v in temp_daily.values() if v != -999.0]
        valid_rains  = [v for v in rain_daily.values() if v != -999.0]

        if not valid_temps or not valid_rains:
            print(f"  [WEATHER] No valid data for ({lat}, {lon}).")
            return (None, None)

        avg_temperature = round(sum(valid_temps) / len(valid_temps), 3)
        total_rainfall  = round(sum(valid_rains), 3)

        return (avg_temperature, total_rainfall)

    except requests.exceptions.Timeout:
        print(f"  [WEATHER] Request timed out for ({lat}, {lon}).")
        return (None, None)
    except requests.exceptions.ConnectionError:
        print(f"  [WEATHER] Connection error for ({lat}, {lon}). Check internet.")
        return (None, None)
    except requests.exceptions.HTTPError as e:
        print(f"  [WEATHER] HTTP error for ({lat}, {lon}): {e}")
        return (None, None)
    except (KeyError, ValueError) as e:
        print(f"  [WEATHER] Data parsing error for ({lat}, {lon}): {e}")
        return (None, None)
    except Exception as e:
        print(f"  [WEATHER] Unexpected error for ({lat}, {lon}): {e}")
        return (None, None)
