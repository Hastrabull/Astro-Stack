"""Image loading — FITS and RAW (CR3/CR2/NEF/ARW etc.)."""

from pathlib import Path
import numpy as np

FITS_EXTENSIONS = {".fit", ".fits", ".fts"}
RAW_EXTENSIONS = {".cr3", ".cr2", ".nef", ".arw", ".dng", ".raf", ".orf", ".rw2"}


def load_image(path: str | Path) -> np.ndarray:
    """Load a FITS or RAW file and return a float32 array normalised to [0, 1].

    Mono images: shape (H, W)
    Colour images: shape (H, W, 3)
    """
    path = Path(path)
    ext = path.suffix.lower()
    if ext in FITS_EXTENSIONS:
        return load_fits(path)
    if ext in RAW_EXTENSIONS:
        return load_raw(path)
    raise ValueError(f"Unsupported file type: {ext}")


def load_fits(path: Path) -> np.ndarray:
    from astropy.io import fits

    with fits.open(str(path)) as hdul:
        # Find first image HDU with data
        data = None
        for hdu in hdul:
            if hdu.data is not None and hdu.data.ndim >= 2:
                data = hdu.data
                break
        if data is None:
            raise ValueError(f"No image data found in {path}")

    data = data.astype(np.float32)

    # FITS can be (C, H, W) — convert to (H, W, C) then squeeze
    if data.ndim == 3 and data.shape[0] in (1, 3):
        data = np.moveaxis(data, 0, -1)
    if data.ndim == 3 and data.shape[2] == 1:
        data = data[:, :, 0]

    # Normalise to [0, 1]
    lo, hi = data.min(), data.max()
    if hi > lo:
        data = (data - lo) / (hi - lo)
    return data


def load_raw(path: Path) -> np.ndarray:
    import rawpy

    with rawpy.imread(str(path)) as raw:
        rgb = raw.postprocess(
            use_camera_wb=True,
            no_auto_bright=True,
            output_bps=16,
            output_color=rawpy.ColorSpace.sRGB,
        )
    # rgb is uint16 (H, W, 3)
    data = rgb.astype(np.float32) / 65535.0
    return data
