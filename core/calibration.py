"""Calibration frame pipeline: Bias, Dark, Flat."""

from typing import List
import numpy as np

from .loader import load_image
from .stacking import stack_median


def build_master(paths: List[str]) -> np.ndarray | None:
    if not paths:
        return None
    frames = [load_image(p) for p in paths]
    return stack_median(frames)


def build_master_bias(bias_paths: List[str]) -> np.ndarray | None:
    return build_master(bias_paths)


def build_master_dark(
    dark_paths: List[str], master_bias: np.ndarray | None = None
) -> np.ndarray | None:
    master = build_master(dark_paths)
    if master is None:
        return None
    if master_bias is not None:
        master = np.clip(master - master_bias, 0, None)
    return master


def build_master_flat(flat_paths: List[str]) -> np.ndarray | None:
    master = build_master(flat_paths)
    if master is None:
        return None
    med = np.median(master)
    if med > 0:
        master = master / med
    return master


def calibrate_light(
    light: np.ndarray,
    master_dark: np.ndarray | None,
    master_flat: np.ndarray | None,
) -> np.ndarray:
    result = light.copy()
    if master_dark is not None:
        result = np.clip(result - master_dark, 0, None)
    if master_flat is not None:
        flat = master_flat.copy()
        flat[flat == 0] = 1.0  # avoid division by zero
        result = result / flat
    return np.clip(result, 0, 1).astype(np.float32)
