# AstroStack

A Windows desktop application for astrophotography image stacking. It handles the complete calibration and integration pipeline — from raw light frames to a processed, stretched result ready for export.

---

## What it does

AstroStack takes multiple exposures of the same deep-sky object and combines them into a single, low-noise master image. The more frames you stack, the better the signal-to-noise ratio of the result. The application covers:

- **Calibration** — subtracts thermal noise (Darks, Bias) and corrects optical vignetting and dust (Flats)
- **Frame analysis** — detects stars in each light frame, measures sharpness (FWHM) and signal quality (SNR), and ranks frames automatically
- **Stacking** — combines calibrated frames using one of four mathematical algorithms
- **Stretching** — maps the linear 32-bit stack to a visually pleasing image
- **Plate solving** — identifies which part of the sky is in the frame and returns precise RA/Dec coordinates
- **Export** — saves the result as TIFF 16-bit, PNG, or JPEG

Alignment of frames is assumed to be done externally (e.g. in NINA, Siril, or DeepSkyStacker) before importing into AstroStack.

---

## Supported file formats

| Type | Extensions |
|------|-----------|
| FITS | `.fit` `.fits` `.fts` |
| Canon RAW | `.cr3` `.cr2` |
| Nikon RAW | `.nef` |
| Sony RAW | `.arw` |
| Other RAW | `.dng` `.raf` `.orf` `.rw2` |

---

## Stacking algorithms

| Algorithm | Description |
|-----------|-------------|
| **Mean** | Simple arithmetic average. Fast, best for clean datasets. |
| **Median** | Picks the middle value per pixel. Resistant to single-frame artefacts. |
| **Sigma Clipping** | Iteratively rejects pixels deviating more than N sigma from the mean. Removes satellite trails and hot pixels. |
| **Kappa-Sigma** | Variant of sigma clipping with an explicit kappa parameter. |

---

## Frame calibration pipeline

```
Master Bias  = stack(Bias frames)
Master Dark  = stack(Dark frames) − Master Bias
Master Flat  = stack(Flat frames) / median(Flat)

Calibrated Light = (Light − Master Dark) / Master Flat
```

Any calibration type can be omitted — the pipeline skips missing steps automatically.

---

## Pre-stack frame review

Before stacking, a review dialog opens for every session. It shows each light frame with:

- **Thumbnail** preview (auto-stretched)
- **Star count** — number of stars detected by photutils IRAFStarFinder
- **FWHM** — median full-width at half-maximum of detected stars in pixels (lower = sharper)
- **SNR** — signal-to-noise ratio estimate
- **File size**
- **Status** — Good / Average / Weak signal / Blurry stars
- **Rank** — composite score (40 % SNR + 40 % FWHM + 20 % star count), rank 1 is the best frame

Frames can be excluded individually or via automatic rejection by SNR, FWHM, or star count threshold.

---

## Normalization

Optional pre-stack brightness equalisation:

| Mode | When to use |
|------|-------------|
| None | Stable sky conditions, consistent exposure |
| Normalize to median | Long sessions with varying sky brightness or thin cloud |
| Normalize to first frame | When one reference frame sets the baseline |

---

## Stretch modes

| Mode | Description |
|------|-------------|
| **Auto STF** | One-click stretch modelled on PixInsight's Screen Transfer Function |
| **Levels** | Manual black point, white point and gamma |
| **Curves** | Cubic-spline tone curve via control points |
| **Histogram EQ** | CDF-based equalisation |

Stretch is non-destructive — the raw 32-bit stack is always preserved. TIFF 16-bit export saves the pre-stretch data.

---

## Plate solving

After stacking, **Narzędzia → Plate Solving** identifies the star field using [tetra3](https://github.com/esa/tetra3) (ESA). It runs fully offline with the bundled star catalogue.

Input: focal length (mm) + sensor size from a dropdown of 18 common presets. The application computes the field of view automatically.

Output: RA/Dec of the frame centre (decimal degrees and HMS/DMS), camera roll angle, measured FOV, RMSE, and number of matched stars.

---

## Technology

| Layer | Library |
|-------|---------|
| GUI | PyQt6 |
| FITS I/O | astropy |
| RAW I/O | rawpy (libraw) |
| Maths | NumPy · SciPy |
| Star detection | photutils |
| Plate solving | tetra3 (ESA) |
| Histogram | matplotlib |
| Image export | Pillow · tifffile |
| Packaging | PyInstaller |

---

## Installation

### Pre-built executable (recommended)

Download `AstroStack.exe` from the [latest release](https://github.com/Hastrabull/Astro-Stack/releases/latest). No Python or additional libraries required — double-click to run.

First launch may take 5–10 seconds while the executable unpacks itself.

### Run from source

```powershell
git clone https://github.com/Hastrabull/Astro-Stack.git
cd Astro-Stack

python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt

python main.py
```

### Build executable locally

```powershell
pip install pyinstaller
pyinstaller astrostack.spec
# Output: dist\AstroStack.exe
```

---

## Automated releases

Every version tag (`v*.*.*`) triggers a GitHub Actions workflow that builds `AstroStack.exe` on `windows-latest` and publishes it as a GitHub Release automatically.

---

## Project structure

```
astrostack/
├── main.py                  # Entry point
├── core/
│   ├── loader.py            # FITS and RAW loading → float32
│   ├── calibration.py       # Bias / Dark / Flat pipeline
│   ├── stacking.py          # Mean, Median, Sigma, Kappa-Sigma
│   ├── stretch.py           # STF, Levels, Curves, Histogram EQ
│   ├── stardetect.py        # Star detection and FWHM (photutils)
│   └── platesolve.py        # Plate solving (tetra3)
├── ui/
│   ├── main_window.py       # Main window layout
│   ├── frames_panel.py      # Frame list tabs
│   ├── prestack_dialog.py   # Frame review, normalization, performance
│   ├── stack_panel.py       # Algorithm settings
│   ├── stretch_panel.py     # Stretch controls + histogram
│   ├── preview_widget.py    # Zoomable image preview
│   ├── platesolve_dialog.py # Plate solve dialog
│   ├── worker.py            # Background stacking thread
│   └── help_dialog.py       # In-app manual
├── export/
│   └── exporter.py          # TIFF / PNG / JPEG output
├── requirements.txt
└── astrostack.spec          # PyInstaller build spec
```

---

## License

GPL-3.0 — see [LICENSE](LICENSE).
