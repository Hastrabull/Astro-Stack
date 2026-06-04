"""Plate solve dialog — identifies RA/Dec of the stacked image."""

import numpy as np

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLabel, QPushButton, QDoubleSpinBox, QSpinBox,
    QPlainTextEdit, QGroupBox, QDialogButtonBox, QWidget,
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QFont, QColor


# ---------------------------------------------------------------------------
# Background solver thread
# ---------------------------------------------------------------------------

class SolverThread(QThread):
    log_line  = pyqtSignal(str)
    finished  = pyqtSignal(object)   # SolveResult

    def __init__(self, img: np.ndarray, fov_estimate: float | None,
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
        self.resize(520, 560)
        self.setWindowFlags(
            Qt.WindowType.Window |
            Qt.WindowType.WindowCloseButtonHint
        )

        layout = QVBoxLayout(self)

        # --- Info ---
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
        params_box = QGroupBox("Parametry")
        params_layout = QFormLayout(params_box)

        self._fov = QDoubleSpinBox()
        self._fov.setRange(0.0, 180.0)
        self._fov.setValue(0.0)
        self._fov.setSingleStep(0.5)
        self._fov.setDecimals(2)
        self._fov.setSpecialValueText("Automatycznie")
        self._fov.setSuffix(" °")
        self._fov.setToolTip(
            "Przybliżone pole widzenia teleskopu w stopniach.\n"
            "Zostaw 0 dla automatycznego wykrycia (wolniejsze).\n"
            "Przykłady: Samyang 135mm f/2 ≈ 10°, Newton 200/800 ≈ 2°"
        )
        params_layout.addRow("FOV teleskopu:", self._fov)

        self._fov_err = QDoubleSpinBox()
        self._fov_err.setRange(0.01, 0.5)
        self._fov_err.setValue(0.1)
        self._fov_err.setSingleStep(0.01)
        self._fov_err.setDecimals(2)
        self._fov_err.setToolTip("Dopuszczalny błąd FOV jako ułamek (0.1 = ±10%)")
        params_layout.addRow("Tolerancja FOV:", self._fov_err)

        self._timeout = QSpinBox()
        self._timeout.setRange(5, 300)
        self._timeout.setValue(30)
        self._timeout.setSuffix(" s")
        params_layout.addRow("Timeout:", self._timeout)

        layout.addWidget(params_box)

        # --- Solve button ---
        self._btn_solve = QPushButton("🔭  Uruchom Plate Solving")
        self._btn_solve.setMinimumHeight(36)
        self._btn_solve.setStyleSheet("font-weight: bold; font-size: 13px;")
        self._btn_solve.clicked.connect(self._start_solve)
        layout.addWidget(self._btn_solve)

        # --- Log ---
        log_box = QGroupBox("Log")
        log_layout = QVBoxLayout(log_box)
        self._log = QPlainTextEdit()
        self._log.setReadOnly(True)
        self._log.setMaximumHeight(100)
        self._log.setStyleSheet(
            "background: #111; color: #b0bec5; font-family: Consolas, monospace; font-size: 11px;"
        )
        log_layout.addWidget(self._log)
        layout.addWidget(log_box)

        # --- Result panel ---
        self._result_box = QGroupBox("Wynik")
        result_layout = QFormLayout(self._result_box)

        def _result_label():
            lbl = QLabel("–")
            lbl.setStyleSheet("color: #4fc3f7; font-size: 13px; font-weight: bold;")
            return lbl

        self._lbl_ra    = _result_label()
        self._lbl_dec   = _result_label()
        self._lbl_roll  = _result_label()
        self._lbl_fov   = _result_label()
        self._lbl_rmse  = _result_label()
        self._lbl_match = _result_label()

        result_layout.addRow("RA (rektascensja):", self._lbl_ra)
        result_layout.addRow("Dec (deklinacja):",  self._lbl_dec)
        result_layout.addRow("Roll (obrót):",      self._lbl_roll)
        result_layout.addRow("FOV:",               self._lbl_fov)
        result_layout.addRow("RMSE:",              self._lbl_rmse)
        result_layout.addRow("Dopasowane gwiazdy:", self._lbl_match)

        layout.addWidget(self._result_box)

        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        btns.rejected.connect(self.close)
        layout.addWidget(btns)

        self._log.appendPlainText(
            "Gotowy. Opcjonalnie podaj FOV teleskopu i kliknij Uruchom."
        )

    def _start_solve(self):
        if self._thread and self._thread.isRunning():
            return

        self._btn_solve.setEnabled(False)
        self._btn_solve.setText("Solving…")
        self._log.clear()
        self._clear_result()

        self._thread = SolverThread(
            self._img,
            fov_estimate=self._fov.value(),
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
