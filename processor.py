"""
1970s comic book / cel-animation style image processor.

Artistic principles drawn from:
  de Reyna  (1970) How to Draw What You See        → value mass separation
  Edwards   (1979) Drawing on the Right Side of the Brain → pure contour line weight
  Probyn    (1970) The Complete Drawing Book        → cross-hatch tonal mark-making

Pipeline per frame:
  1. Bilateral filter   — smooth flat areas, preserve edges      (de Reyna: see forms)
  2. Value mass clarity — S-curve pushes lights/shadows apart    (de Reyna: squinting)
  3. K-means quant      — reduce to N flat cel colours
  4. Vintage grade      — shift to warm 1970s print palette
  5. Cross-hatch        — directional ink in shadow zones        (Probyn)
  6. Halftone dots      — vectorised Ben-Day mid-tone overlay
  7. Variable contour   — gradient-weighted edge lines           (Edwards)
"""

import cv2
import numpy as np
from PIL import Image


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def process_image(
    img_rgb: np.ndarray,
    *,
    cross_hatch: bool = True,
    variable_contour: bool = True,
    n_colors: int = 8,
) -> np.ndarray:
    """
    Apply 1970s comic style to an RGB numpy array. Returns RGB array.

    Keyword-only options:
      cross_hatch      — Probyn: directional hatching in shadow zones
      variable_contour — Edwards: gradient-weighted contour line weight
      n_colors         — palette size, 4–12 (de Reyna palette control)
    """
    # Stage 1 — smooth while preserving hard edges (de Reyna: see the form)
    smooth = _bilateral(img_rgb)

    # Stage 2 — clarify value masses before quantisation (de Reyna: squinting)
    massed = _clarity_value_zones(smooth, strength=0.65)

    # Stage 3 — reduce to flat cel colours
    quantized = _quantize(massed, k=n_colors)

    # Stage 4 — shift palette to warm 1970s print tones
    graded = _vintage_grade(quantized)

    # Stage 5 — cross-hatch shadow zones (Probyn: mark accumulation)
    if cross_hatch:
        graded = _cross_hatch_shadows(graded, spacing=8)

    # Stage 6 — Ben-Day halftone dots in mid-tones
    halftoned = _apply_halftone(graded, spacing=5)

    # Stage 7 — contour lines
    if variable_contour:
        # Edwards: pure contour — detect on clean smooth source,
        # burn as variable-weight lines into the fully processed result
        return _apply_variable_contour(halftoned, edge_source=smooth)

    # Fallback: standard uniform Canny edges
    edges = _detect_edges(smooth)
    return _burn_edges(halftoned, edges)


def process_video(
    input_path: str,
    output_path: str,
    progress_cb=None,
    *,
    cross_hatch: bool = True,
    variable_contour: bool = True,
    n_colors: int = 8,
) -> None:
    """
    Process every frame of a video with the 1970s comic style.
    Writes an MP4 to output_path. Calls progress_cb(int_percent) periodically.
    """
    cap = cv2.VideoCapture(input_path)
    if not cap.isOpened():
        raise RuntimeError(f"Cannot open video: {input_path}")

    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    fps = cap.get(cv2.CAP_PROP_FPS) or 24.0
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")

    opts = dict(cross_hatch=cross_hatch, variable_contour=variable_contour, n_colors=n_colors)
    writer = None
    idx = 0
    try:
        while True:
            ret, frame_bgr = cap.read()
            if not ret:
                break

            if writer is None:
                h_r, w_r = frame_bgr.shape[:2]
                writer = cv2.VideoWriter(output_path, fourcc, fps, (w_r, h_r))

            frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
            result_rgb = process_image(frame_rgb, **opts)
            writer.write(cv2.cvtColor(result_rgb, cv2.COLOR_RGB2BGR))
            idx += 1
            if progress_cb and total > 0:
                progress_cb(int(idx * 100 / total))
    finally:
        cap.release()
        if writer is not None:
            writer.release()


# ---------------------------------------------------------------------------
# Book-inspired pipeline stages
# ---------------------------------------------------------------------------

def _clarity_value_zones(img: np.ndarray, strength: float = 0.65) -> np.ndarray:
    """
    de Reyna (1970) — squinting technique: see in value masses, not in details.

    Applies a smooth S-curve to luminance that pushes tonal values away
    from the mid-grey midpoint — highlights become lighter, shadows darker —
    creating the clearer light/shadow mass separation de Reyna describes
    when instructing students to 'squint at the subject'.

    Uses the polynomial S-curve:  v' = v + k·4·v·(1−v)·(v−0.5)
    which is anchored at {0, 0.5, 1} and smooth everywhere.
    """
    hsv = cv2.cvtColor(img, cv2.COLOR_RGB2HSV).astype(np.float32)
    v = hsv[:, :, 2] / 255.0

    # S-curve: pushes values away from 0.5
    # At v=0 and v=1 the curve is anchored; at v=0.25 it darkens,
    # at v=0.75 it lightens.
    v_s = v + strength * 4.0 * v * (1.0 - v) * (v - 0.5)
    v_s = np.clip(v_s, 0.0, 1.0)

    hsv[:, :, 2] = v_s * 255.0
    return cv2.cvtColor(hsv.astype(np.uint8), cv2.COLOR_HSV2RGB)


def _cross_hatch_shadows(img: np.ndarray, spacing: int = 8) -> np.ndarray:
    """
    Probyn (1970) — tonal mark-making through directional hatching.

    In The Complete Drawing Book Probyn demonstrates building shadow tone
    through accumulating parallel ink strokes: single-direction lines for
    mid-shadows, cross-hatch (two perpendicular sets) for deep shadows.
    The darkest core shadows need no hatching — they read as solid ink.

    Hatch angles: 45° (NE–SW) and 135° (NW–SE), spaced `spacing` pixels apart.
    """
    gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
    h, w = gray.shape
    yy, xx = np.mgrid[0:h, 0:w]

    # Diagonal stripe patterns (1-pixel-wide lines every `spacing` pixels)
    hatch_45  = ((xx + yy) % spacing) < 1   # NE–SW
    hatch_135 = ((xx - yy) % spacing) < 1   # NW–SE

    mid_shadow  = (gray > 45)  & (gray < 115)  # single-direction hatch
    deep_shadow = (gray >= 10) & (gray <= 45)  # cross-hatch
    # core shadow (< 10) stays solid — hatching adds nothing to near-black

    result = img.copy().astype(np.float32)

    # Mid-shadow: single 45° lines darkened to 25 % of original colour
    mid_mask = hatch_45 & mid_shadow
    result[mid_mask] *= 0.25

    result = np.clip(result, 0, 255).astype(np.uint8)

    # Deep shadow: cross-hatch lines set to near-ink dark
    deep_mask = (hatch_45 | hatch_135) & deep_shadow
    result[deep_mask] = [18, 9, 4]

    return result


def _apply_variable_contour(img: np.ndarray, edge_source: np.ndarray) -> np.ndarray:
    """
    Edwards (1979) — pure contour drawing with variable line weight.

    Drawing on the Right Side of the Brain describes pure contour as
    following every edge exactly as seen — with pressure variation:
    heavier lines at form overlaps and strong boundaries, lighter
    hairlines at subtle surface transitions and interior details.

    Implementation: Sobel gradient magnitude on the clean bilateral-smoothed
    source image drives line weight.
      magnitude > 80  → bold contour (3px dilation), near-black ink
      magnitude > 32  → hairline (1px), colour darkened to 42 %
    """
    gray = cv2.cvtColor(edge_source, cv2.COLOR_RGB2GRAY)

    gx = cv2.Sobel(gray, cv2.CV_32F, 1, 0, ksize=3)
    gy = cv2.Sobel(gray, cv2.CV_32F, 0, 1, ksize=3)
    mag = np.sqrt(gx ** 2 + gy ** 2)
    mag_u8 = cv2.normalize(mag, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)

    # Bold contours — major form boundaries (dilated to 3 px thickness)
    strong = (mag_u8 > 80).astype(np.uint8) * 255
    strong_wide = cv2.dilate(strong, np.ones((3, 3), np.uint8), iterations=1).astype(bool)

    # Hairline contours — subtle transitions, interior form description
    subtle = (mag_u8 > 32) & ~strong_wide

    result = img.copy()
    result[strong_wide] = [13, 7, 4]                                          # warm near-black
    result[subtle] = (result[subtle].astype(np.float32) * 0.42).astype(np.uint8)

    return result


# ---------------------------------------------------------------------------
# Core pipeline helpers (unchanged)
# ---------------------------------------------------------------------------

def _bilateral(img: np.ndarray) -> np.ndarray:
    """Smooth while preserving edges — flat cel-animation fill look."""
    bgr = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
    smooth_bgr = cv2.bilateralFilter(bgr, d=9, sigmaColor=75, sigmaSpace=75)
    return cv2.cvtColor(smooth_bgr, cv2.COLOR_BGR2RGB)


def _detect_edges(img: np.ndarray) -> np.ndarray:
    """Standard Canny edge mask (uint8, 0 or 255). Used in fallback path."""
    gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
    edges = cv2.Canny(gray, threshold1=30, threshold2=100)
    return cv2.dilate(edges, np.ones((2, 2), np.uint8), iterations=1)


def _quantize(img: np.ndarray, k: int = 8) -> np.ndarray:
    """K-means colour quantisation — reduces palette to k flat colours."""
    h, w = img.shape[:2]
    data = img.reshape(-1, 3).astype(np.float32)
    criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 20, 1.0)
    _, labels, centers = cv2.kmeans(
        data, k, None, criteria, 10, cv2.KMEANS_PP_CENTERS
    )
    centers = np.clip(centers, 0, 255).astype(np.uint8)
    return centers[labels.flatten()].reshape(h, w, 3)


def _vintage_grade(img: np.ndarray) -> np.ndarray:
    """Shift palette toward warm 1970s print tones (boost R/Y, cut B)."""
    f = img.astype(np.float32)
    f[:, :, 0] = f[:, :, 0] * 1.08 + 12   # warm reds / oranges
    f[:, :, 1] = f[:, :, 1] * 0.97 + 4    # slight green warmth
    f[:, :, 2] = f[:, :, 2] * 0.82 - 8    # pull cool blues back
    return np.clip(f, 0, 255).astype(np.uint8)


def _apply_halftone(img: np.ndarray, spacing: int = 5) -> np.ndarray:
    """
    Vectorised Ben-Day dot overlay.
    Brightness drives dot radius; dots appear only in mid-tones (40–215).
    """
    gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
    h, w = gray.shape

    yy, xx = np.mgrid[0:h, 0:w]
    cy = (yy // spacing) * spacing + spacing // 2
    cx = (xx // spacing) * spacing + spacing // 2
    cy = np.clip(cy, 0, h - 1)
    cx = np.clip(cx, 0, w - 1)

    brightness = gray[cy, cx].astype(np.float32)
    radius = (1.0 - brightness / 255.0) * spacing * 0.55
    dist = np.sqrt(
        (yy - cy).astype(np.float32) ** 2 +
        (xx - cx).astype(np.float32) ** 2
    )

    dot_mask = (dist <= radius) & (brightness > 40) & (brightness < 215)

    result = img.copy()
    result[dot_mask] = (result[dot_mask].astype(np.float32) * 0.35).astype(np.uint8)
    return result


def _burn_edges(img: np.ndarray, edges: np.ndarray) -> np.ndarray:
    """Overlay binary edge mask as very dark brown-black (fallback path)."""
    result = img.copy()
    result[edges > 0] = [15, 8, 5]
    return result


# ---------------------------------------------------------------------------
# CLI test helper
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys

    if len(sys.argv) < 3:
        print("Usage: python processor.py <input_image> <output_image> [--no-hatch] [--no-contour] [--colors N]")
        sys.exit(1)

    args = sys.argv[1:]
    src = args[0]
    dst = args[1]
    opts = {
        "cross_hatch":      "--no-hatch"    not in args,
        "variable_contour": "--no-contour"  not in args,
        "n_colors": int(args[args.index("--colors") + 1]) if "--colors" in args else 8,
    }

    pil = Image.open(src).convert("RGB")
    out = process_image(np.array(pil), **opts)
    Image.fromarray(out).save(dst)
    print(f"Saved → {dst}  (opts: {opts})")
