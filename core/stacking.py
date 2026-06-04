"""Stacking algorithms operating on lists of float32 arrays."""

from typing import List, Callable
import numpy as np


def stack_mean(frames: List[np.ndarray], progress_cb: Callable[[int, int], None] | None = None) -> np.ndarray:
    if progress_cb:
        progress_cb(1, 1)
    return np.mean(np.stack(frames, axis=0), axis=0).astype(np.float32)


def stack_median(frames: List[np.ndarray], progress_cb: Callable[[int, int], None] | None = None) -> np.ndarray:
    if progress_cb:
        progress_cb(1, 1)
    return np.median(np.stack(frames, axis=0), axis=0).astype(np.float32)


def stack_sigma(
    frames: List[np.ndarray],
    sigma: float = 3.0,
    iterations: int = 5,
    progress_cb: Callable[[int, int], None] | None = None,
) -> np.ndarray:
    """Iterative sigma clipping — each iteration calls progress_cb(current, total)."""
    cube = np.stack(frames, axis=0).astype(np.float32)
    mask = np.zeros_like(cube, dtype=bool)

    for i in range(iterations):
        if progress_cb:
            progress_cb(i + 1, iterations)
        valid = np.where(~mask, cube, np.nan)
        mean = np.nanmean(valid, axis=0, keepdims=True)
        std  = np.nanstd(valid,  axis=0, keepdims=True)
        mask = np.abs(cube - mean) > sigma * std

    cube[mask] = np.nan
    result = np.nanmean(cube, axis=0).astype(np.float32)
    nan_mask = np.isnan(result)
    if nan_mask.any():
        fallback = np.nanmean(cube, axis=0)
        result[nan_mask] = fallback[nan_mask] if not np.isnan(fallback[nan_mask]).all() else 0.0
    return result


def stack_kappa(
    frames: List[np.ndarray],
    kappa: float = 2.5,
    iterations: int = 5,
    progress_cb: Callable[[int, int], None] | None = None,
) -> np.ndarray:
    return stack_sigma(frames, sigma=kappa, iterations=iterations, progress_cb=progress_cb)


ALGORITHMS = {
    "Mean":           stack_mean,
    "Median":         stack_median,
    "Sigma Clipping": stack_sigma,
    "Kappa-Sigma":    stack_kappa,
}
