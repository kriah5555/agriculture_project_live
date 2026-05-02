"""
test_ndvi.py
------------
Quick test to verify that GEE is connected and NDVI is returned
for a single known location (Hyderabad, Telangana).
"""

from ndvi import get_ndvi

# ── Test Location: Hyderabad, Telangana ───────────────────────────────────────
TEST_LAT   = 17.385
TEST_LON   = 78.486
START_DATE = "2023-06-01"
END_DATE   = "2023-09-30"


def run_test():
    print("=" * 45)
    print("GEE NDVI Test")
    print("=" * 45)
    print(f"Location  : ({TEST_LAT}, {TEST_LON})  — Hyderabad")
    print(f"Date range: {START_DATE} to {END_DATE}")
    print("-" * 45)

    ndvi = get_ndvi(TEST_LAT, TEST_LON, START_DATE, END_DATE)

    if ndvi is not None:
        print(f"[OK] NDVI returned: {ndvi:.4f}")
        print("  Healthy vegetation  ~ 0.2 - 0.8")
        print("  Water / bare soil   ~ 0.0 - 0.2")
    else:
        print("[FAIL] NDVI returned: None")
        print("  Possible causes:")
        print("  - No cloud-free Sentinel-2 images in this date range")
        print("  - GEE not authenticated (run: earthengine authenticate)")
        print("  - Project 'soilmain' not registered for Earth Engine")

    print("=" * 45)


if __name__ == "__main__":
    run_test()
