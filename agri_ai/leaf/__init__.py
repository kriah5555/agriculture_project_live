"""
agri_ai.leaf
------------
Leaf disease classification from a photo (ONNX + test-time augmentation).

Usage:
    from agri_ai.leaf import predict_leaf_disease, parse_class_label, get_disease_details

    label, confidence, top5 = predict_leaf_disease(image_file)
    plant, disease           = parse_class_label(label)
    details                  = get_disease_details(label)
"""
from .inference import predict_leaf_disease
from .utils import parse_class_label, get_disease_details, CONFIDENCE_THRESHOLD

__all__ = [
    "predict_leaf_disease",
    "parse_class_label",
    "get_disease_details",
    "CONFIDENCE_THRESHOLD",
]
