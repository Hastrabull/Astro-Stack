"""Plate solve dialog — identifies RA/Dec of the stacked image."""

import math
import numpy as np

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLabel, QPushButton, QDoubleSpinBox, QSpinBox,
    QPlainTextEdit, QGroupBox, QDialogButtonBox, QComboBox,
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal


# ---------------------------------------------------------------------------
# Standard sensor sizes: name → (width_mm, height_mm)
# ---------------------------------------------------------------------------
SENSOR_SIZES = {
    "Full Frame 35mm  (36 × 24 mm)":          (36.0,  24.0),
    "APS-C Canon  (22.3 × 14.9 mm)":          (22.3,  14.9),
    "APS-C Nikon / Sony / Pentax  (23.5 × 15.6 mm)": (23.5, 15.6),
    "APS-C Fujifilm  (23.5 × 15.6 mm)":       (23.5,  15.6),
    "APS-H Canon (stary)  (27.9 × 18.6 mm)":  (27.9,  18.6),
    "Micro 4/3  (17.3 × 13 mm)":              (17.3,  13.0),
    "1\"  (13.2 × 8.8 mm)":                   (13.2,   8.8),
    "2/3\"  (8.8 × 6.6 mm)":                  ( 8.8,   6.6),
    "Medium Format Hasselblad X  (43.8 × 32.9 mm)": (43.8, 32.9),
    "Medium Format Phase One  (53.4 × 40 mm)": (53.4, 40.0),
    "ASI294MC Pro  (19.1 × 13 mm)":           (19.1,  13.0),
    "ASI183MC Pro  (13.2 × 8.8 mm)":          (13.2,   8.8),
    "ASI071MC Pro  (23.4 × 15.6 mm)":         (23.4,  15.6),
    "ASI2600MC Pro  (28.3 × 18.9 mm)":        (28.3,  18.9),
    "ASI6200MC Pro  (36 × 24 mm)":            (36.0,  24.0),
    "Canon EOS Ra  (36 × 24 mm)":             (36.0,  24.0),
    "Nikon Z 6  (35.9 × 23.9 mm)":            (35.9,  23.9),
    "Sony A7S III  (35.6 × 23.8 mm)":         (35.6,  23.8),
}


def compute_fov(focal_mm: float, sensor_w: float, sensor_h: float) -> tuple[float, float, float]:
    """Return (fov_w, fov_h, fov_diagonal) in degrees."""
    if focal_mm <= 0:
        return 0.0, 0.0, 0.0
    fov_w    = math.degrees(2 * math.atan(sensor_w / (2 * focal_mm)))
    fov_h    = math.degrees(2 * math.atan(sensor_h / (2 * focal_mm)))
    diagonal = math.sqrt(sensor_w ** 2 + sensor_h ** 2)
    fov_diag = math.degrees(2 * math.atan(diagonal / (2 * focal_mm)))
    return fov_w, fov_h, fov_diag


# ---------------------------------------------------------------------------
# Background solver thread
# ---------------------------------------------------------------------------

class SolverThread(QThread):
    log_line = pyqtSignal(str)
    finished = pyqtSignal(object)

    def __init__(self, img: np.ndarray, fov_estimate: float,
                 fov_max_error: float, timeout: float):
        super().__init__()
        self._img           = img
        self._fov_estimate  = fov_estimate if fov_estimate > 0 else None
        self._fov_max_error = fov_max_error
        self._timeout       = timeout

    def run(self):
        from core.platesolve import solve
        result = solve(
            self._img,
            fov_estimate=self._fov_estimate,
            fov_max_error=self._fov_max_error,
            timeout=self._timeout,
            log_cb=self.log_line.emit,
        )
        self.finished.emit(result)


# ---------------------------------------------------------------------------
# Dialog
# ---------------------------------------------------------------------------

class PlateSolveDialog(QDialog):
    def __init__(self, img: np.ndarray, parent=None):
        super().__init__(parent)
        self._img    = img
        self._thread = None

        self.setWindowTitle("Plate Solving — identyfikacja pola gwiazd")
        self.resize(540, 620)
        self.setWindowFlags(
            Qt.WindowType.Window |
            Qt.WindowType.WindowCloseButtonHint
        )

        layout = QVBoxLayout(self)

        info = QLabel(
            "<b>Plate Solving</b> identyfikuje, które gwiazdy są widoczne na obrazie<br>"
            "i wyznacza współrzędne RA/Dec centrum kadru.<br>"
            "<span style='color:#aaa; font-size:11px;'>"
            "Powered by <b>tetra3</b> (ESA) — działa offline, bez dostępu do internetu."
            "</span>"
        )
        info.setWordWrap(True)
        layout.addWidget(info)

        # --- Parameters ---
        params_box = QGroupBox("Parametry optyczne")
        params_layout = QFormLayout(params_box)
        params_layout.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)

        # Focal length
        self._focal = QDoubleSpinBox()
        self._focal.setRange(1.0, 5000.0)
        self._focal.setValue(135.0)
        self._focal.setSingleStep(1.0)
        self._focal.setDecimals(1)
        self._focal.setSuffix(" mm")
        self._focal.setToolTip("Ogniskowa obiektywu / teleskopu w milimetrach")
        self._focal.valueChanged.connect(self._update_fov)
        params_layout.addRow("Ogniskowa:", self._focal)

        # Sensor size dropdown
        self._sensor = QComboBox()
        self._sensor.addItems(list(SENSOR_SIZES.keys()))
        self._sensor.setCurrentIndex(0)  # Full Frame default
        self._sensor.currentIndexChanged.connect(self._update_fov)
        params_layout.addRow("Rozmiar matrycy:", self._sensor)

        # Computed FOV (read-only display)
        self._fov_label = QLabel("–")
        self._fov_label.setStyleSheet("color: #4fc3f7; font-size: 12px;")
        params_layout.addRow("Obliczone FOV:", self._fov_label)

        layout.addWidget(params_box)

        # Advanced params (collapsible-ish — just small group)
        adv_box = QGroupBox("Zaawansowane")
        adv_layout = QFormLayout(adv_box)

        self._fov_err = QDoubleSpinBox()
        self._fov_err.setRange(0.01, 0.5)
        self._fov_err.setValue(0.1)
        self._fov_err.setSingleStep(0.01)
        self._fov_err.setDecimals(2)
        self._fov_err.setToolTip("Dopuszczalny błąd FOV jako ułamek (0.1 = ±10%)")
        adv_layout.addRow("Tolerancja FOV:", self._fov_err)

        self._timeout = QSpinBox()
        self._timeout.setRange(5, 300)
        self._timeout.setValue(30)
        self._timeout.setSuffix(" s")
        adv_layout.addRow("Timeout:", self._timeout)

        layout.addWidget(adv_box)

        # Solve button
        self._btn_solve = QPushButton("🔭  Uruchom Plate Solving")
        self._btn_solve.setMinimumHeight(36)
        self._btn_solve.setStyleSheet("font-weight: bold; font-size: 13px;")
        self._btn_solve.clicked.connect(self._start_solve)
        layout.addWidget(self._btn_solve)

        # Log
        log_box = QGroupBox("Log")
        log_layout = QVBoxLayout(log_box)
        self._log = QPlainTextEdit()
        self._log.setReadOnly(True)
        self._log.setMaximumHeight(90)
        self._log.setStyleSheet(
            "background: #111; color: #b0bec5; "
            "font-family: Consolas, monospace; font-size: 11px;"
        )
        log_layout.addWidget(self._log)
        layout.addWidget(log_box)

        # Result panel
        result_box = QGroupBox("Wynik")
        result_layout = QFormLayout(result_box)

        def _rl():
            lbl = QLabel("–")
            lbl.setStyleSheet("color: #4fc3f7; font-size: 13px; font-weight: bold;")
            return lbl

        self._lbl_ra    = _rl()
        self._lbl_dec   = _rl()
        self._lbl_roll  = _rl()
        self._lbl_fov   = _rl()
        self._lbl_rmse  = _rl()
        self._lbl_match = _rl()

        result_layout.addRow("RA (rektascensja):",  self._lbl_ra)
        result_layout.addRow("Dec (deklinacja):",   self._lbl_dec)
        result_layout.addRow("Roll (obrót):",       self._lbl_roll)
        result_layout.addRow("FOV (zmierzone):",    self._lbl_fov)
        result_layout.addRow("RMSE:",               self._lbl_rmse)
        result_layout.addRow("Dopasowane gwiazdy:", self._lbl_match)

        layout.addWidget(result_box)

        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        btns.rejected.connect(self.close)
        layout.addWidget(btns)

        # Init FOV display
        self._update_fov()
        self._log.appendPlainText(
            "Gotowy. Ustaw ogniskową i rozmiar matrycy, następnie kliknij Uruchom."
        )

    # ------------------------------------------------------------------

    def _update_fov(self):
        focal = self._focal.value()
        name  = self._sensor.currentText()
        w, h  = SENSOR_SIZES.get(name, (36.0, 24.0))
        fov_w, fov_h, fov_diag = compute_fov(focal, w, h)
        self._fov_label.setText(
            f"{fov_w:.2f}° × {fov_h:.2f}°  (przekątna: {fov_diag:.2f}°)"
        )
        self._computed_fov = fov_diag  # used by solver

    def _start_solve(self):
        if self._thread and self._thread.isRunning():
            return

        self._btn_solve.setEnabled(False)
        self._btn_solve.setText("Solving…")
        self._log.clear()
        self._clear_result()

        self._thread = SolverThread(
            self._img,
            fov_estimate=self._computed_fov,
            fov_max_error=self._fov_err.value(),
            timeout=float(self._timeout.value()),
        )
        self._thread.log_line.connect(self._log.appendPlainText)
        self._thread.finished.connect(self._on_finished)
        self._thread.start()

    def _on_finished(self, result):
        self._btn_solve.setEnabled(True)
        self._btn_solve.setText("🔭  Uruchom Plate Solving")

        if not result.success:
            self._log.appendPlainText(f"❌ {result.message}")
            return

        self._log.appendPlainText("✓ Rozwiązano pomyślnie!")
        self._lbl_ra.setText(f"{result.ra:.6f}°  ({result.ra_hms})")
        self._lbl_dec.setText(f"{result.dec:.6f}°  ({result.dec_dms})")
        self._lbl_roll.setText(f"{result.roll:.2f}°")
        self._lbl_fov.setText(f"{result.fov:.4f}°")
        self._lbl_rmse.setText(f'{result.rmse:.2f}"' if result.rmse else "–")
        self._lbl_match.setText(str(result.n_matches) if result.n_matches else "–")

    def _clear_result(self):
        for lbl in (self._lbl_ra, self._lbl_dec, self._lbl_roll,
                    self._lbl_fov, self._lbl_rmse, self._lbl_match):
            lbl.setText("–")

    def closeEvent(self, event):
        if self._thread and self._thread.isRunning():
            self._thread.terminate()
            self._thread.wait(1000)
        super().closeEvent(event)
