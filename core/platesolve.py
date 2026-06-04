"""Plate solving via tetra3 — identifies star field position (RA/Dec)."""

from __future__ import annotations
from dataclasses import dataclass
from typing import Callable
import numpy as np


@dataclass
class SolveResult:
    success: bool
    ra: float = 0.0        # degrees
    dec: float = 0.0       # degrees
    roll: float = 0.0      # degrees (camera rotation)
    fov: float = 0.0       # degrees (field of view)
    rmse: float = 0.0      # arcseconds
    n_matches: int = 0
    message: str = ""

    @property
    def ra_hms(self) -> str:
        h = int(self.ra / 15)
        m = int((self.ra / 15 - h) * 60)
        s = ((self.ra / 15 - h) * 60 - m) * 60
        return f"{h:02d}h {m:02d}m {s:05.2f}s"

    @property
    def dec_dms(self) -> str:
        sign = "+" if self.dec >= 0 else "-"
        d = int(abs(self.dec))
        m = int((abs(self.dec) - d) * 60)
        s = ((abs(self.dec) - d) * 60 - m) * 60
        return f"{sign}{d:02d}° {m:02d}' {s:05.2f}\""


def solve(
    img: np.ndarray,
    fov_estimate: float | None = None,
    fov_max_error: float | None = None,
    timeout: float = 30.0,
    log_cb: Callable[[str], None] | None = None,
) -> SolveResult:
    """Attempt to plate-solve img (float32 [0,1]) using tetra3.

    Args:
        img: float32 array, mono or RGB
        fov_estimate: estimated field of view in degrees (helps speed)
        fov_max_error: accepted FOV error fraction (default 0.1)
        timeout: solve timeout in seconds
        log_cb: optional callback for status messages
    """
    def log(msg: str):
        if log_cb:
            log_cb(msg)

    try:
        import tetra3
    except ImportError:
        return SolveResult(False, message="Biblioteka tetra3 nie jest zainstalowana.")

    log("Ładowanie bazy danych tetra3…")
    try:
        t3 = tetra3.Tetra3("default_database")
    except Exception as e:
        return SolveResult(False, message=f"Nie można załadować bazy danych tetra3: {e}")

    # Convert to uint8 PIL image (tetra3 expects PIL Image)
    gray = img.mean(axis=2) if img.ndim == 3 else img
    gray_u8 = (np.clip(gray, 0, 1) * 255).astype(np.uint8)

    from PIL import Image as PILImage
    pil_img = PILImage.fromarray(gray_u8, mode="L")

    log(f"Plate solving… (FOV estimate: {fov_estimate}°, timeout: {timeout}s)")

    kwargs: dict = {"solve_timeout": timeout}
    if fov_estimate is not None:
        kwargs["fov_estimate"] = fov_estimate
    if fov_max_error is not None:
        kwargs["fov_max_error"] = fov_max_error

    try:
        result = t3.solve_from_image(pil_img, **kwargs)
    except Exception as e:
        return SolveResult(False, message=f"Błąd podczas plate solving: {e}")

    if result is None or result.get("RA") is None:
        return SolveResult(False, message="Nie udało się zidentyfikować pola gwiazd. "
                           "Spróbuj podać przybliżone FOV lub wydłużyć timeout.")

    fov_deg  = result.get("FOV", 0.0)
    if isinstance(fov_deg, (list, tuple)):
        fov_deg = fov_deg[0]

    rmse_as  = result.get("RMSE", 0.0)
    if rmse_as and fov_deg:
        h = img.shape[0]
        rmse_as = rmse_as * fov_deg * 3600 / h  # convert to arcsec

    return SolveResult(
        success=True,
        ra=float(result["RA"]),
        dec=float(result["Dec"]),
        roll=float(result.get("Roll", 0.0)),
        fov=float(fov_deg),
        rmse=float(rmse_as),
        n_matches=int(result.get("Matches", 0)),
        message="OK",
    )
