"""
agri_ai.fruit.grading
---------------------
Grades fruit crops with the per-fruit MobileNetV2 models, plus an OpenCV
defect score that can override a borderline CNN result to "Reject".
Ported from HarvestLenz `grading_service` + `shared_mobilenet` + `model_loader`.

Models load lazily on first use per fruit and stay cached in the process.
"""
import logging
import os

import cv2
import numpy as np

from .keras_backend import load_keras_model, mobilenet_preprocess
from .rules import GRADE_BETTER, GRADE_GOOD, GRADE_REJECT

logger = logging.getLogger(__name__)

WEIGHTS_DIR = os.path.join(os.path.dirname(__file__), 'models', 'weights')

# Class order by model output size (alphabetical folders seen in training).
_GRADES_BY_NUM_CLASSES = {
    3: [GRADE_BETTER, GRADE_GOOD, GRADE_REJECT],
    2: [GRADE_GOOD, GRADE_REJECT],
}

# Dark-spot (V channel) threshold per fruit for the defect score.
_V_THRESHOLDS = {'mango': 40, 'pomegranate': 50, 'pineapple': 60, 'grapes': 45, 'banana': 45}

# Fruits whose CNN grade is never overridden by the defect score.
_DEFECT_OVERRIDE_DISABLED = {'orange', 'guava', 'banana', 'strawberry'}

_models = {}


def weight_path(fruit):
    for ext in ('.keras', '.h5'):
        path = os.path.join(WEIGHTS_DIR, f'{fruit}{ext}')
        if os.path.exists(path):
            return path
    return None


def get_model(fruit):
    if fruit not in _models:
        path = weight_path(fruit)
        _models[fruit] = load_keras_model(path) if path else None
        if not path:
            logger.warning('[agri_ai.fruit] No grading weights for %s in %s', fruit, WEIGHTS_DIR)
    return _models[fruit]


def extract_defect_features(crop_bgr, fruit):
    """{'defect_score': 0..1, 'defects': [...]} from dark spots, colour spread and shape."""
    if crop_bgr is None or crop_bgr.size == 0:
        return {'defect_score': 0.0, 'defects': []}

    h, w = crop_bgr.shape[:2]
    hsv = cv2.cvtColor(crop_bgr, cv2.COLOR_BGR2HSV)
    aspect_ratio = float(w) / float(h) if h > 0 else 1.0

    _, dark_spots = cv2.threshold(hsv[:, :, 2], _V_THRESHOLDS.get(fruit, 50), 255, cv2.THRESH_BINARY_INV)
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    dark_spots = cv2.morphologyEx(dark_spots, cv2.MORPH_OPEN, kernel, iterations=1)
    contours, _ = cv2.findContours(dark_spots, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    defect_area  = sum(a for a in (cv2.contourArea(c) for c in contours) if a > 200)
    total_area   = float(h * w)
    spot_score   = min(1.0, (defect_area / total_area if total_area else 0.0) * 6.0)
    hue_std      = float(np.std(hsv[:, :, 0].astype(float))) / 180.0
    sat_std      = float(np.std(hsv[:, :, 1].astype(float))) / 255.0
    uniformity   = min(1.0, (hue_std + sat_std) * 0.5)
    defect_score = min(1.0, spot_score * 0.9 + uniformity * 0.1)

    defects = []
    if defect_score > 0.4:
        defects.append('severe_rot_or_bruising')
    elif defect_score > 0.15:
        defects.append('moderate_surface_blemishes')
    elif defect_score > 0.03:
        defects.append('minor_spots')
    if aspect_ratio < 0.7 or aspect_ratio > 1.4:
        defects.append('shape_deformation')
        defect_score = min(1.0, defect_score + 0.2)

    return {'defect_score': round(defect_score, 4), 'defects': defects}


def _decode(pred, fruit, defect_score):
    """(grade, confidence) from one softmax vector, with the defect override."""
    grades = _GRADES_BY_NUM_CLASSES.get(len(pred), _GRADES_BY_NUM_CLASSES[3])
    idx = int(np.argmax(pred))
    grade, confidence = grades[idx], float(pred[idx])

    if fruit not in _DEFECT_OVERRIDE_DISABLED:
        reject_prob     = float(pred[-1])
        best_non_reject = float(np.max(pred[:-1]))
        if defect_score > 0.7:
            grade, confidence = GRADE_REJECT, min(reject_prob + 0.1, 0.99)
        elif best_non_reject - reject_prob < 0.2 and defect_score > 0.5:
            grade, confidence = GRADE_REJECT, reject_prob
    return grade, round(confidence, 4)


def grade_crops(crops, fruit):
    """
    Grade several crops of the same fruit in one batch.
    crops: {fruit_id: crop_bgr}. Returns {fruit_id: {grade, confidence, defect_score, defects}}.
    Raises RuntimeError when there is no model for the fruit.
    """
    model = get_model(fruit)
    if model is None:
        raise RuntimeError(f"No trained grading model available for '{fruit}'.")
    if not crops:
        return {}

    ids      = list(crops)
    features = {fid: extract_defect_features(crops[fid], fruit) for fid in ids}
    batch    = np.stack([mobilenet_preprocess(crops[fid]) for fid in ids], axis=0)
    preds    = np.asarray(model.predict(batch, verbose=0))

    results = {}
    for fid, pred in zip(ids, preds):
        grade, confidence = _decode(pred, fruit, features[fid]['defect_score'])
        results[fid] = {'grade': grade, 'confidence': confidence, **features[fid]}
    return results
