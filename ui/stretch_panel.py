"""Stretching panel with Auto STF, Levels, Curves, and Histogram Equalisation tabs."""

from typing import List, Tuple
import numpy as np

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTabWidget,
    QSlider, QLabel, QFormLayout, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView,
    QDoubleSpinBox, QSplitter,
)
from PyQt6.QtCore import pyqtSignal, Qt

try:
    from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
    from matplotlib.figure import Figure
    HAS_MPL = True
except ImportError:
    HAS_MPL = False


class HistogramCanvas(QWidget):
    """Embedded matplotlib histogram of the current image."""

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
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
        colors = ["#ff4444", "#44ff44", "#4444ff"] if img.ndim == 3 else ["#aaaaaa"]
        if img.ndim == 3:
            for c, col in enumerate(colors):
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
        layout.addWidget(QLabel("Automatic Screen Transfer Function (PixInsight-style)"))
        btn = QPushButton("Apply Auto STF")
        btn.clicked.connect(self.apply_requested)
        layout.addWidget(btn)
        layout.addStretch()


class LevelsTab(QWidget):
    changed = pyqtSignal(float, float, float)  # black, white, gamma

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

        form.addRow("Black point:", self._black)
        form.addRow("White point:", self._white)
        form.addRow("Gamma:", self._gamma)
        layout.addLayout(form)

        apply_btn = QPushButton("Apply")
        apply_btn.clicked.connect(self._emit)
        layout.addWidget(apply_btn)

        reset_btn = QPushButton("Reset")
        reset_btn.clicked.connect(self._reset)
        layout.addWidget(reset_btn)
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
    changed = pyqtSignal(list)  # list of (x, y) tuples

    DEFAULT_POINTS = [(0.0, 0.0), (0.25, 0.25), (0.5, 0.5), (0.75, 0.75), (1.0, 1.0)]

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Control points (input → output):"))

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
        layout.addWidget(QLabel("Equalise histogram using cumulative distribution function."))
        btn = QPushButton("Apply Histogram Equalisation")
        btn.clicked.connect(self.apply_requested)
        layout.addWidget(btn)
        layout.addStretch()


# ---------------------------------------------------------------------------
# Main stretch panel
# ---------------------------------------------------------------------------

class StretchPanel(QWidget):
    stretch_changed = pyqtSignal(np.ndarray)  # emits stretched image

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)

        title = QLabel("<b>Stretch</b>")
        layout.addWidget(title)

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

        self._stf_tab.apply_requested.connect(self._apply_stf)
        self._levels_tab.changed.connect(self._apply_levels)
        self._curves_tab.changed.connect(self._apply_curves)
        self._histeq_tab.apply_requested.connect(self._apply_histeq)

        self._source: np.ndarray | None = None

    def set_source(self, img: np.ndarray | None):
        """Set the raw stacked image (before stretch)."""
        self._source = img
        self._histogram.update_histogram(img)

    def _apply_stf(self):
        if self._source is None:
            return
        from core.stretch import auto_stf
        out = auto_stf(self._source)
        self._histogram.update_histogram(out)
        self.stretch_changed.emit(out)

    def _apply_levels(self, black: float, white: float, gamma: float):
        if self._source is None:
            return
        from core.stretch import apply_levels
        out = apply_levels(self._source, black, white, gamma)
        self._histogram.update_histogram(out)
        self.stretch_changed.emit(out)

    def _apply_curves(self, points):
        if self._source is None:
            return
        from core.stretch import apply_curves
        out = apply_curves(self._source, points)
        self._histogram.update_histogram(out)
        self.stretch_changed.emit(out)

    def _apply_histeq(self):
        if self._source is None:
            return
        from core.stretch import hist_eq
        out = hist_eq(self._source)
        self._histogram.update_histogram(out)
        self.stretch_changed.emit(out)
