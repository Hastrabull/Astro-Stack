"""Background worker for the stacking pipeline."""

import time
from typing import List, Dict
from concurrent.futures import ThreadPoolExecutor, as_completed
import numpy as np

from PyQt6.QtCore import QThread, pyqtSignal

from core.loader import load_image
from core.calibration import build_master_bias, build_master_dark, build_master_flat, calibrate_light
from core.stacking import ALGORITHMS


class StackWorker(QThread):
    # percent (0-100), message, elapsed_seconds, estimated_remaining_seconds
    progress = pyqtSignal(int, str, float, float)
    finished = pyqtSignal(np.ndarray)
    error    = pyqtSignal(str)

    def __init__(
        self,
        paths: Dict[str, List[str]],
        algorithm: str,
        sigma: float,
        iterations: int,
        normalization: str = "none",   # "none" | "median" | "first"
        n_threads: int = 4,
    ):
        super().__init__()
        self._paths         = paths
        self._algorithm     = algorithm
        self._sigma         = sigma
        self._iterations    = iterations
        self._normalization = normalization
        self._n_threads     = n_threads

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
            self.error.emit("Brak klatek Light do stackowania.")
            return

        LOAD_PCT_MAX = 70
        load_steps   = len(bias) + len(darks) + len(flats) + len(lights) + 1
        step         = 0
        t_start      = time.monotonic()

        def advance(msg: str):
            nonlocal step
            step += 1
            pct       = int(step / load_steps * LOAD_PCT_MAX)
            elapsed   = time.monotonic() - t_start
            remaining = (elapsed / max(pct, 1)) * (100 - pct)
            self.progress.emit(pct, msg, elapsed, remaining)

        def advance_stack(current: int, total: int):
            pct       = LOAD_PCT_MAX + int(current / total * (100 - LOAD_PCT_MAX))
            elapsed   = time.monotonic() - t_start
            iter_el   = elapsed - self._stack_start
            remaining = (iter_el / current) * (total - current) if current > 0 else 0.0
            self.progress.emit(
                pct,
                f"Stackowanie — iteracja {current}/{total}…",
                elapsed,
                remaining,
            )

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

        # --- Load and calibrate lights (parallel) ---
        calibrated: List[np.ndarray | None] = [None] * len(lights)

        def load_one(args):
            idx, path = args
            frame = load_image(path)
            frame = calibrate_light(frame, master_dark, master_flat)
            return idx, frame

        loaded_count = 0
        with ThreadPoolExecutor(max_workers=self._n_threads) as ex:
            futures = {ex.submit(load_one, (i, p)): i for i, p in enumerate(lights)}
            for fut in as_completed(futures):
                idx, frame = fut.result()
                calibrated[idx] = frame
                loaded_count += 1
                advance(f"Wczytywanie Light {loaded_count}/{len(lights)}…")

        calibrated = [f for f in calibrated if f is not None]

        # --- Normalization ---
        if self._normalization == "median" and len(calibrated) > 1:
            self.progress.emit(LOAD_PCT_MAX, "Normalizacja do mediany…",
                               time.monotonic() - t_start, 0.0)
            medians = [float(np.median(f)) for f in calibrated]
            ref     = float(np.median(medians))
            calibrated = [
                np.clip(f * (ref / m), 0, 1).astype(np.float32) if m > 0 else f
                for f, m in zip(calibrated, medians)
            ]
        elif self._normalization == "first" and len(calibrated) > 1:
            self.progress.emit(LOAD_PCT_MAX, "Normalizacja do pierwszej klatki…",
                               time.monotonic() - t_start, 0.0)
            ref = float(np.median(calibrated[0]))
            calibrated = [
                np.clip(f * (ref / float(np.median(f))), 0, 1).astype(np.float32)
                if float(np.median(f)) > 0 else f
                for f in calibrated
            ]

        # --- Stack ---
        is_iterative = self._algorithm in ("Sigma Clipping", "Kappa-Sigma")
        iters        = self._iterations if is_iterative else 1

        elapsed = time.monotonic() - t_start
        self.progress.emit(
            LOAD_PCT_MAX,
            f"Stackowanie {len(calibrated)} klatek ({self._algorithm})"
            + (f" — {iters} iteracji…" if is_iterative else "…"),
            elapsed, 0.0,
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
