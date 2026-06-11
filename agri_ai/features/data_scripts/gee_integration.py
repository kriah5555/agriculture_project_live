import pandas as pd
import ee
import os
import requests

# Configuration
TEST_MODE = False
PROJECT_ID = 'soilmain'
INPUT_FILE = 'data/processed/india_soil_geo.csv'
OUTPUT_FILE = 'data/processed/india_soil_live.csv'

def setup_gee():
    print(f"Setting up Google Earth Engine with project: {PROJECT_ID}...")
    try:
        ee.Initialize(project=PROJECT_ID)
        print("GEE Initialized successfully.")
        return True
    except Exception as e:
        print(f"Error initializing GEE: {e}")
        print("Tip: Run 'earthengine authenticate' in your terminal.")
        return False

def get_ndvi(point, date_start, date_end):
    try:
        s2 = (ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
              .filterBounds(point)
              .filterDate(date_start, date_end)
              .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 20)))

        def add_ndvi(image):
            return image.addBands(
                image.normalizedDifference(['B8', 'B4']).rename('NDVI')
            )

        mean_ndvi = s2.map(add_ndvi).select('NDVI').mean()
        stats = mean_ndvi.reduceRegion(
            reducer=ee.Reducer.mean(),
            geometry=point,
            scale=10
        ).getInfo()
        return stats.get('NDVI')
    except Exception as e:
        print(f"  [Error in get_ndvi]: {e}")
        return None

def get_lst(point, date_start, date_end):
    try:
        mean_lst = (ee.ImageCollection("MODIS/061/MOD11A2")
                    .filterBounds(point)
                    .filterDate(date_start, date_end)
                    .select('LST_Day_1km')
                    .mean())

        stats = mean_lst.reduceRegion(
            reducer=ee.Reducer.mean(),
            geometry=point,
            scale=1000
        ).getInfo()

        val = stats.get('LST_Day_1km')
        return (val * 0.02) - 273.15 if val is not None else None
    except Exception as e:
        print(f"  [Error in get_lst]: {e}")
        return None

def get_soil_moisture(lat, lon):
    """
    Fetch mean root-zone soil wetness (GWETROOT, 0-1 scale) for 2024
    using the NASA POWER API — no GEE quota consumed.
    """
    try:
        response = requests.get(
            "https://power.larc.nasa.gov/api/temporal/daily/point",
            params={
                "parameters": "GWETROOT",
                "community":  "AG",
                "longitude":  lon,
                "latitude":   lat,
                "start":      "20240101",
                "end":        "20241231",
                "format":     "JSON",
            },
            timeout=30
        )
        response.raise_for_status()
        data   = response.json()
        values = data["properties"]["parameter"]["GWETROOT"]
        valid  = [v for v in values.values() if v != -999.0]
        return round(sum(valid) / len(valid), 4) if valid else None
    except Exception as e:
        print(f"  [Error in get_soil_moisture]: {e}")
        return None

def main():
    if not setup_gee():
        return

    if not os.path.exists(INPUT_FILE):
        print(f"Input file {INPUT_FILE} not found.")
        return

    df = pd.read_csv(INPUT_FILE)
    df['lat'] = pd.to_numeric(df['lat'], errors='coerce')
    df['lon'] = pd.to_numeric(df['lon'], errors='coerce')
    df = df.dropna(subset=['lat', 'lon'])

    if TEST_MODE:
        df = df.head(10).copy()
        print("TEST_MODE active: Processing only first 10 rows.")

    # Use 2024 for stable data availability
    date_start = "2024-01-01"
    date_end   = "2024-12-31"

    ndvi_list, temp_list, sm_list = [], [], []
    success_count, fail_count = 0, 0
    total = len(df)

    print(f"Processing {total} rows for satellite features...")

    for i, (idx, row) in enumerate(df.iterrows(), 1):
        print(f"[{i}/{total}] Processing {row['district']}, {row['state']}...", end='\r')
        try:
            point = ee.Geometry.Point([row['lon'], row['lat']])
            ndvi = get_ndvi(point, date_start, date_end)
            lst  = get_lst(point, date_start, date_end)
            sm   = get_soil_moisture(row['lat'], row['lon'])

            ndvi_list.append(ndvi)
            temp_list.append(lst)
            sm_list.append(sm)
            success_count += 1
            ndvi_str = f"{ndvi:.3f}" if ndvi is not None else "N/A"
            lst_str  = f"{lst:.1f}°C" if lst is not None else "N/A"
            sm_str   = f"{sm:.3f}" if sm is not None else "N/A"

            print(f"[{i}/{total}] OK — {row['district']}, {row['state']} | "
                  f"NDVI={ndvi_str}, LST={lst_str}, SM={sm_str}")
        except Exception as e:
            print(f"[{i}/{total}] Failed: {e}")
            ndvi_list.append(None)
            temp_list.append(None)
            sm_list.append(None)
            fail_count += 1

    df['ndvi'] = ndvi_list
    df['temperature'] = temp_list
    df['soil_moisture'] = sm_list

    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
    df.to_csv(OUTPUT_FILE, index=False)

    print(f"\n{'='*30}")
    print("SATELLITE INTEGRATION SUMMARY")
    print(f"{'='*30}")
    print(f"Successful rows : {success_count}")
    print(f"Failed rows     : {fail_count}")
    print(f"Output saved to : {OUTPUT_FILE}")
    print("\nSample output:")
    print(df[['district', 'state', 'ndvi', 'temperature', 'soil_moisture']].head())

if __name__ == "__main__":
    main()