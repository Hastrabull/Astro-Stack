"""Star detection using photutils — returns star count and median FWHM."""

from typing import TypedDict
import numpy as np


MAX_SIDE = 2000   # downsample if image larger than this (performance)
FWHM_KERNEL = 3.0 # initial kernel FWHM for DAOStarFinder
THRESHOLD_SIGMA = 5.0


class StarDetectResult(TypedDict):
    n_stars: int
    median_fwhm: float   # pixels (on downsampled image → scaled back)
    std_fwhm: float
    snr: float


def detect_stars(img: np.ndarray) -> StarDetectResult:
    """Detect stars and compute FWHM on a float32 image.

    Downsamples to MAX_SIDE on the longer axis for speed.
    Returns n_stars, median_fwhm (in original-image pixels), std_fwhm, snr.
    """
    from astropy.stats import sigma_clipped_stats
    from photutils.detection import IRAFStarFinder

    # Convert colour → luminance
    gray = img.mean(axis=2).astype(np.float32) if img.ndim == 3 else img.astype(np.float32)

    # Downsample if needed
    h, w = gray.shape
    scale = 1.0
    if max(h, w) > MAX_SIDE:
        scale = MAX_SIDE / max(h, w)
        new_h, new_w = int(h * scale), int(w * scale)
        from PIL import Image as PILImage
        pil = PILImage.fromarray((gray * 65535).astype(np.uint16))
        gray = np.array(pil.resize((new_w, new_h), PILImage.LANCZOS)) / 65535.0

    # Background statistics
    _, median, std = sigma_clipped_stats(gray, sigma=3.0)
    if std == 0:
        return StarDetectResult(n_stars=0, median_fwhm=0.0, std_fwhm=0.0,
                                snr=float(np.mean(gray)))

    # Detect
    finder = IRAFStarFinder(
        threshold=THRESHOLD_SIGMA * std,
        fwhm=FWHM_KERNEL,
        roundness_range=(-0.5, 0.5),
        sharpness_range=(0.2, 1.0),
        peak_max=0.99,   # reject saturated
    )
    sources = finder(gray - median)

    if sources is None or len(sources) == 0:
        snr = float(np.mean(gray)) / (float(np.std(gray)) + 1e-9)
        return StarDetectResult(n_stars=0, median_fwhm=0.0, std_fwhm=0.0, snr=round(snr, 2))

    fwhms = np.array(sources["fwhm"], dtype=np.float32)
    # Remove outliers (e.g. cosmic rays detected as stars)
    fwhms = fwhms[(fwhms > 0.5) & (fwhms < 20.0)]

    # Scale FWHM back to original image pixels
    median_fwhm = float(np.median(fwhms) / scale) if len(fwhms) else 0.0
    std_fwhm    = float(np.std(fwhms)    / scale) if len(fwhms) else 0.0
    snr         = float(np.mean(gray)) / (float(std) + 1e-9)

    return StarDetectResult(
        n_stars=len(sources),
        median_fwhm=round(median_fwhm, 2),
        std_fwhm=round(std_fwhm, 2),
        snr=round(snr, 2),
    )
