"""agri_ai.leaf.utils — helpers shared by the LeafLenz device API."""
import os
import json

DISEASE_DATA_PATH = os.path.join(os.path.dirname(__file__), 'models', 'disease_data.json')

try:
    with open(DISEASE_DATA_PATH, 'r') as f:
        DISEASE_INFO = json.load(f)
except Exception as e:
    print(f"[agri_ai.leaf] Error loading disease_data.json: {e}")
    DISEASE_INFO = {}

CONFIDENCE_THRESHOLD = 0.18


def parse_class_label(label):
    """Parses a class label like 'Tomato___Bacterial_spot' into plant and disease names."""
    if "___" in label:
        plant, disease = label.split("___", 1)
        plant   = plant.replace("_", " ").title()
        disease = disease.replace("_", " ").title()
        if disease.lower() == "healthy":
            disease = "Healthy"
    else:
        plant   = "Unknown Plant"
        disease = label.replace("_", " ").title()
    return plant, disease


def get_disease_details(label):
    """Look up description/symptoms/treatment for a raw predicted label, with a fallback entry."""
    details = DISEASE_INFO.get(label)
    if not details:
        plant, disease = parse_class_label(label)
        details = DISEASE_INFO.get("fallback", {
            "plant_name": plant,
            "disease_name": disease,
            "description": "No specific details available in local database for this condition.",
            "symptoms": "N/A",
            "treatment_prevention": "N/A",
        })
    return details
