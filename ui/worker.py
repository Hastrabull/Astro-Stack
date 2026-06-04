"""Background worker for the stacking pipeline."""

import time
from typing import List, Dict
import numpy as np

from PyQt6.QtCore import QThread, pyqtSignal

from core.loader import load_image
from core.calibration import build_master_bias, build_master_dark, build_master_flat, calibrate_light
from core.stacking import ALGORITHMS


class StackWorker(QThread):
    # percent (0-100), message, elapsed_seconds, estimated_remaining_seconds
    # percent == -1  →  tryb nieokreślony (pulsujący pasek)
    progress  = pyqtSignal(int, str, float, float)
    finished  = pyqtSignal(np.ndarray)
    error     = pyqtSignal(str)

    def __init__(
        self,
        paths: Dict[str, List[str]],
        algorithm: str,
        sigma: float,
        iterations: int,
    ):
        super().__init__()
        self._paths      = paths
        self._algorithm  = algorithm
        self._sigma      = sigma
        self._iterations = iterations

    def run(self):
        try:
            self._run()
        except Exception as exc:
            self.error.emit(str(exc))

    def _run(self):
        lights = self._paths.get("Lights", [])
        darks  = self._paths.get("Darks",  [])
        bias   = self._paths.get("Bias",   [])
        flats  = self._paths.get("Flats",  [])

        if not lights:
            self.error.emit("No Light frames loaded.")
            return

        # Total deterministic steps = loading steps
        load_steps  = len(bias) + len(darks) + len(flats) + len(lights) + 1
        # Last 30% reserved for stacking iterations (or single pass for mean/median)
        LOAD_PCT_MAX = 70
        t_start = time.monotonic()
        step = 0

        def advance_load(msg: str):
            nonlocal step
            step += 1
            pct     = int(step / load_steps * LOAD_PCT_MAX)
            elapsed = time.monotonic() - t_start
            # Estimate remaining only from loading portion
            remaining = (elapsed / max(pct, 1)) * (100 - pct) if pct > 0 else 0.0
            self.progress.emit(pct, msg, elapsed, remaining)

        def advance_stack(current: int, total: int):
            """Called per stacking iteration."""
            pct     = LOAD_PCT_MAX + int(current / total * (100 - LOAD_PCT_MAX))
            elapsed = time.monotonic() - t_start
            iter_elapsed = elapsed - self._stack_start
            iter_remaining = (iter_elapsed / current) * (total - current) if current > 0 else 0.0
            self.progress.emit(
                pct,
                f"Stackowanie — iteracja {current}/{total}…",
                elapsed,
                iter_remaining,
            )

        # --- Calibration masters ---
        advance_load("Przygotowywanie…")

        master_bias = None
        if bias:
            for i in range(len(bias)):
                advance_load(f"Wczytywanie Bias {i+1}/{len(bias)}…")
            master_bias = build_master_bias(bias)

        master_dark = None
        if darks:
            for i in range(len(darks)):
                advance_load(f"Wczytywanie Dark {i+1}/{len(darks)}…")
            master_dark = build_master_dark(darks, master_bias)

        master_flat = None
        if flats:
            for i in range(len(flats)):
                advance_load(f"Wczytywanie Flat {i+1}/{len(flats)}…")
            master_flat = build_master_flat(flats)

        # --- Load and calibrate lights ---
        calibrated = []
        for i, p in enumerate(lights):
            advance_load(f"Wczytywanie Light {i+1}/{len(lights)}…")
            frame = load_image(p)
            frame = calibrate_light(frame, master_dark, master_flat)
            calibrated.append(frame)

        # --- Stack ---
        is_iterative = self._algorithm in ("Sigma Clipping", "Kappa-Sigma")
        iters        = self._iterations if is_iterative else 1

        elapsed = time.monotonic() - t_start
        self.progress.emit(
            LOAD_PCT_MAX,
            f"Stackowanie {len(calibrated)} klatek ({self._algorithm})"
            + (f" — {iters} iteracji…" if is_iterative else "…"),
            elapsed,
            0.0,
        )

        self._stack_start = time.monotonic()
        stack_fn = ALGORITHMS[self._algorithm]

        kwargs: dict = {"progress_cb": advance_stack}
        if self._algorithm == "Sigma Clipping":
            kwargs.update(sigma=self._sigma, iterations=self._iterations)
        elif self._algorithm == "Kappa-Sigma":
            kwargs.update(kappa=self._sigma, iterations=self._iterations)

        result = stack_fn(calibrated, **kwargs)

        elapsed = time.monotonic() - t_start
        self.progress.emit(100, f"Gotowe! Czas całkowity: {elapsed:.1f}s", elapsed, 0.0)
        self.finished.emit(result)
