"""
agri_ai.features
----------------
Environmental feature fetchers used by the soil inference pipeline.

Usage:
    from agri_ai.features import get_weather, get_ndvi, get_elevation, get_soil_texture
"""

from .weather      import get_weather
from .ndvi         import get_ndvi
from .elevation    import get_elevation
from .soil_texture import get_soil_texture

__all__ = ["get_weather", "get_ndvi", "get_elevation", "get_soil_texture"]