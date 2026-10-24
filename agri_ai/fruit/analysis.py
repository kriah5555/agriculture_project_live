"""
agri_ai.fruit.analysis
----------------------
Full HarvestLenz pipeline for one photo, synchronous and DB-free:

    decode -> (auto-detect fruit) -> segment -> crop -> verify fruit type
    -> grade (CNN + defect score) -> shelf life / market / price -> summary
    -> annotated image

Ported from HarvestLenz `analysis_orchestrator.analyze()`.
"""
import logging

import cv2
import numpy as np

from . import grading, rules, segmentation, verification
from .rules import GRADE_BETTER, GRADE_GOOD, GRADE_MISMATCH, GRADE_REJECT

logger = logging.getLogger(__name__)

MIN_GRADE_CONFIDENCE = 0.40   # fruits graded below this are dropped (likely not a fruit)


class FruitAnalysisError(ValueError):
    """Bad input the caller should report as a 400 (unreadable image, unsupported fruit)."""


def _read_image(image_file):
    data = image_file.read()
    if hasattr(image_file, 'seek'):
        image_file.seek(0)
    image = cv2.imdecode(np.frombuffer(data, dtype=np.uint8), cv2.IMREAD_COLOR)
    if image is None:
        raise FruitAnalysisError('Could not read the image. Upload a JPEG, PNG or WEBP photo.')
    return image


def analyze_fruit_image(image_file, fruit_type='auto', is_single=True):
    """
    Returns (result, annotated_jpeg_bytes).

    result = {
        fruit_type, fruit_name, auto_detected, is_single, total_fruits,
        summary {good, better, reject}, mismatch, average_shelf_life,
        average_confidence, fruits [...], image_width, image_height,
        + overall_grade, score, recommended_market, total_price,
          estimated_selling_price, profit_estimation, *_percentage, ai_recommendations
    }
    Raises FruitAnalysisError for bad input, RuntimeError if the model is missing.
    """
    image = _read_image(image_file)
    h_img, w_img = image.shape[:2]

    fruit = (fruit_type or 'auto').lower().strip()
    auto_detected = fruit == 'auto'
    if auto_detected:
        detected = verification.classify_fruit(image)['fruit_type']
        if detected not in rules.SUPPORTED_FRUITS:
            raise FruitAnalysisError(
                'Could not recognise the fruit automatically. Please select the fruit type.'
            )
        fruit = detected
    elif fruit not in rules.SUPPORTED_FRUITS:
        raise FruitAnalysisError(
            f"Unsupported fruit_type '{fruit_type}'. Supported: {', '.join(rules.SUPPORTED_FRUITS)} or 'auto'."
        )

    regions = segmentation.segment_fruits(image, fruit_type=fruit, is_single=is_single)

    crops = {}
    for region in regions:
        crop = segmentation.extract_fruit_crop(image, region['bbox'])
        if crop is not None:
            crops[region['fruit_id']] = crop

    # Fruit-type check before grading; mismatched crops are not graded.
    mismatch_warning = None
    mismatched = set()
    for fid, crop in crops.items():
        check = verification.verify_fruit(crop, fruit)
        if not check['is_match']:
            mismatched.add(fid)
            mismatch_warning = mismatch_warning or check['warning']
            logger.warning('Fruit mismatch for %s: expected=%s detected=%s',
                           fid, fruit, check['predicted_fruit'])

    graded = grading.grade_crops({fid: c for fid, c in crops.items() if fid not in mismatched}, fruit)
    for fid in mismatched:
        graded[fid] = {'grade': GRADE_MISMATCH, 'confidence': 1.0, 'defect_score': 1.0,
                       'defects': ['fruit_type_mismatch']}

    fruits = []
    for region in regions:
        fid = region['fruit_id']
        res = graded.get(fid)
        if res is None or res['confidence'] < MIN_GRADE_CONFIDENCE:
            continue
        grade = res['grade']
        if grade == GRADE_MISMATCH:
            shelf_days, market, price = 0, 'N/A - Fruit Mismatch', 0.0
        else:
            shelf_days = rules.predict_shelf_life(fruit, grade, res['defect_score'])
            market     = rules.recommend_market(fruit, grade)['market']
            price      = rules.fruit_price(fruit, grade)
        fruits.append({
            'fruit_id'             : fid,
            'grade'                : grade,
            'confidence'           : res['confidence'],
            'bbox'                 : [int(v) for v in region['bbox']],
            'defect_score'         : res['defect_score'],
            'defects'              : res['defects'],
            'shelf_life_days'      : shelf_days,
            'market_recommendation': market,
            'price'                : price,
            'grade_color'          : rules.GRADE_COLORS.get(grade, '#E57373'),
        })

    good     = sum(1 for f in fruits if f['grade'] == GRADE_GOOD)
    better   = sum(1 for f in fruits if f['grade'] == GRADE_BETTER)
    reject   = sum(1 for f in fruits if f['grade'] in (GRADE_REJECT, GRADE_MISMATCH))
    total    = len(fruits)
    mismatch = any(f['grade'] == GRADE_MISMATCH for f in fruits)

    overall = rules.overall_from_counts(fruit, good, better, reject, mismatch=mismatch)
    if mismatch and mismatch_warning:
        overall['ai_recommendations'][0] = mismatch_warning

    result = {
        'fruit_type'        : fruit,
        'fruit_name'        : rules.fruit_display_name(fruit),
        'auto_detected'     : auto_detected,
        'is_single'         : bool(is_single),
        'total_fruits'      : total,
        'summary'           : {'good': good, 'better': better, 'reject': reject},
        'mismatch'          : mismatch,
        'average_shelf_life': 0.0 if (mismatch or not total) else
                              round(sum(f['shelf_life_days'] for f in fruits) / total, 1),
        'average_confidence': round(sum(f['confidence'] for f in fruits) / total, 4) if total else 0.0,
        'fruits'            : fruits,
        'image_width'       : w_img,
        'image_height'      : h_img,
        **overall,
    }

    annotated = segmentation.draw_segmentation(
        image, [r for r in regions if r['fruit_id'] in {f['fruit_id'] for f in fruits}], fruits
    )
    ok, buf = cv2.imencode('.jpg', annotated, [cv2.IMWRITE_JPEG_QUALITY, 85])
    return result, (buf.tobytes() if ok else None)
