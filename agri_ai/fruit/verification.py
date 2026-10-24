"""
agri_ai.fruit.verification
--------------------------
Checks that a crop actually is the fruit the user selected, so a wrong photo
is reported as a "Mismatch" instead of being graded. Also powers
fruit_type='auto'. Ported from HarvestLenz `classification_service`.

Uses a trained classifier when `models/fruit_classifier.keras` (+ optional
`class_indices.json`) exists; otherwise falls back to OpenCV colour/shape
heuristics (HarvestLenz ships no classifier, so this is the default).
"""
import json
import logging
import os

import cv2
import numpy as np

from .keras_backend import load_keras_model, mobilenet_preprocess

logger = logging.getLogger(__name__)

MODEL_DIR       = os.path.join(os.path.dirname(__file__), 'models')
CLASSIFIER_PATH = os.path.join(MODEL_DIR, 'fruit_classifier.keras')
INDICES_PATH    = os.path.join(MODEL_DIR, 'class_indices.json')

_classifier     = None
_classes        = []
_classifier_tried = False


def _get_classifier():
    global _classifier, _classes, _classifier_tried
    if _classifier_tried:
        return _classifier
    _classifier_tried = True
    if not os.path.exists(CLASSIFIER_PATH):
        logger.info('[agri_ai.fruit] No fruit classifier, using OpenCV feature verification')
        return None
    _classifier = load_keras_model(CLASSIFIER_PATH)
    if _classifier is not None and os.path.exists(INDICES_PATH):
        with open(INDICES_PATH, 'r') as f:
            mapping = json.load(f)
        _classes = [k for k, _v in sorted(mapping.items(), key=lambda kv: kv[1])]
    return _classifier


def _hsv_metrics(crop_bgr):
    """Mean H/S/V over non-background pixels (ignores white and very dark borders)."""
    hsv = cv2.cvtColor(crop_bgr, cv2.COLOR_BGR2HSV)
    s, v = hsv[:, :, 1], hsv[:, :, 2]
    fg = ~((s < 25) & (v > 210)) & (v > 25)
    if not np.any(fg):
        return tuple(float(np.mean(hsv[:, :, i])) for i in range(3))
    return tuple(float(np.mean(hsv[:, :, i][fg])) for i in range(3))


def _gray_std(crop_bgr):
    return float(np.std(cv2.cvtColor(crop_bgr, cv2.COLOR_BGR2GRAY)))


def classify_fruit(crop_bgr):
    """{'fruit_type': str, 'confidence': float} — 'unknown' when nothing matches."""
    if crop_bgr is None or crop_bgr.size == 0:
        return {'fruit_type': 'unknown', 'confidence': 0.0}

    model = _get_classifier()
    if model is not None and _classes:
        try:
            preds = model.predict(np.expand_dims(mobilenet_preprocess(crop_bgr), 0), verbose=0)[0]
            idx = int(np.argmax(preds))
            return {'fruit_type': _classes[idx] if idx < len(_classes) else 'unknown',
                    'confidence': round(float(preds[idx]), 4)}
        except Exception:
            logger.exception('[agri_ai.fruit] Fruit classifier inference failed')

    fruit, confidence = _feature_based_classify(crop_bgr)
    return {'fruit_type': fruit, 'confidence': confidence}


def verify_fruit(crop_bgr, expected_fruit):
    """{'is_match', 'predicted_fruit', 'confidence', 'warning'} for one crop."""
    expected = expected_fruit.lower().strip()
    if crop_bgr is None or crop_bgr.size == 0:
        return {'is_match': True, 'predicted_fruit': expected, 'confidence': 0.5, 'warning': None}

    # 1. A confident *trained* classifier decides. The heuristic fallback in
    #    classify_fruit() is not used here: it labels most warm-coloured,
    #    textured photos 'pineapple'/'guava' and so flagged genuine mango,
    #    grape and pomegranate photos as mismatches.
    if _get_classifier() is not None and _classes:
        result    = classify_fruit(crop_bgr)
        predicted = result['fruit_type']
        conf      = result['confidence']
    else:
        predicted, conf = 'unknown', 0.0

    if predicted != 'unknown' and conf >= 0.70:
        if predicted == expected:
            return {'is_match': True, 'predicted_fruit': predicted, 'confidence': conf, 'warning': None}
        return {
            'is_match': False, 'predicted_fruit': predicted, 'confidence': conf,
            'warning': (f"Image Mismatch: Uploaded image appears to be a '{predicted.capitalize()}', "
                        f"but '{expected.capitalize()}' was selected."),
        }

    # 2. Otherwise check the expected fruit's visual profile.
    ok, detected, warning = _check_feature_profile(crop_bgr, expected)
    if not ok:
        return {'is_match': False, 'predicted_fruit': detected or 'Different Fruit',
                'confidence': 0.85, 'warning': warning}
    return {'is_match': True, 'predicted_fruit': expected, 'confidence': 0.90, 'warning': None}


def _feature_based_classify(crop_bgr):
    h, w = crop_bgr.shape[:2]
    if h == 0 or w == 0:
        return 'unknown', 0.0
    aspect = float(w) / float(h)
    if aspect < 1.0:
        aspect = 1.0 / aspect
    hue, sat, val = _hsv_metrics(crop_bgr)

    # Non-graded produce (carrot, tomato, plum...) is still recognised so a
    # photo of it is reported as a mismatch rather than graded.
    if aspect > 1.8:
        if 5 <= hue <= 25 and sat > 50:
            return 'carrot', 0.85
        if 35 <= hue <= 85:
            return 'cucumber', 0.82
        if 15 <= hue <= 65:
            return 'banana', 0.85
    if 10 <= hue <= 40 and val > 40 and sat > 30 and _gray_std(crop_bgr) > 18:
        return 'pineapple', 0.82
    if 5 <= hue <= 28 and sat > 50:
        return 'orange', 0.85
    if (hue < 14 or hue > 165) and sat > 45:
        if aspect < 1.35:
            return ('strawberry', 0.85) if sat > 55 else ('tomato', 0.85)
        return 'pomegranate', 0.85
    if 15 <= hue <= 60 and sat > 35:
        return 'mango', 0.75
    if (30 <= hue <= 90 or 110 <= hue <= 165) and sat > 20:
        if hue > 110:
            return ('grapes', 0.80) if sat > 35 else ('plum', 0.80)
        if aspect > 1.3:
            return ('pear', 0.75) if hue < 40 else ('capsicum', 0.75)
        return 'guava', 0.75
    if 10 <= hue <= 35 and sat < 35:
        return 'potato', 0.70
    return 'unknown', 0.50


def _mismatch(detected, expected_name, msg=None):
    return False, detected, msg or (
        f"Image Mismatch: Uploaded image appears to be a '{detected.capitalize()}', "
        f"but '{expected_name}' was selected."
    )


def _check_feature_profile(crop_bgr, expected):
    """Per-fruit rules that catch the most common wrong-photo cases."""
    h, w = crop_bgr.shape[:2]
    if h == 0 or w == 0:
        return True, None, None
    aspect = float(w) / float(h)
    hue, sat, _val = _hsv_metrics(crop_bgr)
    red = hue < 14 or hue > 165

    if expected == 'mango':
        if red and sat > 45:
            return _mismatch('strawberry' if aspect < 1.35 else 'pomegranate', 'Mango')
        if 115 <= hue <= 165 and sat > 40:
            return _mismatch('grapes', 'Mango')

    if expected == 'strawberry' and 25 <= hue <= 90 and sat > 30:
        return _mismatch('mango' if 15 <= hue <= 60 else 'guava', 'Strawberry')

    if expected == 'orange':
        if (hue < 4 or hue > 165) and sat > 50:
            return _mismatch('strawberry', 'Orange')
        if 35 <= hue <= 90 and sat > 30:
            return _mismatch('guava', 'Orange',
                             "Image Mismatch: Uploaded image appears to be a green fruit (Guava/Grapes), "
                             "but 'Orange' was selected.")

    if expected == 'grapes':
        if 12 <= hue <= 40 and sat > 30 and _gray_std(crop_bgr) > 18:
            return _mismatch('pineapple', 'Grapes')
        if red and sat > 50:
            return _mismatch('strawberry', 'Grapes')
        if aspect > 1.95 or aspect < 0.5:
            return _mismatch('banana', 'Grapes', "Image Mismatch: Uploaded image shape does not match Grapes.")

    if expected == 'pineapple':
        if (45 <= hue <= 85 or hue > 120) and aspect < 1.3 and _gray_std(crop_bgr) < 18:
            return _mismatch('grapes', 'Pineapple',
                             "Image Mismatch: Uploaded image appears to be Grapes or Guava, "
                             "but 'Pineapple' was selected.")

    if expected == 'banana' and 0.75 <= aspect <= 1.35 and red and sat > 50:
        return _mismatch('strawberry', 'Banana')

    return True, None, None
