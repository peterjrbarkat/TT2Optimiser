import cv2
import numpy as np
from pathlib import Path
import json

# === Choose ONE OCR backend ===
USE_EASYOCR = True  # EasyOCR only

import easyocr
ocr_reader = easyocr.Reader(['en'], gpu=False)

# ----------------- utilities -----------------
def non_max_suppression(boxes, scores, overlapThresh=0.35):
    if len(boxes) == 0: return []
    boxes = np.array(boxes, dtype=float)
    scores = np.array(scores, dtype=float)
    x1, y1, x2, y2 = boxes[:,0], boxes[:,1], boxes[:,2], boxes[:,3]
    areas = (x2 - x1 + 1) * (y2 - y1 + 1)
    idxs = scores.argsort()[::-1]
    keep = []
    while len(idxs) > 0:
        i = idxs[0]
        keep.append(i)
        xx1 = np.maximum(x1[i], x1[idxs[1:]])
        yy1 = np.maximum(y1[i], y1[idxs[1:]])
        xx2 = np.minimum(x2[i], x2[idxs[1:]])
        yy2 = np.minimum(y2[i], y2[idxs[1:]])
        w = np.maximum(0, xx2 - xx1 + 1)
        h = np.maximum(0, yy2 - yy1 + 1)
        inter = w * h
        iou = inter / (areas[i] + areas[idxs[1:]] - inter + 1e-7)
        idxs = idxs[np.where(iou <= overlapThresh)[0] + 1]
    return [tuple(map(int, boxes[i])) for i in keep], [float(scores[i]) for i in keep]

def load_templates(templates_dir):
    """Return dict: name -> (image, key) where key is the name."""
    templates = {}
    for p in Path(templates_dir).glob("*.png"):
        img = cv2.imread(str(p), cv2.IMREAD_UNCHANGED)
        if img is None: 
            continue
        templates[p.stem] = img
    if not templates:
        raise RuntimeError(f"No templates found in {templates_dir}")
    return templates

def prepare_for_match(img):
    # Robust preprocessing for template matching (grayscale + optional alpha mask)
    mask = None
    src = img
    if img.shape[2] == 4:
        bgr = img[:,:,:3]
        a = img[:,:,3]  # alpha 0..255
        # Trim transparent border
        ys, xs = np.where(a > 10)
        if len(xs) > 0 and len(ys) > 0:
            x_min, x_max = xs.min(), xs.max()
            y_min, y_max = ys.min(), ys.max()
            bgr = bgr[y_min:y_max+1, x_min:x_max+1]
            a = a[y_min:y_max+1, x_min:x_max+1]
        src = bgr
        # Build binary mask from alpha (focus on opaque icon only)
        mask = (a > 10).astype(np.uint8) * 255
    gray = cv2.cvtColor(src, cv2.COLOR_BGR2GRAY)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
    gray = clahe.apply(gray)
    # Return both gray and trimmed BGR so we can do color-aware matching if desired
    return gray, mask, src

def _top_peaks(res, threshold, max_peaks=10):
    """Return list of (y,x) peak positions above threshold using non-maximum suppression on the response map."""
    if res.size == 0:
        return []
    # Ensure numeric type
    res_norm = res.copy()
    # Local maxima with 3x3 neighborhood
    mx = cv2.dilate(res_norm, np.ones((3,3), np.uint8))
    peaks_mask = (res_norm == mx) & (res_norm >= threshold)
    ys, xs = np.where(peaks_mask)
    scores = res_norm[ys, xs]
    order = np.argsort(-scores)
    ys = ys[order][:max_peaks]
    xs = xs[order][:max_peaks]
    return list(zip(ys, xs)), list(scores[order][:max_peaks])

def multiscale_match(scene_gray, tmpl_gray, name, mask=None, scales=np.linspace(0.5, 1.3, 11), th=0.55, *, use_color=False, scene_bgr=None, tmpl_bgr=None, scene_edges=None, max_peaks_per_scale=6):
    """Return list of (x1,y1,x2,y2,score,name) using intensity + edge assisted matching.
       Supports an optional template mask (from alpha)."""
    h_t, w_t = tmpl_gray.shape[:2]
    scene_edges = scene_edges if scene_edges is not None else cv2.Canny(scene_gray, 50, 150)
    tmpl_edges_full = cv2.Canny(tmpl_gray, 50, 150)
    hits = []
    for s in scales:
        tw, thh = int(w_t*s), int(h_t*s)
        if tw < 16 or thh < 16: 
            continue
        tmpl_resized = cv2.resize(tmpl_gray, (tw, thh), interpolation=cv2.INTER_AREA)
        edge_resized = cv2.resize(tmpl_edges_full, (tw, thh), interpolation=cv2.INTER_AREA)
        if mask is not None:
            mask_resized = cv2.resize(mask, (tw, thh), interpolation=cv2.INTER_NEAREST)
            res_int = cv2.matchTemplate(scene_gray, tmpl_resized, cv2.TM_CCORR_NORMED, mask=mask_resized)
        else:
            res_int = cv2.matchTemplate(scene_gray, tmpl_resized, cv2.TM_CCOEFF_NORMED)
        res_edge = cv2.matchTemplate(scene_edges, edge_resized, cv2.TM_CCOEFF_NORMED)

        # Optional color-aware score across channels
        if use_color and scene_bgr is not None and tmpl_bgr is not None:
            tmpl_bgr_resized = cv2.resize(tmpl_bgr, (tw, thh), interpolation=cv2.INTER_AREA)
            if mask is not None:
                mask_resized = cv2.resize(mask, (tw, thh), interpolation=cv2.INTER_NEAREST)
            res_cols = []
            for c in range(3):
                if mask is not None:
                    res_c = cv2.matchTemplate(scene_bgr[:,:,c], tmpl_bgr_resized[:,:,c], cv2.TM_CCORR_NORMED, mask=mask_resized)
                else:
                    res_c = cv2.matchTemplate(scene_bgr[:,:,c], tmpl_bgr_resized[:,:,c], cv2.TM_CCOEFF_NORMED)
                res_cols.append(res_c)
            res_color = (res_cols[0] + res_cols[1] + res_cols[2]) / 3.0
            res = 0.45*res_int + 0.35*res_edge + 0.20*res_color
        else:
            # Combine scores; ensure same shape
            res = 0.65*res_int + 0.35*res_edge
        # Select only top local maxima to avoid iterating over all above-threshold pixels
        (ys_xs, scores) = _top_peaks(res, th, max_peaks=max_peaks_per_scale)
        for (y, x), score in zip(ys_xs, scores):
            hits.append((x, y, x+tw, y+thh, float(score), name))
    return hits

def crop_count_badge(scene, box, badge_rel=(0.60, 0.60, 1.00, 1.00)):
    """
    Crop a bottom-right sub-ROI where the count badge typically is.
    badge_rel is (x1_rel, y1_rel, x2_rel, y2_rel) relative to the icon box.
    """
    x1, y1, x2, y2 = box
    w, h = x2 - x1, y2 - y1
    bx1 = x1 + int(w * badge_rel[0])
    by1 = y1 + int(h * badge_rel[1])
    bx2 = x1 + int(w * badge_rel[2])
    by2 = y1 + int(h * badge_rel[3])
    # small padding to be safe
    pad = max(2, int(0.02 * max(w, h)))
    bx1 = max(0, bx1 - pad); by1 = max(0, by1 - pad)
    bx2 = min(scene.shape[1], bx2 + pad); by2 = min(scene.shape[0], by2 + pad)
    return scene[by1:by2, bx1:bx2]

def crop_center_down_box(scene, box):
    """
    From the middle of the detected icon, draw a box the same size as the icon,
    positioned directly below the middle line. Use that as OCR ROI.
    """
    x1, y1, x2, y2 = box
    w, h = x2 - x1, y2 - y1
    mid_y = y1 + h // 2
    # shift box to the right by half the icon width
    bx1 = x1 + (w // 2)
    bx2 = bx1 + w
    by1 = mid_y
    by2 = mid_y + h
    # clamp
    bx1 = max(0, bx1); by1 = max(0, by1)
    bx2 = min(scene.shape[1], bx2); by2 = min(scene.shape[0], by2)
    return scene[by1:by2, bx1:bx2], (bx1, by1, bx2, by2)

def crop_rel(scene, box, rel):
    """Crop using relative box (x1r,y1r,x2r,y2r) within the icon box."""
    x1, y1, x2, y2 = box
    w, h = x2 - x1, y2 - y1
    rx1, ry1, rx2, ry2 = rel
    bx1 = x1 + int(w * rx1)
    by1 = y1 + int(h * ry1)
    bx2 = x1 + int(w * rx2)
    by2 = y1 + int(h * ry2)
    bx1 = max(0, bx1); by1 = max(0, by1)
    bx2 = min(scene.shape[1], bx2); by2 = min(scene.shape[0], by2)
    return scene[by1:by2, bx1:bx2], (bx1, by1, bx2, by2)

def generate_ocr_rois(scene, box):
    """
    Produce a small set of candidate OCR regions. Order matters; we return
    from most-likely to fallback.
    """
    rois = []
    # 1) Center-down shifted right half-width (requested)
    r1, b1 = crop_center_down_box(scene, box)
    rois.append((r1, b1))
    # 2) Center-down shifted right ~1/3 width
    x1, y1, x2, y2 = box
    w = x2 - x1
    alt = (x1 + (w//3), y1, x2 + (w//3), y2)
    r2, b2 = crop_center_down_box(scene, alt)
    rois.append((r2, b2))
    # 3) Center-down shifted right ~2/3 width
    alt2 = (x1 + (2*w//3), y1, x2 + (2*w//3), y2)
    r3, b3 = crop_center_down_box(scene, alt2)
    rois.append((r3, b3))
    # 4) Bottom-left relative window (earlier heuristic)
    r4, b4 = crop_rel(scene, box, (0.00, 0.62, 0.52, 1.00))
    rois.append((r4, b4))
    # 5) Slightly smaller bottom-left
    r5, b5 = crop_rel(scene, box, (0.00, 0.68, 0.45, 1.00))
    rois.append((r5, b5))
    # 6) Centered strip directly below the icon (y2..y2+0.5h), centered x 0.25..0.75
    r6, b6 = crop_rel(scene, box, (0.25, 1.00, 0.75, 1.50))
    rois.append((r6, b6))
    # 7) Left-centered strip below (slightly more to the left)
    r7, b7 = crop_rel(scene, box, (0.10, 0.95, 0.60, 1.45))
    rois.append((r7, b7))
    return rois

def ocr_digits(img_bgr):
    # Robust OCR for white digits with multiple binarization fallbacks
    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
    gray = clahe.apply(gray)

    # Keep from 10% downwards to capture digits that sit high or low
    h = gray.shape[0]
    y0 = int(h * 0.10)
    sub = gray[y0:,:]

    kernels = [np.ones((2,2), np.uint8), np.ones((3,3), np.uint8)]
    bins = []
    # bright thresholds
    for t in (160, 170, 180, 190):
        bins.append(cv2.inRange(sub, t, 255))
    # adaptive
    bins.append(cv2.adaptiveThreshold(sub, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 31, -3))
    # otsu
    _, otsu = cv2.threshold(sub, 0, 255, cv2.THRESH_BINARY+cv2.THRESH_OTSU)
    bins.append(otsu)

    best_text = ""
    for b in bins:
        for k in kernels:
            thr = cv2.morphologyEx(b, cv2.MORPH_OPEN, k)
            thr = cv2.morphologyEx(thr, cv2.MORPH_CLOSE, k)
            contours, _ = cv2.findContours(thr, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            if contours:
                xs, ys, xe, ye = [], [], [], []
                for c in contours:
                    x, y, w, h2 = cv2.boundingRect(c)
                    if w*h2 < 8:
                        continue
                    xs.append(x); ys.append(y); xe.append(x+w); ye.append(y+h2)
                if xs:
                    x1 = max(0, min(xs)-2); y1 = max(0, min(ys)-2)
                    x2 = min(thr.shape[1], max(xe)+2); y2 = min(thr.shape[0], max(ye)+2)
                    digit_roi = thr[y1:y2, x1:x2]
                else:
                    digit_roi = thr
            else:
                digit_roi = thr

            # sanity check
            white_ratio = float(np.count_nonzero(digit_roi)) / max(1, digit_roi.size)
            if white_ratio < 0.001 or white_ratio > 0.60:
                continue

            up = cv2.resize(digit_roi, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
            text = ''.join(ocr_reader.readtext(up, detail=0, allowlist='0123456789'))
            text = ''.join([c for c in text if c.isdigit()])[:2]
            if len(text) >= len(best_text):
                best_text = text
            if len(best_text) >= 1:
                break
        if len(best_text) >= 1:
            break
    try:
        val = int(text) if text else None
        if val is None: 
            return None
        if val < 0 or val > 99:
            return None
        return val
    except ValueError:
        return None

# -------------- screen ROI helpers --------------
def get_shelf_roi(scene_bgr, rel=(0.08, 0.22, 0.92, 0.70)):
    """
    Return (roi_bgr, (offset_x, offset_y)).
    rel are normalized (x1,y1,x2,y2) for the wooden shelf area.
    """
    h, w = scene_bgr.shape[:2]
    x1 = int(w*rel[0]); y1 = int(h*rel[1])
    x2 = int(w*rel[2]); y2 = int(h*rel[3])
    roi = scene_bgr[y1:y2, x1:x2]
    return roi, (x1, y1)

# ----------------- main pipeline -----------------
def extract_ingredient_counts(image_path, templates_dir, score_threshold=0.60, nms_iou=0.35, debug=False, use_color_match=False, fast_mode=True):
    scene = cv2.imread(str(image_path))
    if scene is None:
        raise FileNotFoundError(image_path)

    # Focus matching on the shelf ROI
    shelf_bgr, (off_x, off_y) = get_shelf_roi(scene)

    # Optional downscale for speed, keep scale factor to map back
    ds_factor = 1.0
    if fast_mode:
        target_width = 900  # ~half-width of screenshot speeds up ~3-4x
        if shelf_bgr.shape[1] > target_width:
            ds_factor = target_width / shelf_bgr.shape[1]
            shelf_bgr = cv2.resize(shelf_bgr, (int(shelf_bgr.shape[1]*ds_factor), int(shelf_bgr.shape[0]*ds_factor)), interpolation=cv2.INTER_AREA)
    scene_gray = cv2.cvtColor(shelf_bgr, cv2.COLOR_BGR2GRAY)
    scene_edges = cv2.Canny(scene_gray, 50, 150)

    templates = load_templates(templates_dir)

    # 1) template match all ingredients at multiple scales
    raw_hits = []
    for name, tmpl in templates.items():
        tmpl_gray, tmpl_mask, tmpl_bgr = prepare_for_match(tmpl)
        # Tighter scale range in fast mode (icons are consistent in the cabinet)
        scales = np.linspace(0.85, 1.15, 7) if fast_mode else np.linspace(0.5, 1.3, 11)
        hits = multiscale_match(scene_gray, tmpl_gray, name, mask=tmpl_mask, th=score_threshold,
                                use_color=use_color_match, scene_bgr=shelf_bgr, tmpl_bgr=tmpl_bgr,
                                scene_edges=scene_edges, max_peaks_per_scale=4 if fast_mode else 8, scales=scales)
        # adjust coords back to full-scene space
        for (x1,y1,x2,y2,score, nm) in hits:
            # unscale from downscaled shelf ROI back to original coords
            if ds_factor != 1.0:
                x1 = int(x1 / ds_factor); x2 = int(x2 / ds_factor)
                y1 = int(y1 / ds_factor); y2 = int(y2 / ds_factor)
            raw_hits.append((x1+off_x, y1+off_y, x2+off_x, y2+off_y, score, nm))

    if not raw_hits:
        # Fallback: try entire scene if ROI failed
        scene_gray_full = cv2.cvtColor(scene, cv2.COLOR_BGR2GRAY)
        scene_edges_full = cv2.Canny(scene_gray_full, 50, 150)
        for name, tmpl in templates.items():
            tmpl_gray, tmpl_mask, tmpl_bgr = prepare_for_match(tmpl)
            scales = np.linspace(0.7, 1.2, 7) if fast_mode else np.linspace(0.5, 1.3, 11)
            hits = multiscale_match(scene_gray_full, tmpl_gray, name, mask=tmpl_mask, th=score_threshold,
                                    use_color=use_color_match, scene_bgr=scene, tmpl_bgr=tmpl_bgr,
                                    scene_edges=scene_edges_full, max_peaks_per_scale=3 if fast_mode else 6, scales=scales)
            raw_hits.extend(hits)
        if not raw_hits:
            return {}, scene

    # 2) for each ingredient, run NMS so we keep max one box per physical icon
    boxes, scores, names = [], [], []
    for (x1,y1,x2,y2,score,name) in raw_hits:
        boxes.append((x1,y1,x2,y2))
        scores.append(score)
        names.append(name)
    nms_boxes, nms_scores = non_max_suppression(boxes, scores, overlapThresh=nms_iou)

    # Map kept boxes back to names by nearest match (same coords)
    kept = []
    for kept_box, kept_score in zip(nms_boxes, nms_scores):
        matches = [(i, s, names[i]) for i,(b,s) in enumerate(zip(boxes, scores)) if b == kept_box]
        if matches:
            i_best = max(matches, key=lambda t: t[1])[0]
            kept.append((kept_box, names[i_best], kept_score))

    # Enforce one match per icon template: keep highest score per name
    best_per_name = {}
    for (box, name, sc) in kept:
        if name not in best_per_name or sc > best_per_name[name][1]:
            best_per_name[name] = (box, sc)
    kept = [(box, name, sc) for name, (box, sc) in best_per_name.items()]

    # 3) crop badge & OCR per kept detection
    result = {}
    overlay = scene.copy()
    # OCR crop: try several candidate regions and take first valid digit read
    for (x1,y1,x2,y2), name, sc in kept:
        count = None
        chosen_box = None
        for roi, ocr_box in generate_ocr_rois(scene, (x1,y1,x2,y2)):
            count = ocr_digits(roi)
            if count is not None:
                chosen_box = ocr_box
                break

        # Only keep confident counts; if OCR failed, skip or set 0
        if count is not None:
            result[name] = count

        if debug:
            cv2.rectangle(overlay, (x1,y1), (x2,y2), (0,255,0), 2)
            label = f"{name}: {count if count is not None else '?'}"
            cv2.putText(overlay, label, (x1, y1-6), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0,255,0), 1, cv2.LINE_AA)
            # Draw OCR box
            if chosen_box is not None:
                ox1, oy1, ox2, oy2 = chosen_box
                cv2.rectangle(overlay, (ox1,oy1), (ox2,oy2), (255,0,0), 2)

    return result, overlay

# Example usage:
# counts, dbg = extract_ingredient_counts("screenshot.jpg", "templates", debug=True)
# print(counts)
# cv2.imwrite("debug_output.png", dbg)

if __name__ == "__main__":
    # Quick local run against the provided example and templates in /imgs
    example_img = Path(__file__).parent / "examples" / "08F19DEC-4B2C-4A68-AA8F-9E4ED25B51D7.jpeg"
    tmpl_dir = Path(__file__).resolve().parents[1] / "screenshot_extraction/ingredient_images"
    # Toggle color-aware template matching here:
    USE_COLOR_MATCH = False  # default off for speed
    counts, overlay = extract_ingredient_counts(str(example_img), str(tmpl_dir), debug=True, use_color_match=USE_COLOR_MATCH, fast_mode=True)
    print(counts)
    out_file = Path(__file__).parent / "debug_output.png"
    cv2.imwrite(str(out_file), overlay)

    # Optional ground-truth check if file exists
    truth_path = Path(__file__).parent / "ground_truth_08F19DEC.json"
    if truth_path.exists():
        with open(truth_path, "r", encoding="utf-8") as f:
            truth = json.load(f)
        # compare only for keys present in truth
        mismatches = {}
        missing = []
        for k, v in truth.items():
            if k not in counts:
                missing.append(k)
            elif int(counts[k]) != int(v):
                mismatches[k] = {"expected": int(v), "got": int(counts[k])}
        extras = [k for k in counts.keys() if k not in truth]

        print("Ground-truth check:")
        if not mismatches and not missing:
            print("  OK: all expected items matched.")
        if missing:
            print("  Missing:", missing)
        if mismatches:
            print("  Mismatches:", mismatches)
        if extras:
            print("  Extras (detected but not in truth):", extras)
