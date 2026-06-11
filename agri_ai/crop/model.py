"""
agri_ai.crop.model
------------------
Crop recommendation model — predicts the best crop from soil nutrients + climate.

Inputs : N, P, K (kg/ha), temperature (°C), humidity (%), ph, rainfall (mm)
Output : crop name string  (one of 22 crops)
"""

import os
import pickle
import pandas as pd

_MODEL_PATH = os.path.join(os.path.dirname(__file__), "models", "classifier.pkl")

CROP_LABELS = {
    0: "apple",       1: "banana",      2: "blackgram",  3: "chickpea",
    4: "coconut",     5: "coffee",      6: "cotton",     7: "grapes",
    8: "jute",        9: "kidneybeans", 10: "lentil",    11: "maize",
    12: "mango",      13: "mothbeans",  14: "mungbean",  15: "muskmelon",
    16: "orange",     17: "papaya",     18: "pigeonpeas",19: "pomegranate",
    20: "rice",       21: "watermelon",
}

_model = None


def _load():
    global _model
    if _model is None:
        with open(_MODEL_PATH, "rb") as f:
            _model = pickle.load(f)
    return _model


def run_model(soil_data: dict) -> str:
    """
    Predict the recommended crop.

    Parameters
    ----------
    soil_data : dict with list values, e.g.
        {'N': [120], 'P': [18], 'K': [200],
         'temperature': [26.0], 'humidity': [65.0],
         'ph': [6.8], 'rainfall': [900.0]}

    Returns
    -------
    str — crop name
    """
    model      = _load()
    input_df   = pd.DataFrame(soil_data)
    prediction = model.predict(input_df)
    return CROP_LABELS[prediction[0]]