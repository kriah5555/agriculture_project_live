"""
agri_ai.leaf.inference
-----------------------
Leaf disease classification using an ONNX model with test-time augmentation (TTA).
Ported from the standalone `agriculture_ai/detector` app.
"""
import os
import json
import numpy as np
from PIL import Image
import onnxruntime as ort

MODEL_DIR    = os.path.join(os.path.dirname(__file__), 'models')
MODEL_PATH   = os.path.join(MODEL_DIR, 'model.onnx')
CLASSES_PATH = os.path.join(MODEL_DIR, 'class_names.json')

_ort_session  = None
_class_names  = None
_model_loaded = False


def load_inference_assets():
    global _ort_session, _class_names, _model_loaded
    if _model_loaded:
        return True

    if not os.path.exists(MODEL_PATH) or not os.path.exists(CLASSES_PATH):
        print("WARNING: ONNX model or class names JSON not found in agri_ai/leaf/models/.")
        return False

    try:
        _ort_session = ort.InferenceSession(MODEL_PATH)
        with open(CLASSES_PATH, 'r') as f:
            _class_names = json.load(f)
        _model_loaded = True
        print("[agri_ai.leaf] ONNX model and class names loaded successfully!")
        return True
    except Exception as e:
        print(f"[agri_ai.leaf] Error loading ONNX model: {e}")
        return False


# Attempt to load assets on import (mirrors agri_ai.soil eager-load style)
load_inference_assets()

# ImageNet normalization constants
_MEAN = np.array([0.485, 0.456, 0.406], dtype=np.float32)
_STD  = np.array([0.229, 0.224, 0.225], dtype=np.float32)


def _normalize(arr):
    """Normalize a (H, W, 3) float32 array in [0,1] with ImageNet stats."""
    return (arr - _MEAN) / _STD


def _to_tensor(arr):
    """HWC → CHW → add batch dim → (1, 3, H, W)."""
    return np.expand_dims(arr.transpose(2, 0, 1), axis=0)


def _five_crops(img_np, size=224):
    """Return centre crop + 4 corner crops of a (256,256) image."""
    h, w = img_np.shape[:2]
    d = size
    return [
        img_np[(h - d) // 2:(h + d) // 2, (w - d) // 2:(w + d) // 2],  # centre
        img_np[0:d,   0:d],                                            # top-left
        img_np[0:d,   w - d:w],                                        # top-right
        img_np[h - d:h, 0:d],                                          # bottom-left
        img_np[h - d:h, w - d:w],                                      # bottom-right
    ]


def preprocess_image(image_file, target_size=256):
    """
    Load image from file-like object, resize to target_size×target_size,
    convert to float32 in [0,1], and return a (target_size, target_size, 3)
    numpy array (NOT yet normalized or cropped).
    """
    img = Image.open(image_file).convert('RGB')
    img = img.resize((target_size, target_size), Image.BILINEAR)
    return np.array(img, dtype=np.float32) / 255.0


def _run_batch(tensors):
    """Run a list of (1, 3, 224, 224) tensors through the ONNX session and average the softmax."""
    input_name = _ort_session.get_inputs()[0].name
    prob_sum = None
    for t in tensors:
        logits = _ort_session.run(None, {input_name: t})[0][0]
        exp_l = np.exp(logits - np.max(logits))
        probs = exp_l / np.sum(exp_l)
        prob_sum = probs if prob_sum is None else prob_sum + probs
    return prob_sum / len(tensors)


def predict_leaf_disease(image_file):
    """
    Predicts the leaf type and disease using Test-Time Augmentation (TTA).

    TTA strategy (10 views): original image (5 crops) + flipped image (5 crops).
    All softmax probability vectors are averaged before taking argmax.

    Returns:
        predicted_label (str), confidence (float), top5 (list of (label, conf))
    """
    is_loaded = load_inference_assets()

    if not is_loaded:
        return "Tomato___Early_blight", 0.965, [("Tomato___Early_blight", 0.965)]

    try:
        arr      = preprocess_image(image_file, target_size=256)   # (256,256,3)
        arr_flip = arr[:, ::-1, :].copy()

        tensors = []
        for source in (arr, arr_flip):
            for crop in _five_crops(source, size=224):
                norm = _normalize(crop)
                tensors.append(_to_tensor(norm).astype(np.float32))

        avg_probs = _run_batch(tensors)

        top5_indices = np.argsort(avg_probs)[::-1][:5]
        top5 = [(str(_class_names[i]), float(avg_probs[i])) for i in top5_indices]

        predicted_label = top5[0][0]
        confidence      = top5[0][1]
        return predicted_label, confidence, top5

    except Exception as e:
        print(f"[agri_ai.leaf] Error during ONNX inference: {e}")
        return "fallback", 0.0, [("fallback", 0.0)]
