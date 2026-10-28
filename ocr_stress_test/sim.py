"""OCR + VLM cross-check stress test.

Renders certificate-style batch-result tables from real values, degrades them like
real scans, reads them with two independent OCR engines, and compares:

  * NAIVE design  - the "VLM" reads the page with the OCR words in its context and
                    points to an OCR word ID; a value is accepted when the VLM's text
                    equals that word's text.
  * FIXED design  - deskew + ruled-grid detection, two independent reads per cell
                    (Tesseract page OCR and PP-OCR via RapidOCR on the cell crop),
                    typed normalisation, column/row rules, zoom re-read, then human.

No real VLM is called. The VLM's own visual read is stood in for by PP-OCR on the
cell crop, and its tendency to copy the OCR text it was given is a swept parameter
(copy rate). Everything else is measured.
"""
import io, math, re, random
from decimal import Decimal, InvalidOperation

import cv2
import numpy as np
import pytesseract
from PIL import Image, ImageDraw, ImageFont
from rapidocr_onnxruntime import RapidOCR

FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
FONT_B = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
_rapid = None


def rapid():
    global _rapid
    if _rapid is None:
        _rapid = RapidOCR()
    return _rapid


# --------------------------------------------------------------------------- render
def render_table(batch_ids, cols, rows, title_lines):
    """cols: list of dicts {key, header (list of lines), width}.
    rows: list of lists of printed strings (one per value column).
    Returns PIL 'L' image and ground truth cells
    [{r, c, key, text, box:(x0,y0,x1,y1)}] in image pixels (300 dpi)."""
    f = ImageFont.truetype(FONT, 36)
    fb = ImageFont.truetype(FONT_B, 36)
    ft = ImageFont.truetype(FONT_B, 44)
    W = 2480
    x_left = 100
    widths = [300] + [c["width"] for c in cols]
    head_h, row_h = 112, 66
    y_top = 330
    n = len(rows)
    H = y_top + head_h + n * row_h + 260
    im = Image.new("L", (W, H), 255)
    d = ImageDraw.Draw(im)
    y = 90
    for i, t in enumerate(title_lines):
        d.text((x_left, y), t, font=ft if i == 0 else f, fill=0)
        y += 64 if i == 0 else 50
    xs = [x_left]
    for w in widths:
        xs.append(xs[-1] + w)
    ys = [y_top, y_top + head_h] + [y_top + head_h + (i + 1) * row_h for i in range(n)]
    lw = 3
    for x in xs:
        d.line([(x, ys[0]), (x, ys[-1])], fill=0, width=lw)
    for yy in ys:
        d.line([(xs[0], yy), (xs[-1], yy)], fill=0, width=lw)
    headers = [["Batch"]] + [c["header"] for c in cols]
    for ci, lines in enumerate(headers):
        cx = (xs[ci] + xs[ci + 1]) / 2
        total = len(lines) * 42
        yy = ys[0] + (head_h - total) / 2
        for ln in lines:
            tw = d.textlength(ln, font=fb)
            d.text((cx - tw / 2, yy), ln, font=fb, fill=0)
            yy += 42
    gt = []
    for ri in range(n):
        y0, y1 = ys[ri + 1], ys[ri + 2]
        cells = [batch_ids[ri]] + rows[ri]
        for ci, txt in enumerate(cells):
            cx = (xs[ci] + xs[ci + 1]) / 2
            tw = d.textlength(txt, font=f)
            d.text((cx - tw / 2, y0 + (row_h - 44) / 2), txt, font=f, fill=0)
            if ci > 0:
                gt.append({"r": ri, "c": ci - 1, "key": cols[ci - 1]["key"], "text": txt,
                           "box": (xs[ci], y0, xs[ci + 1], y1)})
    d.text((x_left, ys[-1] + 60), "Results reported to the decimal places of the specification.",
           font=f, fill=0)
    return im, gt, {"xs": xs, "ys": ys}


# -------------------------------------------------------------------------- degrade
LEVELS = {
    "L0 clean digital": dict(dpi=300, rot=0.0, blur=0.0, noise=0, jpeg=95, speck=0.0, binar=False),
    "L1 good scan": dict(dpi=200, rot=0.4, blur=0.5, noise=6, jpeg=75, speck=0.0, binar=False),
    "L2 poor scan": dict(dpi=150, rot=1.0, blur=0.9, noise=12, jpeg=50, speck=0.002, binar=False),
    "L3 fax / photocopy": dict(dpi=150, rot=1.5, blur=0.7, noise=10, jpeg=60, speck=0.003, binar=True),
}


def degrade(im, p, rng):
    a = np.array(im)
    h, w = a.shape
    ang = rng.uniform(-p["rot"], p["rot"]) if p["rot"] else 0.0
    M = cv2.getRotationMatrix2D((w / 2, h / 2), ang, 1.0)
    a = cv2.warpAffine(a, M, (w, h), flags=cv2.INTER_LINEAR, borderValue=255)
    k = p["dpi"] / 300.0
    if k != 1.0:
        a = cv2.resize(a, (int(w * k), int(h * k)), interpolation=cv2.INTER_AREA)
    if p["blur"]:
        a = cv2.GaussianBlur(a, (0, 0), p["blur"])
    if p["noise"]:
        a = np.clip(a.astype(np.float32) + rng.normal(0, p["noise"], a.shape), 0, 255).astype(np.uint8)
    if p["speck"]:
        m = rng.random(a.shape)
        a[m < p["speck"] / 2] = 0
        a[m > 1 - p["speck"] / 2] = 255
    if p["binar"]:
        _, a = cv2.threshold(a, 175, 255, cv2.THRESH_BINARY)
    ok, enc = cv2.imencode(".jpg", a, [cv2.IMWRITE_JPEG_QUALITY, p["jpeg"]])
    a = cv2.imdecode(enc, cv2.IMREAD_GRAYSCALE)
    Mk = M * k  # full transform original -> degraded
    return a, Mk, ang


def poly_of(box, M):
    x0, y0, x1, y1 = box
    pts = np.array([[x0, y0], [x1, y0], [x1, y1], [x0, y1]], np.float32)
    pts = np.hstack([pts, np.ones((4, 1), np.float32)]) @ M.T
    return pts.astype(np.float32)


# -------------------------------------------------------------------------- readers
def remove_lines(a):
    """Paint ruled table lines white so they are not read as characters."""
    inv = 255 - a
    _, bw = cv2.threshold(inv, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    bw = cv2.dilate(bw, np.ones((2, 2), np.uint8))
    H, W = a.shape
    hm = cv2.morphologyEx(bw, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_RECT, (max(25, W // 25), 1)))
    vm = cv2.morphologyEx(bw, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_RECT, (1, max(15, H // 30))))
    mask = cv2.dilate(cv2.bitwise_or(hm, vm), np.ones((3, 3), np.uint8))
    out = a.copy()
    out[mask > 0] = 255
    return out


def tess_words(a):
    a = remove_lines(a)
    d = pytesseract.image_to_data(a, config="--psm 6", output_type=pytesseract.Output.DICT)
    out = []
    for i, t in enumerate(d["text"]):
        t = t.strip()
        if not t:
            continue
        x, y, w, h = d["left"][i], d["top"][i], d["width"][i], d["height"][i]
        out.append({"id": i, "text": t, "cx": x + w / 2, "cy": y + h / 2, "box": (x, y, x + w, y + h),
                    "conf": float(d["conf"][i])})
    return out


def words_in_poly(words, poly):
    inside = [w for w in words if cv2.pointPolygonTest(poly, (w["cx"], w["cy"]), False) >= 0]
    inside.sort(key=lambda w: w["cx"])
    return inside


def crop_poly(a, poly, pad=0):
    """Warp the (possibly rotated) cell polygon to an upright rectangle, then inset."""
    w = int(round(np.linalg.norm(poly[1] - poly[0])))
    h = int(round(np.linalg.norm(poly[3] - poly[0])))
    A = cv2.getAffineTransform(poly[[0, 1, 3]].astype(np.float32),
                               np.array([[0, 0], [w, 0], [0, h]], np.float32))
    up = cv2.warpAffine(a, A, (w, h), flags=cv2.INTER_LINEAR, borderValue=255)
    return up[pad:h - pad, pad:w - pad]


def tighten(crop, margin=6):
    """Crop to the ink so recognisers do not hallucinate on empty margins."""
    if crop.size == 0:
        return crop
    ys, xs = np.where(crop < 160)
    if len(xs) < 3:
        return crop
    x0, x1 = max(0, xs.min() - margin), min(crop.shape[1], xs.max() + margin + 1)
    y0, y1 = max(0, ys.min() - margin), min(crop.shape[0], ys.max() + margin + 1)
    return crop[y0:y1, x0:x1]


def rapid_read(crop):
    if crop.size == 0 or min(crop.shape[:2]) < 4:
        return ""
    crop = tighten(crop)
    rgb = cv2.cvtColor(crop, cv2.COLOR_GRAY2RGB)
    res, _ = rapid()(rgb, use_det=False, use_cls=False, use_rec=True)
    return res[0][0].strip() if res else ""


def tess_cell(crop, numeric=False):
    if crop.size == 0 or min(crop.shape[:2]) < 4:
        return ""
    crop = cv2.copyMakeBorder(tighten(crop), 10, 10, 10, 10, cv2.BORDER_CONSTANT, value=255)
    cfg = "--psm 7"
    if numeric:
        cfg += " -c tessedit_char_whitelist=0123456789.<>%,"
    return pytesseract.image_to_string(crop, config=cfg).strip()


def zoom(crop, f=3):
    z = cv2.resize(crop, None, fx=f, fy=f, interpolation=cv2.INTER_CUBIC)
    blur = cv2.GaussianBlur(z, (0, 0), 1.0)
    z = cv2.addWeighted(z, 1.6, blur, -0.6, 0)
    z = cv2.copyMakeBorder(z, 12, 12, 12, 12, cv2.BORDER_CONSTANT, value=255)
    return z


# --------------------------------------------------------------------- normalise
def canon(s):
    """Typed value: (qualifier, Decimal, decimals) or None if not a clean number."""
    if s is None:
        return None
    t = s.strip().replace(" ", "").replace("%", "").replace(",", ".").rstrip(".:;")
    q = ""
    if t and t[0] in "<>":
        q, t = t[0], t[1:]
    if not re.fullmatch(r"\d+(\.\d+)?", t or "x"):
        return None
    dec = len(t.split(".")[1]) if "." in t else 0
    try:
        return (q, Decimal(t), dec)
    except InvalidOperation:
        return None


def same_value(a, b):
    ca, cb = canon(a), canon(b)
    return ca is not None and cb is not None and ca[0] == cb[0] and ca[1] == cb[1] and ca[2] == cb[2]


# --------------------------------------------------------------------- grid (fixed)
def deskew(a):
    inv = 255 - a
    _, bw = cv2.threshold(inv, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    k = max(15, a.shape[1] // 60)
    hmask = cv2.morphologyEx(bw, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_RECT, (k, 1)))
    lines = cv2.HoughLinesP(hmask, 1, np.pi / 1800, threshold=80, minLineLength=a.shape[1] // 4,
                            maxLineGap=k)
    if lines is None:
        return a, 0.0
    angs = []
    for x1, y1, x2, y2 in lines[:, 0]:
        if x2 != x1:
            ang = math.degrees(math.atan2(y2 - y1, x2 - x1))
            if abs(ang) < 5:
                angs.append(ang)
    if not angs:
        return a, 0.0
    ang = float(np.median(angs))
    h, w = a.shape
    M = cv2.getRotationMatrix2D((w / 2, h / 2), ang, 1.0)
    return cv2.warpAffine(a, M, (w, h), flags=cv2.INTER_CUBIC, borderValue=255), ang


def peaks(profile, min_frac, min_gap):
    thr = profile.max() * min_frac
    idx = np.where(profile >= thr)[0]
    groups, cur = [], []
    for i in idx:
        if cur and i - cur[-1] > min_gap:
            groups.append(cur)
            cur = []
        cur.append(i)
    if cur:
        groups.append(cur)
    return [int(np.mean(g)) for g in groups]


def detect_grid(a):
    inv = 255 - a
    _, bw = cv2.threshold(inv, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    bw = cv2.morphologyEx(bw, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8))
    W = a.shape[1]
    hk = cv2.getStructuringElement(cv2.MORPH_RECT, (max(30, W // 12), 1))
    vk = cv2.getStructuringElement(cv2.MORPH_RECT, (1, max(20, a.shape[0] // 40)))
    hm = cv2.morphologyEx(bw, cv2.MORPH_OPEN, hk)
    vm = cv2.morphologyEx(bw, cv2.MORPH_OPEN, vk)
    gap = max(4, int(W / 2480 * 25))
    ys = peaks(hm.sum(1).astype(float), 0.5, gap)
    xs = peaks(vm.sum(0).astype(float), 0.3, gap)
    return xs, ys


def parse_col(s, dec):
    """Column-aware typed parse used by the FIXED design.
    Fixes only unambiguous OCR punctuation noise; never adds or moves digits.
    Returns the canonical text, or None when no single token fits the column's
    reporting format (so a lost decimal point still causes a disagreement)."""
    if not s:
        return None
    t = s.replace(":", ".").replace(",", ".")
    cands = []
    for tok in t.split():
        q = "<" if tok.startswith("<") else ""
        tok = re.sub(r"^[^0-9]+", "", tok)
        tok = re.sub(r"[^0-9]+$", "", tok)
        tok = re.sub(r"\.{2,}", ".", tok)
        if re.fullmatch(r"\d+(\.\d+)?", tok or "x"):
            d = len(tok.split(".")[1]) if "." in tok else 0
            if d == dec:
                cands.append(q + tok)
    return cands[0] if len(set(cands)) == 1 else None
