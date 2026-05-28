"""
1970s comic book / cel-animation style image processor.

Pipeline per frame:
  1. Bilateral filter  — smooths flat areas while preserving hard edges
  2. Canny + dilate    — extracts bold black outlines
  3. K-means quant     — reduces to 8 flat colours (cel-fill look)
  4. Vintage grade     — shifts palette to warm 70s tones
  5. Halftone dots     — vectorised Ben-Day dot overlay in mid-tones
  6. Edge composite    — burns outlines as near-black on top
"""

import cv2
import numpy as np
from PIL import Image


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def process_image(img_rgb: np.ndarray) -> np.ndarray:
    """Apply 1970s comic style to an RGB numpy array. Returns RGB array."""
    smooth = _bilateral(img_rgb)
    edges = _detect_edges(smooth)
    quantized = _quantize(smooth, k=8)
    graded = _vintage_grade(quantized)
    halftoned = _apply_halftone(graded, spacing=5)
    return _burn_edges(halftoned, edges)


def process_video(input_path: str, output_path: str, progress_cb=None) -> None:
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

    writer = None
    idx = 0
    try:
        while True:
            ret, frame_bgr = cap.read()
            if not ret:
                break

            # Defer writer creation until we have real frame dimensions
            if writer is None:
                h_real, w_real = frame_bgr.shape[:2]
                writer = cv2.VideoWriter(output_path, fourcc, fps, (w_real, h_real))

            frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
            result_rgb = process_image(frame_rgb)
            result_bgr = cv2.cvtColor(result_rgb, cv2.COLOR_RGB2BGR)
            writer.write(result_bgr)
            idx += 1
            if progress_cb and total > 0:
                progress_cb(int(idx * 100 / total))
    finally:
        cap.release()
        if writer is not None:
            writer.release()


# ---------------------------------------------------------------------------
# Pipeline stages
# ---------------------------------------------------------------------------

def _bilateral(img: np.ndarray) -> np.ndarray:
    """Smooth while preserving edges — gives the flat cel-animation fill look."""
    bgr = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
    smooth_bgr = cv2.bilateralFilter(bgr, d=9, sigmaColor=75, sigmaSpace=75)
    return cv2.cvtColor(smooth_bgr, cv2.COLOR_BGR2RGB)


def _detect_edges(img: np.ndarray) -> np.ndarray:
    """Return a binary edge mask (uint8, 0 or 255)."""
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
    For each grid cell the brightness drives the dot radius;
    dots appear only in mid-tones (40–215) to mimic offset printing.
    """
    gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
    h, w = gray.shape

    yy, xx = np.mgrid[0:h, 0:w]

    # Cell-centre coordinates for every pixel
    cy = (yy // spacing) * spacing + spacing // 2
    cx = (xx // spacing) * spacing + spacing // 2
    cy = np.clip(cy, 0, h - 1)
    cx = np.clip(cx, 0, w - 1)

    brightness = gray[cy, cx].astype(np.float32)
    radius = (1.0 - brightness / 255.0) * spacing * 0.55
    dist = np.sqrt((yy - cy).astype(np.float32) ** 2 +
                   (xx - cx).astype(np.float32) ** 2)

    mid_tone = (brightness > 40) & (brightness < 215)
    dot_mask = (dist <= radius) & mid_tone

    result = img.copy()
    # Darken dot pixels to simulate dense ink
    result[dot_mask] = (result[dot_mask].astype(np.float32) * 0.35).astype(np.uint8)
    return result


def _burn_edges(img: np.ndarray, edges: np.ndarray) -> np.ndarray:
    """Overlay edge pixels as a very dark brown-black."""
    result = img.copy()
    result[edges > 0] = [15, 8, 5]
    return result


# ---------------------------------------------------------------------------
# CLI test helper
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys

    if len(sys.argv) < 3:
        print("Usage: python processor.py <input_image> <output_image>")
        sys.exit(1)

    src = sys.argv[1]
    dst = sys.argv[2]
    pil = Image.open(src).convert("RGB")
    arr = np.array(pil)
    out = process_image(arr)
    Image.fromarray(out).save(dst)
    print(f"Saved → {dst}")
