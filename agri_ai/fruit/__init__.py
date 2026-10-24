"""
agri_ai.fruit
-------------
HarvestLenz fruit quality grading from a photo (Keras MobileNetV2 per fruit +
OpenCV segmentation). Ported from the standalone `agriculture_ai` (HarvestLenz) app.

Usage:
    from agri_ai.fruit import analyze_fruit_image, FruitAnalysisError, SUPPORTED_FRUITS

    result, annotated_jpeg = analyze_fruit_image(image_file, fruit_type='mango', is_single=True)
    overall = overall_from_counts('mango', good=3, better=1, reject=0)
"""
from .analysis import analyze_fruit_image, FruitAnalysisError
from .rules import FRUIT_INFO, SUPPORTED_FRUITS, fruit_display_name, overall_from_counts

__all__ = [
    "analyze_fruit_image",
    "FruitAnalysisError",
    "FRUIT_INFO",
    "SUPPORTED_FRUITS",
    "fruit_display_name",
    "overall_from_counts",
]
