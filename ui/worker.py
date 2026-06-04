"""Background worker for the stacking pipeline."""

from typing import List, Dict
import numpy as np

from PyQt6.QtCore import QThread, pyqtSignal

from core.loader import load_image
from core.calibration import build_master_bias, build_master_dark, build_master_flat, calibrate_light
from core.stacking import ALGORITHMS


class StackWorker(QThread):
    progress = pyqtSignal(int, str)     # percent, message
    finished = pyqtSignal(np.ndarray)   # result image
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
        darks = self._paths.get("Darks", [])
        bias = self._paths.get("Bias", [])
        flats = self._paths.get("Flats", [])

        if not lights:
            self.error.emit("No Light frames loaded.")
            return

        total_steps = len(bias) + len(darks) + len(flats) + len(lights) + 3
        step = 0

        def advance(msg: str):
            nonlocal step
            step += 1
            self.progress.emit(int(step / total_steps * 100), msg)

        # --- Calibration masters ---
        advance("Building Master Bias…")
        master_bias = None
        if bias:
            for i, p in enumerate(bias):
                advance(f"Loading bias {i+1}/{len(bias)}")
            master_bias = build_master_bias(bias)

        master_dark = None
        if darks:
            for i, p in enumerate(darks):
                advance(f"Loading dark {i+1}/{len(darks)}")
            master_dark = build_master_dark(darks, master_bias)

        master_flat = None
        if flats:
            for i, p in enumerate(flats):
                advance(f"Loading flat {i+1}/{len(flats)}")
            master_flat = build_master_flat(flats)

        # --- Load and calibrate lights ---
        calibrated = []
        for i, p in enumerate(lights):
            advance(f"Loading light {i+1}/{len(lights)}")
            frame = load_image(p)
            frame = calibrate_light(frame, master_dark, master_flat)
            calibrated.append(frame)

        # --- Stack ---
        advance(f"Stacking {len(calibrated)} frames with {self._algorithm}…")
        stack_fn = ALGORITHMS[self._algorithm]
        kwargs = {}
        if self._algorithm in ("Sigma Clipping", "Kappa-Sigma"):
            kwargs = {"sigma": self._sigma, "iterations": self._iterations}

        result = stack_fn(calibrated, **kwargs)
        self.progress.emit(100, "Done.")
        self.finished.emit(result)
