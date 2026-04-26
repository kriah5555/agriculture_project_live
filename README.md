# ArkaShine Agriculture Platform

A Django-based backend for the ArkaShine smart agriculture system. Supports multiple IoT soil and atmospheric sensor devices, a web admin dashboard, and a mobile REST API.

---

## Supported Device Types

| Key          | Display Name | Description                                      |
|--------------|--------------|--------------------------------------------------|
| `soilsaathi` | SoiLENZ      | Soil nutrient sensor (N, P, K, pH, EC, OC, etc.) |
| `atmo_sense` | SoilSparsh   | Atmospheric + soil temp, moisture, light sensor  |
| `soil_life`  | SoilLIFE     | Bio-gas sensor (CO₂, methane, ammonia, etc.)     |
| `ph_bottle`  | PHBottle     | pH & EC probe (pH value/voltage, EC value/voltage)|

---

## Setup

### 1. Clone the Repository

```bash
git clone <repository-url>
cd agriculture_project_live
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

Or use the automated installer (checks system dependencies for psycopg2, etc.):

```bash
bash install_deps.sh
```

### 3. Configure the Database

The project supports **PostgreSQL** (production) and **SQLite** (development).

For PostgreSQL, set these environment variables before running:

```
DB_NAME=<your_db_name>
DB_USER=<your_db_user>
DB_PASSWORD=<your_db_password>
DB_HOST=<host>
DB_PORT=5432
```

### 4. Run Migrations

```bash
python manage.py makemigrations agriapp
python manage.py migrate
```

This also runs the data migration that creates the `deviseowner` group required by the Users page.

### 5. Create a Superuser (Admin)

```bash
python manage.py createsuperuser
```

Follow the prompts to set a username, email, and password.

### 6. Start the Development Server

```bash
python manage.py runserver
```

---

## Deployment (Production)

After pulling updates or changing configuration:

```bash
sudo systemctl daemon-reload
sudo systemctl restart gunicorn
sudo systemctl restart nginx
```

---

## Web Admin Routes

| URL | Description |
|-----|-------------|
| `/welcome/` | Admin dashboard |
| `/soil-saathi-dashboard/` | SoiLENZ device list & API calls |
| `/atmos-sense-dashboard/` | SoilSparsh device list & API calls |
| `/soil-life-dashboard/` | SoilLIFE device list & API calls |
| `/ph-bottle-dashboard/` | PHBottle device list & API calls |
| `/users/` | Users in the `deviseowner` group |
| `/docs/` | API documentation (Swagger / ReDoc) |

---

## Mobile REST API

All endpoints are prefixed with `/api/mobile/` and require JWT Bearer authentication unless noted.

### Authentication

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/mobile/auth/login/` | Obtain access + refresh tokens |
| POST | `/api/mobile/auth/refresh/` | Get a new access token |
| POST | `/api/mobile/auth/logout/` | Blacklist the refresh token |
| POST | `/api/mobile/auth/forgot-password/` | Notify admin of forgotten password (no auth) |

### Device Types & Field Schema

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/mobile/device-types/` | List all device types with lock status |
| GET | `/api/mobile/device-types/<type_key>/field-schema/` | Field label map for a device type (e.g. `field1` → `"pH Value"`) |

### Devices

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/mobile/devices/` | List user's devices |
| GET | `/api/mobile/devices/<id>/` | Full device details |
| GET | `/api/mobile/devices/<id>/location/` | Device GPS coordinates |

> **Note on `<id>` vs `devise_id`:** The `<id>` in all API URLs above is the **integer primary key** of the device record (the `id` field). This is different from the string `devise_id` field shown on the device details page (which is a human-readable identifier like a username or device tag). Always use the integer `id` when calling mobile APIs.

### API Calls (Sensor Readings)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/mobile/devices/<id>/api-calls/` | Paginated reading list |
| POST | `/api/mobile/devices/<id>/api-calls/create/` | Submit a new reading |
| GET | `/api/mobile/devices/<id>/api-calls/<call_id>/` | Single reading detail |

**SoiLENZ** readings use fields: `nitrogen`, `phosphorous`, `potassium`, `ph`, `ec`, `oc`, `calcium`, `magnesium`, `sulphur`, `zinc`, `manganese`, `iron`, `copper`, `boron`, `crop_type`, `latitude`, `longitude`.

**SoilSparsh / SoilLIFE / PHBottle** readings use generic keys `field1`–`field8`. The response includes a `labeled_fields` map showing the human-readable name for each key (e.g. `"pH Value": 7.2`). Use the `/field-schema/` endpoint to get this map without needing a reading.

### Thresholds

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/mobile/devices/<id>/threshold/` | Get alert threshold levels |
| POST/PUT | `/api/mobile/devices/<id>/threshold/set/` | Create or update threshold |

### Recommendations (SoiLENZ only)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/mobile/devices/<id>/recommendations/` | Fertilizer recommendations based on NPK data |

### Account

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/mobile/account/profile/` | Get current user profile |
| PATCH | `/api/mobile/account/profile/update/` | Update name/email |
| POST | `/api/mobile/account/change-password-request/` | Notify admin of password change request |

---

## Interactive API Docs (Swagger / ReDoc)

Available at:
- `/api/schema/swagger-ui/` — Swagger UI
- `/api/schema/redoc/` — ReDoc

---

## Field Mappings Reference

### SoilSparsh (`atmo_sense`)
| Key | Label |
|-----|-------|
| `field1` | Soil Temp (°C) |
| `field2` | Soil Moisture (%) |
| `field3` | Atmos Temp (°C) |
| `field4` | Atmos Humidity (%) |
| `field5` | Light Intensity (lux) |

### SoilLIFE (`soil_life`)
| Key | Label |
|-----|-------|
| `field1` | CO₂ (ppm) |
| `field2` | Methane (ppm) |
| `field3` | Ammonia (ppm) |
| `field4` | Nitrous Oxide (ppm) |
| `field5` | Temperature (°C) |
| `field6` | Humidity (%) |
| `field7` | Atmospheric Pressure (hPa) |
| `field8` | Microbial Content (%) |

### PHBottle (`ph_bottle`)
| Key | Label |
|-----|-------|
| `field1` | pH Value |
| `field2` | pH Voltage (mV) |
| `field3` | EC Value (mS/cm) |
| `field4` | EC Voltage (mV) |

---

## User Groups

| Group | Purpose |
|-------|---------|
| `deviseowner` | Regular users who own devices. Listed on the `/users/` admin page. Created automatically by migration `0011`. |

---

## Project Structure

```
agriculture_project_live/
├── agriapp/                  # Core app — models, web views, forms, migrations
│   ├── models.py             # Device types, field mappings, all DB models
│   ├── views.py              # Web dashboard views
│   ├── urls.py               # Web URL routes
│   └── migrations/           # Database migrations (0001 – 0011)
├── devise_apis/              # Mobile REST API
│   ├── mobile_api.py         # All mobile endpoints
│   ├── mobile_serializers.py # DRF serializers
│   └── mobile_urls.py        # Mobile URL routes
├── authapp/                  # Auth helpers
├── predicter/                # ML prediction engine
├── templates/                # HTML templates
├── static/                   # CSS, JS, images
├── requirements.txt          # Python dependencies
└── manage.py
```