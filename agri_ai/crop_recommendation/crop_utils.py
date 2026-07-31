"""
agri_ai.crop_recommendation.crop_utils
-----------------------------------------
Crop-name normalization and Indian-local-name -> English mapping, used to
match India dataset crop names against the World crop-guide dataset.
Ported from the AgroZone prototype (apps/engine/crop_utils.py) verbatim.
"""
import re

INDIAN_TO_ENGLISH_CROP_NAMES = {
    "ragi": "finger millet", "jowar": "sorghum", "bajra": "pearl millet",
    "red gram": "pigeon pea", "tur": "pigeon pea", "arhar": "pigeon pea",
    "maize": "maize", "groundnut": "groundnut", "castor": "castor",
    "cotton": "cotton", "sugarcane": "sugarcane", "tobacco": "tobacco",
    "jute": "jute", "tea": "tea", "coffee": "coffee", "coconut": "coconut",
    "cashew": "cashew", "arecanut": "areca nut", "areca": "areca nut",
    "rubber": "rubber", "turmeric": "turmeric", "ginger": "ginger",
    "garlic": "garlic", "coriander": "coriander", "cumin": "cumin",
    "fenugreek": "fenugreek", "mustard": "mustard", "onion": "onion",
    "potato": "potato", "tomato": "tomato", "chilli": "chili pepper",
    "chili": "chili pepper", "chili pepper": "chili pepper",
    "brinjal": "eggplant", "ladies finger": "okra", "bhindi": "okra",
    "pumpkin": "pumpkin", "bottle gourd": "bottle gourd",
    "bitter gourd": "bitter gourd", "carrot": "carrot", "radish": "radish",
    "cabbage": "cabbage", "cauliflower": "cauliflower", "mango": "mango",
    "banana": "banana", "guava": "guava", "papaya": "papaya",
    "pomegranate": "pomegranate", "watermelon": "watermelon",
    "lemon": "citrus (orange)", "lime": "citrus (orange)",
    "orange": "citrus (orange)", "sweet lime": "citrus (orange)",
    "mosambi": "citrus (orange)", "sapota": "sapota", "chikoo": "sapota",
    "jackfruit": "jackfruit", "litchi": "litchi", "tamarind": "tamarind",
    "marigold": "marigold", "rose": "rose", "jasmine": "jasmine",
    "chrysanthemum": "chrysanthemum", "tuberose": "tuberose",
    "cassava": "cassava", "sweet potato": "cassava", "soybean": "soybean",
    "soya bean": "soybean", "sunflower": "sunflower", "sesame": "sesame",
    "til": "sesame", "linseed": "linseed", "safflower": "safflower",
    "niger": "niger seed", "field pea": "field pea", "pea": "field pea",
    "mat bean": "horse gram", "kulthi": "horse gram", "cowpea": "cowpea",
    "black gram": "black gram", "green gram": "green gram",
    "chickpea": "chickpea", "gram": "chickpea", "bengal gram": "chickpea",
    "chana": "chickpea", "lentil": "lentil", "masoor": "lentil",
    "pigeon pea": "pigeon pea", "barley": "barley", "wheat": "wheat",
    "rice": "rice", "paddy": "rice", "foxtail millet": "foxtail millet",
    "kodo millet": "kodo millet", "little millet": "little millet",
    "barnyard millet": "barnyard millet", "proso millet": "proso millet",
    "sisal": "sisal", "cocoa": "cocoa", "custard apple": "custard apple",
    "fig": "fig", "avocado": "avocado",
}


def normalize_crop_name(name: str) -> str:
    if not name:
        return ""
    n = name.strip().lower()
    n = re.sub(r"\s+", " ", n)
    n = re.sub(r"\([^)]*\)", "", n)          # remove parentheticals
    n = re.sub(r"\s*—.*$", "", n)            # remove em-dash trailing notes
    n = n.strip().rstrip(".,;: ")
    return n


def extract_base_name(crop_name: str) -> str:
    """'Rice (Paddy)' -> 'Rice', 'Bajra (Pearl Millet)' -> 'Bajra'"""
    name = crop_name.strip()
    parts = re.split(r"[\s]*\([^)]*\)[\s]*", name)
    base = parts[0].strip() if parts else name
    base = re.split(r"\s*—\s*", base)[0].strip()
    base = re.split(r"\s*,\s*", base)[0].strip()
    return base


def safe_get(value, default="Not available"):
    if value is None or (isinstance(value, str) and not value.strip()):
        return default
    return str(value).strip()