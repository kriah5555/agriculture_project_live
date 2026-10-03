"""
pdf_cache.py
────────────
Background generation + on-disk cache for the SoiLENZ advisory PDF.

Building the report takes longer than gunicorn's worker timeout on
production (the ML/climate lookups alone can take ~30s), so the mobile
endpoint can't just generate it inline — the worker gets killed and nginx
answers 502. Instead the first request starts a background thread, waits
a bounded time, and either returns the finished PDF or tells the app to
ask again shortly. The finished file is kept on disk, keyed by a
fingerprint of the reading's values, so repeat downloads are instant and
any change to the reading (e.g. linking a PHBottle reading) builds a fresh
one. Files and lock markers live on disk, so this works across gunicorn
workers.
"""
import glob
import hashlib
import os
import threading
import time

from django.conf import settings
from django.db import connection

CACHE_DIR = os.path.join(settings.MEDIA_ROOT, 'report_cache')
LOCK_STALE_SECS = 300   # a lock older than this belongs to a dead worker

_FINGERPRINT_FIELDS = (
    'nitrogen', 'phosphorous', 'potassium', 'calcium', 'magnesium', 'sulphur',
    'zinc', 'manganese', 'iron', 'copper', 'boron', 'ph', 'ec', 'oc',
    'crop_type', 'area_name', 'latitude', 'longitude', 'farmer_id',
    'ph_bottle_reading_id',
)


def _paths(reading):
    raw = '|'.join(str(getattr(reading, f, '')) for f in _FINGERPRINT_FIELDS)
    fp = hashlib.sha1(raw.encode()).hexdigest()[:12]
    base = os.path.join(CACHE_DIR, f'soilenz_{reading.pk}_{fp}')
    return base + '.pdf', base + '.name', base + '.lock', base + '.err'


def _take_lock(lock_path):
    """Atomically create the lock file; False if another worker holds it."""
    if os.path.exists(lock_path) and time.time() - os.path.getmtime(lock_path) > LOCK_STALE_SECS:
        try:
            os.remove(lock_path)
        except FileNotFoundError:
            pass
    try:
        os.close(os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY))
        return True
    except FileExistsError:
        return False


def _generate(reading_pk, pdf_path, name_path, lock_path, err_path, base_url, own_host):
    from reports.views import render_soil_report_pdf
    try:
        result = render_soil_report_pdf(reading_pk, base_url, own_host)
        if result is None:
            raise ValueError('Reading not found.')
        pdf_bytes, filename = result
        tmp = pdf_path + '.tmp'
        with open(tmp, 'wb') as f:
            f.write(pdf_bytes)
        with open(name_path, 'w') as f:
            f.write(filename)
        os.replace(tmp, pdf_path)
    except Exception as e:
        with open(err_path, 'w') as f:
            f.write(str(e) or e.__class__.__name__)
    finally:
        try:
            os.remove(lock_path)
        except FileNotFoundError:
            pass
        connection.close()   # this thread's own DB connection


def _read_ready(pdf_path, name_path):
    with open(pdf_path, 'rb') as f:
        pdf_bytes = f.read()
    try:
        with open(name_path) as f:
            filename = f.read().strip() or 'SoiLENZ_Report.pdf'
    except FileNotFoundError:
        filename = 'SoiLENZ_Report.pdf'
    return pdf_bytes, filename


def get_or_start(reading, base_url, own_host, wait_secs=15):
    """
    Returns one of:
      ('ready', (pdf_bytes, filename))
      ('generating', None)   — still building; ask again in a few seconds
      ('error', message)     — the last attempt failed (next call retries)
    """
    os.makedirs(CACHE_DIR, exist_ok=True)
    pdf_path, name_path, lock_path, err_path = _paths(reading)

    if os.path.exists(pdf_path):
        return 'ready', _read_ready(pdf_path, name_path)

    if os.path.exists(err_path) and not os.path.exists(lock_path):
        with open(err_path) as f:
            message = f.read()
        os.remove(err_path)
        return 'error', message

    if _take_lock(lock_path):
        # Drop older cached PDFs of this reading (values have changed since).
        for old in glob.glob(os.path.join(CACHE_DIR, f'soilenz_{reading.pk}_*')):
            if not old.startswith(pdf_path[:-4]):
                try:
                    os.remove(old)
                except OSError:
                    pass
        threading.Thread(
            target=_generate,
            args=(reading.pk, pdf_path, name_path, lock_path, err_path, base_url, own_host),
            daemon=True,
        ).start()

    deadline = time.monotonic() + wait_secs
    while time.monotonic() < deadline:
        if os.path.exists(pdf_path):
            return 'ready', _read_ready(pdf_path, name_path)
        if os.path.exists(err_path) and not os.path.exists(lock_path):
            break
        time.sleep(0.5)

    if os.path.exists(err_path) and not os.path.exists(lock_path):
        with open(err_path) as f:
            message = f.read()
        os.remove(err_path)
        return 'error', message
    return 'generating', None
