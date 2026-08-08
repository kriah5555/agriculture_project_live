# ArkaShine Agriculture Platform

---

## Setup

### 1. Clone the Repository

```bash
git clone <repository-url>
cd agriculture_project_live
```

### 2. Install System-Level Packages (Ubuntu / Debian)

```bash
sudo apt-get install -y libpq-dev python3-dev

sudo apt-get install -y \
    libpango-1.0-0 libpangoft2-1.0-0 libpangocairo-1.0-0 \
    libcairo2 libgdk-pixbuf2.0-0 libharfbuzz-subset0 \
    libffi-dev python3-cffi python3-brotli
```

### 3. Create and Activate Virtual Environment

```bash
python3 -m venv env
source env/bin/activate
```

### 4. Install Python Dependencies

```bash
pip install -r requirements.txt
```

### 5. Configure the Database

For PostgreSQL, set these environment variables:

```
DB_NAME=<your_db_name>
DB_USER=<your_db_user>
DB_PASSWORD=<your_db_password>
DB_HOST=<host>
DB_PORT=5432
```

SQLite is used automatically if these are not set (development only).

### 6. Run Migrations

```bash
python manage.py makemigrations agriapp
python manage.py migrate
```

### 7. Create a Superuser

```bash
python manage.py createsuperuser
```

### 8. Create the `deviseowner` Group

The `/users/` admin page looks up a group named `deviseowner`. On a fresh
database this group doesn't exist yet, which causes a `Group.DoesNotExist`
error when opening that page. Create it once with:

```bash
python manage.py shell -c "from django.contrib.auth.models import Group; Group.objects.get_or_create(name='deviseowner')"
```

### 9. Place ML Model Files

All `.pkl` files are gitignored. Copy them manually after cloning.

**Soil models — copy these 13 files to `agri_ai/soil/models/`:**

```bash
# From a models.zip archive:
unzip models.zip -d agri_ai/soil/models/

# Or copy individually:
cp /path/to/models/lgbm_ph.pkl              agri_ai/soil/models/
cp /path/to/models/lgbm_ec.pkl              agri_ai/soil/models/
cp /path/to/models/lgbm_n.pkl               agri_ai/soil/models/
cp /path/to/models/lgbm_p.pkl               agri_ai/soil/models/
cp /path/to/models/lgbm_k.pkl               agri_ai/soil/models/
cp /path/to/models/lgbm_organic_carbon.pkl  agri_ai/soil/models/
cp /path/to/models/lgbm_s.pkl               agri_ai/soil/models/
cp /path/to/models/lgbm_fe.pkl              agri_ai/soil/models/
cp /path/to/models/lgbm_zn.pkl              agri_ai/soil/models/
cp /path/to/models/lgbm_cu.pkl              agri_ai/soil/models/
cp /path/to/models/lgbm_b.pkl               agri_ai/soil/models/
cp /path/to/models/lgbm_mn.pkl              agri_ai/soil/models/
cp /path/to/models/rf_fertility.pkl         agri_ai/soil/models/
```

**Crop classifier — copy 1 file to `agri_ai/crop/models/`:**

```bash
cp /path/to/models/classifier.pkl  agri_ai/crop/models/
```

> If models are missing the app still runs. Only AI crop prediction and ML-enriched PDF reports are affected.

### 10. Start the Development Server

```bash
python manage.py runserver
```

---

## Production Deployment

```bash
sudo systemctl daemon-reload
sudo systemctl restart gunicorn
sudo systemctl restart nginx
```

---

## Adding New ML Models

1. Create `agri_ai/<model_name>/` with `__init__.py`, `model.py`, and `models/` folder
2. Place `.pkl` files in `models/` (they are gitignored)
3. Import from any app: `from agri_ai.<model_name> import <function>`

See `agri_ai/crop/` as a reference implementation.