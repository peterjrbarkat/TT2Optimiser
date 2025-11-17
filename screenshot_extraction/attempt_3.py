import cv2, numpy as np
from pathlib import Path

# --------------------- helpers ---------------------
def rgba_to_bgr_and_mask(rgba):
    bgr = rgba[:,:,:3].astype(np.float32)
    a = rgba[:,:,3:4].astype(np.float32) / 255.0
    bgr = (bgr * a + 255*(1-a)).astype(np.uint8)
    mask = (rgba[:,:,3] > 10).astype(np.uint8) * 255
    return bgr, mask

def kmeans_colors(bgr, mask, k=3):
    pts = bgr[mask>0].reshape(-1,3).astype(np.float32)
    if len(pts) < k: return []
    # bias toward saturated colors (drop near-grays)
    hsv = cv2.cvtColor(pts.reshape(-1,1,3).astype(np.uint8), cv2.COLOR_BGR2HSV)[:,0,:]
    sat = hsv[:,1]
    pts = pts[sat > 80]  # keep saturated pixels only
    if len(pts) < k: k = max(1, len(pts))
    if k == 0: return []
    criteria = (cv2.TERM_CRITERIA_EPS+cv2.TERM_CRITERIA_MAX_ITER, 30, 0.2)
    _, labels, centers = cv2.kmeans(pts, k, None, criteria, 5, cv2.KMEANS_PP_CENTERS)
    return [tuple(map(int, c)) for c in centers]

def bgr_to_lab(img):  # Lab is robust to brightness
    return cv2.cvtColor(img, cv2.COLOR_BGR2LAB)

def deltaE(lab_img, ref_lab):  # CIE76 (good enough & fast)
    diff = lab_img.astype(np.int16) - np.array(ref_lab, dtype=np.int16)
    return np.sqrt((diff**2).sum(axis=2)).astype(np.float32)

def union_color_mask(scene_bgr, swatches_bgr, dE=18):
    lab = bgr_to_lab(scene_bgr)
    m = np.zeros(scene_bgr.shape[:2], np.uint8)
    for bgr in swatches_bgr:
        lab_ref = cv2.cvtColor(np.uint8([[bgr]]), cv2.COLOR_BGR2LAB)[0,0]
        dist = deltaE(lab, lab_ref)
        m = cv2.bitwise_or(m, (dist < dE).astype(np.uint8)*255)
    return m

def find_blobs(mask, min_area=600, max_area=50000):
    cnts,_ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    boxes=[]
    for c in cnts:
        x,y,w,h = cv2.boundingRect(c)
        area = w*h
        if min_area <= area <= max_area:
            boxes.append((x,y,x+w,y+h))
    return boxes

def nms_boxes(boxes, iou=0.35):
    if not boxes: return []
    boxes = np.array(boxes, dtype=np.float32)
    x1,y1,x2,y2 = boxes[:,0],boxes[:,1],boxes[:,2],boxes[:,3]
    areas = (x2-x1)*(y2-y1)
    idxs = np.argsort(areas)[::-1]
    keep=[]
    while len(idxs):
        i = idxs[0]; keep.append(tuple(map(int, boxes[i])))
        xx1 = np.maximum(x1[i], x1[idxs[1:]])
        yy1 = np.maximum(y1[i], y1[idxs[1:]])
        xx2 = np.minimum(x2[i], x2[idxs[1:]])
        yy2 = np.minimum(y2[i], y2[idxs[1:]])
        w = np.maximum(0, xx2-xx1); h = np.maximum(0, yy2-yy1)
        inter = w*h
        iouv = inter / (areas[i] + areas[idxs[1:]] - inter + 1e-7)
        idxs = idxs[np.where(iouv <= iou)[0] + 1]
    return keep

def below_right_badge_roi(box, scene_shape, xrel=(0.55,0.95), yrel=(0.75,1.15), pad=6):
    x1,y1,x2,y2 = box
    w,h = x2-x1, y2-y1
    bx1 = x1 + int(w*xrel[0]) - pad
    bx2 = x1 + int(w*xrel[1]) + pad
    by1 = y1 + int(h*yrel[0]) - pad
    by2 = y1 + int(h*yrel[1]) + pad
    H,W = scene_shape[:2]
    bx1,by1 = max(0,bx1), max(0,by1)
    bx2,by2 = min(W,bx2), min(H,by2)
    return (bx1,by1,bx2,by2)

def find_black_oval(roi_bgr):
    hsv = cv2.cvtColor(roi_bgr, cv2.COLOR_BGR2HSV)
    dark = cv2.inRange(hsv, (0,0,0), (180,255,70))
    dark = cv2.morphologyEx(dark, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_ELLIPSE,(5,5)), iterations=2)
    cnts,_ = cv2.findContours(dark, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    best=None; best_score=-1
    for c in cnts:
        x,y,w,h = cv2.boundingRect(c)
        area = w*h
        if area < 200: continue
        # oval-ness score
        ellipse_like = min(w,h)/max(w,h)
        if ellipse_like > best_score:
            best_score = ellipse_like; best = (x,y,x+w,y+h)
    return best  # None if not found

# ---- digit reading via digit templates (no OCR engine) ----
def load_digit_templates(folder):
    tmpls={}
    for p in Path(folder).glob("*.png"):
        d = p.stem
        img = cv2.imread(str(p), cv2.IMREAD_GRAYSCALE)
        _, img = cv2.threshold(img, 200, 255, cv2.THRESH_BINARY)
        tmpls[d] = img
    return tmpls

def read_digits_template(roi_bgr, digit_tmpls):
    # binarize white digits on dark
    g = cv2.cvtColor(roi_bgr, cv2.COLOR_BGR2GRAY)
    g = cv2.GaussianBlur(g,(3,3),0)
    _, thr = cv2.threshold(g, 200, 255, cv2.THRESH_BINARY)
    # split into connected components (each digit)
    cnts,_ = cv2.findContours(thr, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    boxes=sorted([cv2.boundingRect(c) for c in cnts], key=lambda b: b[0])
    out=''
    for (x,y,w,h) in boxes:
        if w*h < 40: continue
        digit = thr[y:y+h, x:x+w]
        digit = cv2.copyMakeBorder(digit,2,2,2,2, cv2.BORDER_CONSTANT, value=0)
        best=None; best_val=-1
        for d,tmpl in digit_tmpls.items():
            t = cv2.resize(tmpl, (digit.shape[1], digit.shape[0]), interpolation=cv2.INTER_AREA)
            res = cv2.matchTemplate(digit, t, cv2.TM_CCOEFF_NORMED)
            if res.max() > best_val:
                best_val = float(res.max()); best = d
        if best is not None: out += best
    return int(out) if out.isdigit() else None

# --------------------- main ---------------------
def count_ingredients_by_color(scene_path, template_map, digit_templates_dir=None,
                               shelf_roi_rel=(0.30,0.53,0.85,0.92),
                               dE=18):
    scene = cv2.imread(scene_path)
    H,W = scene.shape[:2]
    # crop roughly to the shelf area (adjust these numbers per device once)
    x1 = int(W*shelf_roi_rel[0]); y1 = int(H*shelf_roi_rel[1])
    x2 = int(W*shelf_roi_rel[2]); y2 = int(H*shelf_roi_rel[3])
    shelf = scene[y1:y2, x1:x2].copy()

    # swatches per ingredient
    swatches = {}
    for name, path in template_map.items():
        rgba = cv2.imread(path, cv2.IMREAD_UNCHANGED)
        if rgba is None: continue
        bgr, mask = rgba_to_bgr_and_mask(rgba)
        centers = kmeans_colors(bgr, mask, k=3)
        if centers: swatches[name] = centers  # list of BGR tuples

    # locate each ingredient by swatch backprojection (ΔE threshold)
    results = {}
    for name, centers in swatches.items():
        m = union_color_mask(shelf, centers, dE=dE)
        m = cv2.morphologyEx(m, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_ELLIPSE,(5,5)), 1)
        m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_ELLIPSE,(7,7)), 1)
        boxes = find_blobs(m, min_area=400, max_area=60000)
        boxes = nms_boxes(boxes, iou=0.3)
        # pick at most 1 (there's one jar per ingredient)
        if boxes:
            bx = boxes[0]
            # find the badge just below-right of the jar
            badge_roi = below_right_badge_roi(bx, shelf.shape)
            bx1,by1,bx2,by2 = badge_roi
            badge = shelf[by1:by2, bx1:bx2]
            count = None
            if digit_templates_dir is not None:
                tmpls = load_digit_templates(digit_templates_dir)
                count = read_digits_template(badge, tmpls)  # no OCR engine needed
            results[name] = {
                "box_on_scene": (x1+bx[0], y1+bx[1], x1+bx[2], y1+bx[3]),
                "badge_roi_on_scene": (x1+bx1, y1+by1, x1+bx2, y1+by2),
                "count": count
            }
    return results

# ---------- Example ----------
template_map = {
    "tooth": "4jZrlLN - Imgur.png",
    "poison_drop": "AipJ3Yt - Imgur.png",
    "acorn": "AOswOIi - Imgur.png",
    "beetle": "bdFdyx0 - Imgur.png",
    "leaf": "CGUuB2u - Imgur.png",
    "horn": "dWg2BnN - Imgur.png",
    "hourglass": "FOQ1xFS - Imgur.png",
    "lightning": "FvsyopO - Imgur.png",
    "purple_drop": "gtiQgMt - Imgur.png",
}
# results = count_ingredients_by_color("08F19DEC-4B2C-4A68-AA8F-9E4ED25B51D7.jpeg", template_map, digit_templates_dir="digits/")
# print(results)
