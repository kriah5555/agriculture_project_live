"""
agri_ai.fruit.keras_backend
---------------------------
Loads the HarvestLenz Keras models (.keras / .h5) as-is.

Keras 3 runs on TensorFlow when it is installed; otherwise (e.g. Python 3.14,
which has no TensorFlow wheels) it falls back to the JAX backend. Set
KERAS_BACKEND in the environment to force one.
"""
import importlib.util
import logging
import os
import threading

import cv2
import numpy as np

logger = logging.getLogger(__name__)

_lock = threading.Lock()


def _select_backend():
    if 'KERAS_BACKEND' in os.environ:
        return
    if importlib.util.find_spec('tensorflow') is None:
        os.environ['KERAS_BACKEND'] = 'jax'


def load_keras_model(path):
    """Load a Keras model for inference, or None (logged) if it can't be loaded."""
    with _lock:
        _select_backend()
        try:
            import keras
            model = keras.models.load_model(path, compile=False)
            logger.info('[agri_ai.fruit] Loaded %s (backend=%s)', os.path.basename(path), keras.backend.backend())
            return model
        except Exception:
            logger.exception('[agri_ai.fruit] Failed to load Keras model %s', path)
            return None


def mobilenet_preprocess(img_bgr):
    """
    224x224 RGB float32 scaled to [-1, 1] — identical to
    keras.applications.mobilenet_v2.preprocess_input used in training.
    """
    img = cv2.resize(img_bgr, (224, 224))
    rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB).astype(np.float32)
    return rgb / 127.5 - 1.0
