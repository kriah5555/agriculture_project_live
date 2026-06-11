"""
soil_texture.py
---------------
Fetch soil texture (clay %, sand %, silt %) from the SoilGrids v2 REST API.
No API key required.  SoilGrids docs: https://rest.isric.org/soilgrids/v2.0/docs
"""

import requests

_API_URL      = "https://rest.isric.org/soilgrids/v2.0/properties/query"
_PROPERTIES   = ["clay", "sand", "silt"]
_DEPTH        = "0-5cm"
_VALUE        = "mean"
_TIMEOUT      = 60
_SCALE_FACTOR = 10.0   # SoilGrids returns g/kg → divide by 10 for %


def get_soil_texture(lat: float, lon: float) -> dict:
    """
    Return clay_pct, sand_pct, silt_pct (0-100 scale) for the 0-5 cm topsoil
    layer at the given point. Returns None values on failure.
    """
    result = {"clay_pct": None, "sand_pct": None, "silt_pct": None}
    try:
        param_list = [("lat", lat), ("lon", lon), ("depth", _DEPTH), ("value", _VALUE)]
        for prop in _PROPERTIES:
            param_list.append(("property", prop))

        response = requests.get(_API_URL, params=param_list, timeout=_TIMEOUT)
        response.raise_for_status()
        data = response.json()

        for layer in data.get("properties", {}).get("layers", []):
            name = layer.get("name")
            if name not in _PROPERTIES:
                continue
            for depth_info in layer.get("depths", []):
                if depth_info.get("label") == _DEPTH:
                    raw = depth_info.get("values", {}).get(_VALUE)
                    if raw is not None:
                        result[f"{name}_pct"] = round(raw / _SCALE_FACTOR, 2)
        return result

    except requests.exceptions.Timeout:
        print(f"  [soil_texture] Timeout for ({lat}, {lon})")
    except requests.exceptions.ConnectionError:
        print(f"  [soil_texture] ConnectionError for ({lat}, {lon})")
    except requests.exceptions.HTTPError as e:
        print(f"  [soil_texture] HTTPError {e} for ({lat}, {lon})")
    except Exception as e:
        print(f"  [soil_texture] Unexpected error for ({lat}, {lon}): {e}")
    return result