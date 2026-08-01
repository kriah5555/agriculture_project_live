import json
import os

DATA_DIR         = os.path.join(os.path.dirname(__file__), 'data')
HIERARCHY_PATH   = os.path.join(DATA_DIR, 'hierarchy.json')
LOOKUP_PATH      = os.path.join(DATA_DIR, 'lookup.json')
POTENTIAL_PATH   = os.path.join(DATA_DIR, 'potential_yields.json')
WATER_PATH       = os.path.join(DATA_DIR, 'water_data.json')
IRRIGATION_PATH  = os.path.join(DATA_DIR, 'irrigation_data.json')


def load_hierarchy():
    with open(HIERARCHY_PATH) as f:
        return json.load(f)


def load_lookup():
    with open(LOOKUP_PATH) as f:
        return json.load(f)


def load_potential_yields():
    with open(POTENTIAL_PATH) as f:
        return json.load(f)


def load_water_data():
    with open(WATER_PATH) as f:
        return json.load(f)


def load_irrigation_data():
    with open(IRRIGATION_PATH) as f:
        return json.load(f)