"""Stretching panel with Auto STF, Levels, Curves, and Histogram Equalisation tabs."""

from typing import List, Tuple
import numpy as np

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTabWidget,
    QLabel, QFormLayout, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView,
    QDoubleSpinBox, QSplitter, QFileDialog, QMessageBox,
    QDialog, QRadioButton, QButtonGroup, QDialogButtonBox,
)
from PyQt6.QtCore import pyqtSignal, Qt

try:
    from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
    from matplotlib.figure import Figure
    HAS_MPL = True
except ImportError:
    HAS_MPL = False


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _help_btn(chapter_key: str) -> QPushButton:
    btn = QPushButton("?")
    btn.setFixedSize(18, 18)
    btn.setToolTip("Pomoc")
    btn.setStyleSheet(
        "QPushButton { border-radius: 9px; background: #3a3a3a; color: #aaa; "
        "font-weight: bold; font-size: 11px; border: 1px solid #555; }"
        "QPushButton:hover { background: #4fc3f7; color: #000; }"
    )
    btn.clicked.connect(lambda: _open_help(chapter_key))
    return btn


def _open_help(chapter_key: str):
    from ui.help_dialog import HelpDialog
    HelpDialog.show_chapter(None, chapter_key)


def _row_with_help(widget: QWidget, chapter_key: str) -> QWidget:
    container = QWidget()
    layout = QHBoxLayout(container)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(4)
    layout.addWidget(widget)
    layout.addWidget(_help_btn(chapter_key))
    return container


# ---------------------------------------------------------------------------
# Histogram canvas
# ---------------------------------------------------------------------------

class HistogramCanvas(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Header row with ? button
        header = QHBoxLayout()
        header.addWidget(QLabel("Histogram"))
        header.addStretch()
        header.addWidget(_help_btn("histogram"))
        layout.addLayout(header)

        if HAS_MPL:
            self._fig = Figure(figsize=(3, 1.5), facecolor="#1e1e1e")
            self._ax = self._fig.add_subplot(111)
            self._ax.set_facecolor("#1e1e1e")
            self._ax.tick_params(colors="white", labelsize=7)
            self._fig.tight_layout(pad=0.3)
            self._canvas = FigureCanvas(self._fig)
            self._canvas.setMinimumHeight(100)
            layout.addWidget(self._canvas)
        else:
            layout.addWidget(QLabel("matplotlib not available"))

    def update_histogram(self, img: np.ndarray | None):
        if not HAS_MPL or img is None:
            return
        self._ax.clear()
        self._ax.set_facecolor("#1e1e1e")
        flat = img.ravel()
        if img.ndim == 3:
            for c, col in enumerate(["#ff4444", "#44ff44", "#4444ff"]):
                self._ax.hist(img[:, :, c].ravel(), bins=256, range=(0, 1),
                              color=col, alpha=0.6, histtype="step", linewidth=0.8)
        else:
            self._ax.hist(flat, bins=256, range=(0, 1),
                          color="#aaaaaa", alpha=0.8, histtype="stepfilled")
        self._ax.set_xlim(0, 1)
        self._ax.tick_params(colors="white", labelsize=7)
        self._fig.tight_layout(pad=0.3)
        self._canvas.draw()


# ---------------------------------------------------------------------------
# Individual stretch tabs
# ---------------------------------------------------------------------------

class AutoSTFTab(QWidget):
    apply_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Automatyczny stretch inspirowany PixInsight STF."))
        btn_row = QHBoxLayout()
        apply_btn = QPushButton("Apply Auto STF")
        apply_btn.clicked.connect(self.apply_requested)
        btn_row.addWidget(apply_btn)
        btn_row.addStretch()
        btn_row.addWidget(_help_btn("auto_stf"))
        layout.addLayout(btn_row)
        layout.addStretch()


class LevelsTab(QWidget):
    changed = pyqtSignal(float, float, float)

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        form = QFormLayout()

        def _spin(lo, hi, val, step=0.01):
            s = QDoubleSpinBox()
            s.setRange(lo, hi)
            s.setSingleStep(step)
            s.setValue(val)
            s.setDecimals(3)
            return s

        self._black = _spin(0.0, 0.99, 0.0)
        self._white = _spin(0.01, 1.0, 1.0)
        self._gamma = _spin(0.1, 5.0, 1.0, 0.05)

        form.addRow("Black point:", _row_with_help(self._black, "levels"))
        form.addRow("White point:", _row_with_help(self._white, "levels"))
        form.addRow("Gamma:", _row_with_help(self._gamma, "levels"))
        layout.addLayout(form)

        btn_row = QHBoxLayout()
        apply_btn = QPushButton("Apply")
        apply_btn.clicked.connect(self._emit)
        reset_btn = QPushButton("Reset")
        reset_btn.clicked.connect(self._reset)
        btn_row.addWidget(apply_btn)
        btn_row.addWidget(reset_btn)
        btn_row.addStretch()
        btn_row.addWidget(_help_btn("levels"))
        layout.addLayout(btn_row)
        layout.addStretch()

    def _emit(self):
        self.changed.emit(self._black.value(), self._white.value(), self._gamma.value())

    def _reset(self):
        self._black.setValue(0.0)
        self._white.setValue(1.0)
        self._gamma.setValue(1.0)
        self._emit()

    def values(self):
        return self._black.value(), self._white.value(), self._gamma.value()


class CurvesTab(QWidget):
    changed = pyqtSignal(list)

    DEFAULT_POINTS = [(0.0, 0.0), (0.25, 0.25), (0.5, 0.5), (0.75, 0.75), (1.0, 1.0)]

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Punkty kontrolne krzywej tonalnej (input → output):"))

        self._table = QTableWidget(len(self.DEFAULT_POINTS), 2)
        self._table.setHorizontalHeaderLabels(["Input", "Output"])
        self._table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self._table.setMaximumHeight(180)
        for row, (x, y) in enumerate(self.DEFAULT_POINTS):
            self._table.setItem(row, 0, QTableWidgetItem(f"{x:.3f}"))
            self._table.setItem(row, 1, QTableWidgetItem(f"{y:.3f}"))
        layout.addWidget(self._table)

        btn_row = QHBoxLayout()
        apply_btn = QPushButton("Apply")
        apply_btn.clicked.connect(self._emit)
        reset_btn = QPushButton("Reset")
        reset_btn.clicked.connect(self._reset)
        btn_row.addWidget(apply_btn)
        btn_row.addWidget(reset_btn)
        btn_row.addStretch()
        btn_row.addWidget(_help_btn("curves"))
        layout.addLayout(btn_row)
        layout.addStretch()

    def _parse_points(self) -> List[Tuple[float, float]]:
        pts = []
        for row in range(self._table.rowCount()):
            try:
                x = float(self._table.item(row, 0).text())
                y = float(self._table.item(row, 1).text())
                pts.append((x, y))
            except (AttributeError, ValueError):
                pass
        return pts

    def _emit(self):
        self.changed.emit(self._parse_points())

    def _reset(self):
        for row, (x, y) in enumerate(self.DEFAULT_POINTS):
            self._table.setItem(row, 0, QTableWidgetItem(f"{x:.3f}"))
            self._table.setItem(row, 1, QTableWidgetItem(f"{y:.3f}"))
        self._emit()

    def points(self):
        return self._parse_points()


class HistEqTab(QWidget):
    apply_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Wyrównanie histogramu przez dystrybuantę (CDF)."))
        btn_row = QHBoxLayout()
        apply_btn = QPushButton("Apply Histogram Equalisation")
        apply_btn.clicked.connect(self.apply_requested)
        btn_row.addWidget(apply_btn)
        btn_row.addStretch()
        btn_row.addWidget(_help_btn("hist_eq"))
        layout.addLayout(btn_row)
        layout.addStretch()


# ---------------------------------------------------------------------------
# Main stretch panel
# ---------------------------------------------------------------------------

class SaveDialog(QDialog):
    """Format + path selection dialog for saving the stretched image."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Zapisz obraz")
        self.setFixedWidth(320)
        layout = QVBoxLayout(self)

        layout.addWidget(QLabel("Wybierz format zapisu:"))

        self._jpg = QRadioButton("JPEG (.jpg)  — mniejszy plik, lekka kompresja")
        self._tiff = QRadioButton("TIFF 16-bit (.tif)  — pełna jakość, bez strat")
        self._jpg.setChecked(True)

        group = QButtonGroup(self)
        group.addButton(self._jpg)
        group.addButton(self._tiff)

        layout.addWidget(self._jpg)
        layout.addWidget(self._tiff)
        layout.addSpacing(8)

        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def selected_format(self) -> str:
        return "tiff" if self._tiff.isChecked() else "jpeg"


class StretchPanel(QWidget):
    stretch_changed = pyqtSignal(np.ndarray)

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)

        # Title with ? for the whole stretch section
        title_row = QHBoxLayout()
        title_row.addWidget(QLabel("<b>Stretch</b>"))
        title_row.addStretch()
        title_row.addWidget(_help_btn("stretch"))
        layout.addLayout(title_row)

        self._tabs = QTabWidget()

        self._stf_tab = AutoSTFTab()
        self._levels_tab = LevelsTab()
        self._curves_tab = CurvesTab()
        self._histeq_tab = HistEqTab()

        self._tabs.addTab(self._stf_tab, "Auto STF")
        self._tabs.addTab(self._levels_tab, "Levels")
        self._tabs.addTab(self._curves_tab, "Curves")
        self._tabs.addTab(self._histeq_tab, "Hist EQ")
        layout.addWidget(self._tabs)

        self._histogram = HistogramCanvas()
        layout.addWidget(self._histogram)

        # Reset + Zapisz buttons
        action_row = QHBoxLayout()
        self._btn_reset = QPushButton("↺  Reset")
        self._btn_reset.setToolTip("Usuń wszystkie modyfikacje Stretch i wróć do surowego stacka")
        self._btn_reset.clicked.connect(self._reset_stretch)
        self._btn_save = QPushButton("💾  Zapisz")
        self._btn_save.setToolTip("Zapisz aktualnie wyświetlany obraz (po Stretch)")
        self._btn_save.clicked.connect(self._save_image)
        action_row.addWidget(self._btn_reset)
        action_row.addWidget(self._btn_save)
        layout.addLayout(action_row)

        self._stf_tab.apply_requested.connect(self._apply_stf)
        self._levels_tab.changed.connect(self._apply_levels)
        self._curves_tab.changed.connect(self._apply_curves)
        self._histeq_tab.apply_requested.connect(self._apply_histeq)

        self._source: np.ndarray | None = None
        self._displayed: np.ndarray | None = None

    def set_source(self, img: np.ndarray | None):
        self._source = img
        self._displayed = img
        self._histogram.update_histogram(img)

    def _reset_stretch(self):
        if self._source is None:
            return
        self._displayed = self._source
        self._histogram.update_histogram(self._source)
        self.stretch_changed.emit(self._source)

    def _save_image(self):
        if self._displayed is None:
            QMessageBox.warning(self, "Brak obrazu", "Najpierw wykonaj stackowanie.")
            return

        dlg = SaveDialog(self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return

        fmt = dlg.selected_format()
        if fmt == "tiff":
            file_filter = "TIFF 16-bit (*.tif *.tiff)"
            default = "wynik.tif"
        else:
            file_filter = "JPEG (*.jpg *.jpeg)"
            default = "wynik.jpg"

        path, _ = QFileDialog.getSaveFileName(self, "Zapisz obraz", default, file_filter)
        if not path:
            return

        try:
            from export.exporter import save_tiff16, save_jpeg
            if fmt == "tiff":
                save_tiff16(self._displayed, path)
            else:
                save_jpeg(self._displayed, path)
            QMessageBox.information(self, "Zapisano", f"Plik zapisany:\n{path}")
        except Exception as exc:
            QMessageBox.critical(self, "Błąd zapisu", str(exc))

    def _emit(self, out: np.ndarray):
        self._displayed = out
        self._histogram.update_histogram(out)
        self.stretch_changed.emit(out)

    def _apply_stf(self):
        if self._source is None:
            return
        from core.stretch import auto_stf
        self._emit(auto_stf(self._source))

    def _apply_levels(self, black: float, white: float, gamma: float):
        if self._source is None:
            return
        from core.stretch import apply_levels
        self._emit(apply_levels(self._source, black, white, gamma))

    def _apply_curves(self, points):
        if self._source is None:
            return
        from core.stretch import apply_curves
        self._emit(apply_curves(self._source, points))

    def _apply_histeq(self):
        if self._source is None:
            return
        from core.stretch import hist_eq
        self._emit(hist_eq(self._source))
