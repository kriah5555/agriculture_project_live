"""
agri_ai.fruit.keras_backend
---------------------------
Loads the HarvestLenz Keras models (.keras / .h5) as-is.

Keras 3 runs on TensorFlow when it is installed; otherwise (e.g. Python 3.14,
which has no TensorFlow wheels) it falls back to the JAX backend. Set
KERAS_BACKEND in the environment to force one.
"""
import importlib.util
import inspect
import logging
import os
import re
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


_compat_patched = False


def _patch_initializer_compat(keras):
    """
    The models were saved with Keras 3.15, which writes extra initializer
    settings ('input_axes', 'output_axes'). Older Keras 3 releases (3.12 is the
    newest on Python 3.10) reject unknown settings, so make Initializer.from_config
    drop arguments the class's __init__ doesn't accept. Initializers only matter
    for training, so inference is unaffected.
    """
    global _compat_patched
    if _compat_patched:
        return
    _compat_patched = True

    def from_config(cls, config):
        params = inspect.signature(cls.__init__).parameters
        if not any(p.kind == p.VAR_KEYWORD for p in params.values()):
            config = {k: v for k, v in config.items() if k in params}
        return cls(**config)

    keras.initializers.Initializer.from_config = classmethod(from_config)

    # Same for layers (e.g. BatchNormalization's 'renorm*' settings): retry
    # without whatever arguments the installed Keras reports as unrecognised.
    operation_from_config = keras.Operation.from_config.__func__

    def layer_from_config(cls, config):
        config = dict(config)
        while True:
            try:
                return operation_from_config(cls, config)
            except (TypeError, ValueError) as e:
                unknown = set(re.findall(r"'(\w+)'", str(e).split('Unrecognized keyword arguments', 1)[-1]))
                unknown |= set(re.findall(r"unexpected keyword argument '(\w+)'", str(e)))
                unknown &= set(config)
                if not unknown:
                    raise
                for key in unknown:
                    config.pop(key)

    keras.Operation.from_config = classmethod(layer_from_config)


def load_keras_model(path):
    """Load a Keras model for inference, or None (logged) if it can't be loaded."""
    with _lock:
        _select_backend()
        try:
            import keras
            _patch_initializer_compat(keras)
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
