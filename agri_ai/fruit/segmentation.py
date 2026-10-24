"""
agri_ai.fruit.segmentation
--------------------------
Finds individual fruits in a photo with classical OpenCV (S/V + per-fruit
colour masks, watershed, contours), cuts out a 224x224 crop per fruit and
draws the annotated result image.
Ported from HarvestLenz `segmentation_service` + `background_removal`.
"""
import logging

import cv2
import numpy as np

logger = logging.getLogger(__name__)

_MIN_AREA_RATIO  = 0.01
_MAX_AREA_RATIO  = 0.85
_MIN_CIRCULARITY = 0.15
_MIN_SOLIDITY    = 0.50
_MAX_ASPECT      = 4.0

# HSV ranges a region must be >=25% made of to count as the selected fruit.
_COLOR_RANGES = {
    'grapes': [
        ((25, 30, 30), (85, 255, 255)),
        ((120, 30, 30), (165, 255, 255)),
    ],
    'pomegranate': [
        ((0, 40, 50), (10, 255, 255)),
        ((160, 40, 50), (180, 255, 255)),
    ],
    'pineapple': [
        ((15, 40, 50), (35, 255, 255)),
        ((25, 25, 40), (85, 255, 255)),
    ],
    'mango': [
        ((10, 40, 50), (30, 255, 255)),
        ((20, 30, 60), (40, 255, 255)),
    ],
}
_DEFAULT_COLOR_RANGE = [((0, 30, 30), (180, 255, 255))]


def _full_image_region(h, w, confidence):
    return {
        'mask'      : np.ones((h, w), dtype=np.uint8) * 255,
        'bbox'      : [0, 0, w, h],
        'contour'   : np.array([[[0, 0]], [[w, 0]], [[w, h]], [[0, h]]], dtype=np.int32),
        'area'      : float(h * w),
        'confidence': confidence,
        'fruit_id'  : 'FRUIT_0001',
    }


def segment_fruits(image, fruit_type='mango', is_single=False):
    """
    Returns a list of fruit regions: {mask, bbox [x1,y1,x2,y2], contour, area, confidence, fruit_id}.
    `is_single=True` treats the whole photo as one fruit.
    """
    if image is None or image.size == 0:
        return []
    h, w = image.shape[:2]
    if is_single:
        return [_full_image_region(h, w, 0.95)]

    # Work on a <=640px-high copy, then scale regions back up.
    work_h = min(h, 640)
    work_w = int(w * (work_h / h)) if h > 0 else w
    small  = cv2.resize(image, (work_w, work_h))
    scale_x, scale_y = w / work_w, h / work_h

    hsv = cv2.cvtColor(small, cv2.COLOR_BGR2HSV)
    regions = _multi_strategy_segment(small, hsv, fruit_type)

    valid = [_scale_region(r, scale_x, scale_y) for r in regions if _validate_region(r, work_w, work_h)]
    valid = _remove_duplicates(valid)

    for i, region in enumerate(valid, 1):
        region['fruit_id'] = f'FRUIT_{i:04d}'
        region['mask'] = cv2.resize(region['mask'], (w, h), interpolation=cv2.INTER_NEAREST)

    if not valid:
        logger.warning('No valid fruit regions detected, using full image as fallback')
        valid = [_full_image_region(h, w, 0.50)]
    return valid


def _multi_strategy_segment(image, hsv, fruit_type):
    """Try several foreground masks x (watershed / contour) and keep the best-scoring set."""
    h, w = image.shape[:2]
    img_area = h * w
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))

    # Strategy A: S>60 & V>80
    s_mask = cv2.threshold(hsv[:, :, 1], 60, 255, cv2.THRESH_BINARY)[1]
    v_mask = cv2.threshold(hsv[:, :, 2], 80, 255, cv2.THRESH_BINARY)[1]
    mask_a = cv2.bitwise_and(s_mask, v_mask)
    mask_a = cv2.morphologyEx(mask_a, cv2.MORPH_OPEN, kernel, iterations=2)
    mask_a = cv2.morphologyEx(mask_a, cv2.MORPH_CLOSE, kernel, iterations=1)

    # Strategy B: fruit-specific colour mask
    mask_b = _segment_by_color(hsv, fruit_type)
    mask_b = cv2.morphologyEx(mask_b, cv2.MORPH_OPEN, kernel, iterations=2)
    mask_b = cv2.morphologyEx(mask_b, cv2.MORPH_CLOSE, kernel, iterations=1)

    all_results = []
    for mask_name, mask in (('sv_60_80', mask_a), (f'color_{fruit_type}', mask_b)):
        fg_ratio = cv2.countNonZero(mask) / img_area
        if fg_ratio < 0.05 or fg_ratio > 0.95:
            continue

        eroded = cv2.erode(mask, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7)), iterations=2)
        candidates = (
            ('erode_ws', _watershed_segment(image, eroded, threshold_ratio=0.05)),
            ('ws',       _watershed_segment(image, mask, threshold_ratio=0.08)),
            ('contour',  _contour_based_segment(mask)),
        )
        for name, raw in candidates:
            valid = [r for r in raw if _validate_region(r, w, h)]
            valid = _filter_by_color_match(valid, hsv, fruit_type)
            all_results.append((f'{mask_name}_{name}', valid, raw))

    # Score = count x covered area, so over-segmentation isn't favoured.
    best_name, best_valid, best_score = None, [], 0
    for name, valid, _raw in all_results:
        if not valid:
            continue
        score = len(valid) * (sum(r['area'] for r in valid) / img_area)
        if score > best_score:
            best_name, best_valid, best_score = name, valid, score

    if best_valid:
        logger.info('Best segmentation: %s (%d regions, score=%.3f)', best_name, len(best_valid), best_score)
        return best_valid

    for name, _valid, raw in all_results:
        if raw:
            logger.info('Using raw results from %s (%d regions)', name, len(raw))
            return raw
    return []


def _segment_by_color(hsv, fruit_type):
    def rng(lo, hi):
        return cv2.inRange(hsv, np.array(lo), np.array(hi))

    if fruit_type == 'grapes':
        return cv2.bitwise_or(rng([25, 20, 20], [85, 255, 255]), rng([120, 20, 20], [165, 255, 255]))
    if fruit_type == 'pomegranate':
        return cv2.bitwise_or(rng([0, 30, 40], [10, 255, 255]), rng([160, 30, 40], [180, 255, 255]))
    if fruit_type == 'pineapple':
        return cv2.bitwise_or(rng([15, 30, 40], [35, 255, 255]), rng([25, 20, 30], [85, 255, 255]))

    _, s_mask = cv2.threshold(hsv[:, :, 1], 60, 255, cv2.THRESH_BINARY)
    _, v_mask = cv2.threshold(hsv[:, :, 2], 80, 255, cv2.THRESH_BINARY)
    return cv2.bitwise_and(s_mask, v_mask)


def _watershed_segment(image, foreground_mask, threshold_ratio=0.06):
    """Watershed to split touching fruits."""
    sure_bg = cv2.dilate(foreground_mask, np.ones((3, 3), np.uint8), iterations=3)
    dist    = cv2.distanceTransform(foreground_mask, cv2.DIST_L2, 5)
    max_dist = dist.max()
    if max_dist <= 0:
        return []

    _, sure_fg = cv2.threshold(dist, threshold_ratio * max_dist, 255, 0)
    sure_fg = np.uint8(sure_fg)
    unknown = cv2.subtract(sure_bg, sure_fg)

    ret, markers = cv2.connectedComponents(sure_fg)
    if ret <= 1:
        return []
    markers = markers + 1
    markers[unknown == 255] = 0
    cv2.watershed(image.copy(), markers)

    regions = []
    for label in range(2, ret + 1):
        label_mask = np.uint8(markers == label)
        contours, _ = cv2.findContours(label_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            continue
        c = max(contours, key=cv2.contourArea)
        x, y, cw, ch = cv2.boundingRect(c)
        full_mask = np.zeros_like(foreground_mask)
        full_mask[markers == label] = 255
        regions.append({
            'mask': full_mask, 'bbox': [x, y, x + cw, y + ch], 'contour': c,
            'area': float(cv2.contourArea(c)), 'confidence': 0.85,
        })
    return regions


def _contour_based_segment(foreground_mask):
    h, w = foreground_mask.shape[:2]
    min_area = int(h * w * 0.005)
    contours, _ = cv2.findContours(foreground_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    regions = []
    for c in contours:
        area = cv2.contourArea(c)
        if area < min_area:
            continue
        x, y, cw, ch = cv2.boundingRect(c)
        mask = np.zeros_like(foreground_mask)
        cv2.drawContours(mask, [c], -1, 255, -1)
        regions.append({
            'mask': mask, 'bbox': [x, y, x + cw, y + ch], 'contour': c,
            'area': float(area), 'confidence': 0.70,
        })
    return regions


def _filter_by_color_match(regions, hsv, fruit_type):
    """Drop regions with <25% fruit-coloured pixels (table, basket, hands...)."""
    if not regions:
        return []
    combined = np.zeros(hsv.shape[:2], dtype=np.uint8)
    for lo, hi in _COLOR_RANGES.get(fruit_type, _DEFAULT_COLOR_RANGE):
        combined = cv2.bitwise_or(combined, cv2.inRange(hsv, np.array(lo), np.array(hi)))

    kept = []
    for region in regions:
        region_area = cv2.countNonZero(region['mask'])
        if region_area == 0:
            continue
        match_ratio = cv2.countNonZero(cv2.bitwise_and(combined, region['mask'])) / region_area
        if match_ratio < 0.25:
            continue
        region['confidence'] = min(0.95, 0.5 + match_ratio * 0.5)
        kept.append(region)
    return kept


def _validate_region(region, img_w, img_h):
    """Plausible-fruit checks: size, circularity, solidity, aspect ratio."""
    area = region['area']
    img_area = img_w * img_h
    area_ratio = area / img_area if img_area > 0 else 0
    if area_ratio < _MIN_AREA_RATIO or area_ratio > _MAX_AREA_RATIO:
        return False

    contour = region['contour']
    perimeter = cv2.arcLength(contour, True)
    if perimeter == 0 or 4 * np.pi * area / (perimeter ** 2) < _MIN_CIRCULARITY:
        return False

    hull_area = cv2.contourArea(cv2.convexHull(contour))
    if hull_area == 0 or area / hull_area < _MIN_SOLIDITY:
        return False

    x1, y1, x2, y2 = region['bbox']
    bw, bh = x2 - x1, y2 - y1
    return max(bw, bh) / max(min(bw, bh), 1) <= _MAX_ASPECT


def _scale_region(region, scale_x, scale_y):
    x1, y1, x2, y2 = region['bbox']
    region['bbox'] = [max(0, int(x1 * scale_x)), max(0, int(y1 * scale_y)),
                      int(x2 * scale_x), int(y2 * scale_y)]
    contour = region['contour'].copy()
    contour[:, :, 0] = (contour[:, :, 0] * scale_x).astype(np.int32)
    contour[:, :, 1] = (contour[:, :, 1] * scale_y).astype(np.int32)
    region['contour'] = contour
    region['fruit_id'] = ''
    return region


def _remove_duplicates(regions, iou_threshold=0.35):
    if len(regions) <= 1:
        return regions
    regions.sort(key=lambda r: r['area'], reverse=True)
    keep = []
    for region in regions:
        b = region['bbox']
        is_dup = False
        for kept in keep:
            k = kept['bbox']
            inter = max(0, min(b[2], k[2]) - max(b[0], k[0])) * max(0, min(b[3], k[3]) - max(b[1], k[1]))
            union = region['area'] + kept['area'] - inter
            if union > 0 and inter / union > iou_threshold:
                is_dup = True
                break
        if not is_dup:
            keep.append(region)
    return keep


def extract_fruit_crop(image, bbox, padding_ratio=0.05, target_size=(224, 224)):
    """Padded bbox crop resized to the grading model's input size (BGR), or None."""
    if image is None:
        return None
    h_img, w_img = image.shape[:2]
    x1, y1, x2, y2 = bbox
    pad_w = int((x2 - x1) * padding_ratio)
    pad_h = int((y2 - y1) * padding_ratio)
    crop = image[max(0, y1 - pad_h):min(h_img, y2 + pad_h), max(0, x1 - pad_w):min(w_img, x2 + pad_w)]
    if crop.size == 0:
        return None
    return cv2.resize(crop, target_size, interpolation=cv2.INTER_AREA)


_DRAW_COLORS = {          # BGR
    'Good'    : (0, 200, 0),
    'Better'  : (0, 165, 255),
    'Reject'  : (0, 0, 255),
    'Mismatch': (57, 53, 229),
}


def draw_segmentation(image, regions, fruits):
    """Image with each fruit's mask tinted, boxed and labelled with its grade."""
    overlay = image.copy()
    grade_by_id = {f['fruit_id']: f['grade'] for f in fruits}
    scale = max(0.5, min(image.shape[:2]) / 800)

    for region in regions:
        fruit_id = region.get('fruit_id', '')
        grade    = grade_by_id.get(fruit_id, '')
        color    = _DRAW_COLORS.get(grade, (0, 255, 255))

        tint = np.zeros_like(overlay)
        tint[region['mask'] > 0] = color
        overlay = cv2.addWeighted(overlay, 0.7, tint, 0.3, 0)

        x1, y1, x2, y2 = region['bbox']
        cv2.rectangle(overlay, (x1, y1), (x2, y2), color, max(2, int(2 * scale)))

        label = f'{fruit_id} | {grade}' if grade else fruit_id
        (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5 * scale, 1)
        text_y = max(y1 - 8, th + 4)
        cv2.rectangle(overlay, (x1, text_y - th - 4), (x1 + tw + 6, text_y + 2), color, -1)
        cv2.putText(overlay, label, (x1 + 3, text_y - 2), cv2.FONT_HERSHEY_SIMPLEX,
                    0.5 * scale, (255, 255, 255), max(1, int(scale)), cv2.LINE_AA)
    return overlay
