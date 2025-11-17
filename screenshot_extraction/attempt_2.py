# pip install easyocr opencv-python numpy
import cv2
import numpy as np
import easyocr
import re
from pathlib import Path

# ---------- utils ----------
def xyxy_from_quad(quad):
    xs = [p[0] for p in quad]
    ys = [p[1] for p in quad]
    return int(min(xs)), int(min(ys)), int(max(xs)), int(max(ys))

def is_white_on_black(gray_roi, white_thresh=200, black_thresh=60,
                      max_white_ratio=0.45, min_black_ratio=0.55):
    """Keep ROIs that look like bright digits over a mostly dark token."""
    total = gray_roi.size
    white_ratio = (gray_roi >= white_thresh).sum() / total
    black_ratio = (gray_roi <= black_thresh).sum() / total
    return white_ratio <= max_white_ratio and black_ratio >= min_black_ratio

def cluster_rows(items, height_tolerance=1.2):
    """
    Group boxes into rows by y-center using a simple gap threshold
    based on median box height, then order each row left->right.
    """
    if not items:
        return []

    # sort by y center
    items = sorted(items, key=lambda it: (it["cy"], it["x1"]))
    heights = [it["h"] for it in items]
    h_med = np.median(heights) if heights else 20

    rows, current = [], []
    last_cy = None
    for it in items:
        if last_cy is None or abs(it["cy"] - last_cy) <= h_med * height_tolerance:
            current.append(it)
        else:
            rows.append(sorted(current, key=lambda r: r["x1"]))
            current = [it]
        last_cy = it["cy"]
    if current:
        rows.append(sorted(current, key=lambda r: r["x1"]))
    return rows

# ---------- core ----------
def extract_counts(image_path,
                   ymin_band=0.18, ymax_band=0.82,
                   return_boxes=False, debug_path=None,
                   scale_factor=2.0, min_confidence=0.45,
                   max_digits=2, max_value=99):
    """
    Extract ingredient counts (white on black) and order them
    left->right within each row, then top->bottom across rows.
    """
    orig = cv2.imread(str(image_path))
    if orig is None:
        raise FileNotFoundError(f"Cannot read image: {image_path}")

    # upscale to help OCR on small digits
    img = cv2.resize(orig, None, fx=scale_factor, fy=scale_factor, interpolation=cv2.INTER_CUBIC)

    # light contrast enhancement
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    gray = clahe.apply(gray)

    H, W = img.shape[:2]

    reader = easyocr.Reader(['en'], gpu=False)
    ocr = reader.readtext(
        img, detail=1, paragraph=False, allowlist='0123456789',
        text_threshold=0.5, low_text=0.3, link_threshold=0.4
    )

    items = []
    for quad, text, conf in ocr:
        # confidence filter
        if conf is not None and conf < min_confidence:
            continue

        text = re.sub(r"[^0-9]", "", text)
        if not text:
            continue

        # ignore very long digit strings (e.g., concatenated artifacts)
        if len(text) > max_digits:
            continue

        x1, y1, x2, y2 = xyxy_from_quad(quad)
        # basic size sanity
        if (x2 - x1) < 12 or (y2 - y1) < 12:
            continue

        cy = (y1 + y2) / 2
        if not (ymin_band * H <= cy <= ymax_band * H):
            # reject outside shelves band
            continue

        pad = 4
        xx1 = max(0, x1 - pad); yy1 = max(0, y1 - pad)
        xx2 = min(W, x2 + pad); yy2 = min(H, y2 + pad)
        roi = gray[yy1:yy2, xx1:xx2]
        if roi.size == 0:
            continue

        if not is_white_on_black(roi):
            continue

        try:
            val = int(text)
        except ValueError:
            continue
        if val > max_value:
            continue

        items.append({
            "value": val, "x1": x1, "y1": y1, "x2": x2, "y2": y2,
            "w": x2 - x1, "h": y2 - y1, "cy": cy
        })

    # group into rows and order left->right, then rows top->bottom
    rows = cluster_rows(items)
    ordered_values = [it["value"] for row in rows for it in row]

    # optional debug image
    if debug_path:
        dbg = img.copy()
        for idx, row in enumerate(rows):
            for it in row:
                cv2.rectangle(dbg, (it["x1"], it["y1"]), (it["x2"], it["y2"]), (0,255,0), 2)
                cv2.putText(dbg, str(it["value"]), (it["x1"], it["y1"]-5),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0,255,0), 2, cv2.LINE_AA)
        cv2.imwrite(debug_path, dbg)

    return (ordered_values, rows) if return_boxes else ordered_values

# ---------- main ----------
def main():
    image_path = r"screenshot_extraction\examples\08F19DEC-4B2C-4A68-AA8F-9E4ED25B51D7.jpeg"
    # shelves band covers the middle portion; tweak if needed
    values, rows = extract_counts(
        image_path,
        ymin_band=0.18,
        ymax_band=0.82,
        debug_path="debug_boxes.png",
        return_boxes=True,
        scale_factor=2.0,
        min_confidence=0.45,
        max_digits=2,
        max_value=99,
    )

    # print rows explicitly
    for i, row in enumerate(rows, 1):
        print(f"row {i}: {[it['value'] for it in row]}")
    # also print flattened order if needed
    print("all:", values)  # left->right within each row, then next row top->bottom

if __name__ == "__main__":
    main()
