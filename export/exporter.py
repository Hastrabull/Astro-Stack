"""Export stacked / stretched images to various formats."""

from pathlib import Path
import numpy as np


def _to_uint8(img: np.ndarray) -> np.ndarray:
    return (np.clip(img, 0, 1) * 255).astype(np.uint8)


def _to_uint16(img: np.ndarray) -> np.ndarray:
    return (np.clip(img, 0, 1) * 65535).astype(np.uint16)


def save_tiff16(img: np.ndarray, path: str | Path) -> None:
    import tifffile

    data = _to_uint16(img)
    if data.ndim == 3:
        data = np.moveaxis(data, -1, 0)  # tifffile prefers (C, H, W) for colour
    tifffile.imwrite(str(path), data, photometric="rgb" if img.ndim == 3 else "minisblack")


def save_png(img: np.ndarray, path: str | Path) -> None:
    from PIL import Image

    data = _to_uint8(img)
    mode = "RGB" if data.ndim == 3 else "L"
    Image.fromarray(data, mode=mode).save(str(path))


def save_jpeg(img: np.ndarray, path: str | Path, quality: int = 95) -> None:
    from PIL import Image

    data = _to_uint8(img)
    if data.ndim == 2:
        img_pil = Image.fromarray(data, mode="L").convert("RGB")
    else:
        img_pil = Image.fromarray(data, mode="RGB")
    img_pil.save(str(path), quality=quality)
