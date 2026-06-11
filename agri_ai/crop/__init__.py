"""
agri_ai.crop
------------
Crop recommendation model (22 crops).

Usage:
    from agri_ai.crop import run_model

    crop = run_model({'N': [120], 'P': [18], 'K': [200],
                      'temperature': [26.0], 'humidity': [65.0],
                      'ph': [6.8], 'rainfall': [900.0]})
"""

from .model import run_model, CROP_LABELS

__all__ = ["run_model", "CROP_LABELS"]