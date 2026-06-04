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
    progress = pyqtSignal(int, str, float, float)
    finished = pyqtSignal(np.ndarray)
    error = pyqtSignal(str)

    def __init__(
        self,
        paths: Dict[str, List[str]],
        algorithm: str,
        sigma: float,
        iterations: int,
    ):
        super().__init__()
        self._paths = paths
        self._algorithm = algorithm
        self._sigma = sigma
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

        total_steps = len(bias) + len(darks) + len(flats) + len(lights) + 3
        step = 0
        t_start = time.monotonic()

        def advance(msg: str):
            nonlocal step
            step += 1
            pct = int(step / total_steps * 100)
            elapsed = time.monotonic() - t_start
            if pct > 0:
                remaining = elapsed / pct * (100 - pct)
            else:
                remaining = 0.0
            self.progress.emit(pct, msg, elapsed, remaining)

        # --- Calibration masters ---
        advance("Przygotowywanie…")
        master_bias = None
        if bias:
            for i in range(len(bias)):
                advance(f"Wczytywanie Bias {i+1}/{len(bias)}…")
            master_bias = build_master_bias(bias)

        master_dark = None
        if darks:
            for i in range(len(darks)):
                advance(f"Wczytywanie Dark {i+1}/{len(darks)}…")
            master_dark = build_master_dark(darks, master_bias)

        master_flat = None
        if flats:
            for i in range(len(flats)):
                advance(f"Wczytywanie Flat {i+1}/{len(flats)}…")
            master_flat = build_master_flat(flats)

        # --- Load and calibrate lights ---
        calibrated = []
        for i, p in enumerate(lights):
            advance(f"Wczytywanie Light {i+1}/{len(lights)}…")
            frame = load_image(p)
            frame = calibrate_light(frame, master_dark, master_flat)
            calibrated.append(frame)

        # --- Stack ---
        advance(f"Stackowanie {len(calibrated)} klatek ({self._algorithm})…")
        stack_fn = ALGORITHMS[self._algorithm]
        kwargs = {}
        if self._algorithm == "Sigma Clipping":
            kwargs = {"sigma": self._sigma, "iterations": self._iterations}
        elif self._algorithm == "Kappa-Sigma":
            kwargs = {"kappa": self._sigma, "iterations": self._iterations}

        result = stack_fn(calibrated, **kwargs)

        elapsed = time.monotonic() - t_start
        self.progress.emit(100, f"Gotowe! Czas: {elapsed:.1f}s", elapsed, 0.0)
        self.finished.emit(result)
