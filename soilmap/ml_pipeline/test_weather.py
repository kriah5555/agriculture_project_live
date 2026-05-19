"""
test_weather.py
---------------
Quick verification script to test the weather.py module
for a single known location (Hyderabad, Telangana).
"""

from weather import get_weather

# ── Test Location ─────────────────────────────────────────────────────────────
TEST_LAT   = 17.385
TEST_LON   = 78.486
LOCATION   = "Hyderabad, Telangana"

# ── Expected ranges for Hyderabad ─────────────────────────────────────────────
EXPECTED_TEMP_RANGE   = (24.0, 32.0)    # Avg annual temp in degrees C
EXPECTED_RAIN_RANGE   = (600, 1100)     # Annual rainfall in mm


def run_test():
    print("=" * 50)
    print("NASA POWER Weather API - Test")
    print("=" * 50)
    print(f"Location  : {LOCATION}")
    print(f"Coords    : ({TEST_LAT}, {TEST_LON})")
    print(f"Year      : 2023")
    print("-" * 50)

    avg_temp, total_rain = get_weather(TEST_LAT, TEST_LON)

    if avg_temp is None or total_rain is None:
        print("[FAIL] No data returned.")
        print("  Possible causes:")
        print("  - No internet connection")
        print("  - NASA POWER API is temporarily down")
        print("  - Invalid coordinates")
        return

    print(f"[OK] Avg Temperature : {avg_temp:.2f} C")
    print(f"[OK] Total Rainfall  : {total_rain:.2f} mm")

    # Plausibility check
    print("\n  Plausibility Check:")
    temp_ok = EXPECTED_TEMP_RANGE[0] <= avg_temp <= EXPECTED_TEMP_RANGE[1]
    rain_ok = EXPECTED_RAIN_RANGE[0] <= total_rain <= EXPECTED_RAIN_RANGE[1]

    print(f"  Temperature {EXPECTED_TEMP_RANGE[0]}-{EXPECTED_TEMP_RANGE[1]} C  : "
          f"{'[PASS]' if temp_ok else '[WARN] Out of expected range'}")
    print(f"  Rainfall {EXPECTED_RAIN_RANGE[0]}-{EXPECTED_RAIN_RANGE[1]} mm     : "
          f"{'[PASS]' if rain_ok else '[WARN] Out of expected range'}")

    print("=" * 50)


if __name__ == "__main__":
    run_test()
