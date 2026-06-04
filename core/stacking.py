"""Stacking algorithms operating on lists of float32 arrays."""

from typing import List, Callable
import numpy as np


def stack_mean(frames: List[np.ndarray]) -> np.ndarray:
    return np.mean(np.stack(frames, axis=0), axis=0).astype(np.float32)


def stack_median(frames: List[np.ndarray]) -> np.ndarray:
    return np.median(np.stack(frames, axis=0), axis=0).astype(np.float32)


def stack_sigma(
    frames: List[np.ndarray],
    sigma: float = 3.0,
    iterations: int = 5,
    progress_cb: Callable[[int], None] | None = None,
) -> np.ndarray:
    """Iterative sigma clipping — pixels beyond sigma*std from mean are masked."""
    cube = np.stack(frames, axis=0).astype(np.float32)  # (N, H, W[, C])
    mask = np.zeros_like(cube, dtype=bool)

    for i in range(iterations):
        valid = np.where(~mask, cube, np.nan)
        mean = np.nanmean(valid, axis=0, keepdims=True)
        std = np.nanstd(valid, axis=0, keepdims=True)
        mask = np.abs(cube - mean) > sigma * std
        if progress_cb:
            progress_cb(i + 1)

    cube[mask] = np.nan
    result = np.nanmean(cube, axis=0).astype(np.float32)
    # Fill any fully-masked pixels with simple mean
    nan_mask = np.isnan(result)
    if nan_mask.any():
        result[nan_mask] = np.nanmean(cube, axis=0)[nan_mask]
    return result


def stack_kappa(
    frames: List[np.ndarray],
    kappa: float = 2.5,
    iterations: int = 5,
    progress_cb: Callable[[int], None] | None = None,
) -> np.ndarray:
    """Kappa-sigma clipping — same as sigma clipping with explicit kappa parameter."""
    return stack_sigma(frames, sigma=kappa, iterations=iterations, progress_cb=progress_cb)


ALGORITHMS = {
    "Mean": stack_mean,
    "Median": stack_median,
    "Sigma Clipping": stack_sigma,
    "Kappa-Sigma": stack_kappa,
}
