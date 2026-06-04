"""Stretching / tone-mapping operations on float32 images."""

from typing import List, Tuple
import numpy as np


def auto_stf(img: np.ndarray, target_bkg: float = 0.25) -> np.ndarray:
    """PixInsight-style Screen Transfer Function auto-stretch."""
    flat = img.ravel()
    median = float(np.median(flat))
    mad = float(np.median(np.abs(flat - median)))
    sigma = mad * 1.4826  # consistent with normal distribution

    # Shadow and highlight clipping points
    c0 = max(0.0, median - 2.8 * sigma)
    c1 = min(1.0, median + 2.8 * sigma)

    # Midtone transfer: solve for m such that MTF(m, median) = target_bkg
    # MTF(m, x) = (m-1)*x / ((2m-1)*x - m)  — simplified to linear midtone
    c0c = max(0.0, c0)
    c1c = min(1.0, c1)
    span = c1c - c0c if c1c > c0c else 1.0

    out = np.clip((img - c0c) / span, 0.0, 1.0).astype(np.float32)

    # Apply midtone: gamma-like curve
    # find gamma such that 0.5^gamma = target_bkg when median_norm = 0.5
    median_norm = (median - c0c) / span
    if 0.0 < median_norm < 1.0:
        gamma = np.log(target_bkg) / np.log(median_norm + 1e-10)
        gamma = float(np.clip(gamma, 0.1, 10.0))
        out = np.power(np.clip(out, 0, 1), gamma).astype(np.float32)

    return out


def apply_levels(
    img: np.ndarray,
    black: float = 0.0,
    white: float = 1.0,
    gamma: float = 1.0,
) -> np.ndarray:
    """Linear remap [black, white] → [0, 1] then apply gamma."""
    span = white - black if white > black else 1e-6
    out = np.clip((img - black) / span, 0.0, 1.0).astype(np.float32)
    if gamma != 1.0:
        out = np.power(out, 1.0 / gamma).astype(np.float32)
    return out


def apply_curves(
    img: np.ndarray,
    control_points: List[Tuple[float, float]],
) -> np.ndarray:
    """Apply a tone curve defined by (input, output) control points via cubic spline."""
    if len(control_points) < 2:
        return img.copy()

    from scipy.interpolate import PchipInterpolator

    pts = sorted(control_points, key=lambda p: p[0])
    xs = np.array([p[0] for p in pts], dtype=np.float64)
    ys = np.array([p[1] for p in pts], dtype=np.float64)

    # Build LUT for performance
    lut_x = np.linspace(0.0, 1.0, 4096, dtype=np.float64)
    interp = PchipInterpolator(xs, ys, extrapolate=True)
    lut_y = np.clip(interp(lut_x), 0.0, 1.0).astype(np.float32)

    indices = np.clip((img * 4095).astype(np.int32), 0, 4095)
    return lut_y[indices]


def hist_eq(img: np.ndarray) -> np.ndarray:
    """Histogram equalisation via CDF (works per-channel for colour)."""
    def _eq_channel(ch: np.ndarray) -> np.ndarray:
        flat = ch.ravel()
        hist, bin_edges = np.histogram(flat, bins=4096, range=(0.0, 1.0))
        cdf = np.cumsum(hist).astype(np.float32)
        cdf = cdf / cdf[-1]
        # map pixel values through CDF
        bin_idx = np.clip((ch * 4095).astype(np.int32), 0, 4095)
        return cdf[bin_idx]

    if img.ndim == 2:
        return _eq_channel(img)
    channels = [_eq_channel(img[:, :, c]) for c in range(img.shape[2])]
    return np.stack(channels, axis=-1).astype(np.float32)
