"""Stack settings panel — algorithm selector + Stack button."""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QFormLayout, QComboBox,
    QDoubleSpinBox, QSpinBox, QPushButton, QLabel,
)
from PyQt6.QtCore import pyqtSignal

from core.stacking import ALGORITHMS


class StackPanel(QWidget):
    stack_requested = pyqtSignal(str, float, int)  # algorithm, sigma/kappa, iterations

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)

        title = QLabel("<b>Stack Settings</b>")
        layout.addWidget(title)

        form = QFormLayout()

        self._algo = QComboBox()
        self._algo.addItems(list(ALGORITHMS.keys()))
        self._algo.currentTextChanged.connect(self._on_algo_changed)
        form.addRow("Algorithm:", self._algo)

        self._sigma = QDoubleSpinBox()
        self._sigma.setRange(0.5, 10.0)
        self._sigma.setSingleStep(0.5)
        self._sigma.setValue(3.0)
        form.addRow("Sigma / Kappa:", self._sigma)

        self._iters = QSpinBox()
        self._iters.setRange(1, 20)
        self._iters.setValue(5)
        form.addRow("Iterations:", self._iters)

        layout.addLayout(form)

        self._btn_stack = QPushButton("▶  Stack")
        self._btn_stack.setMinimumHeight(36)
        self._btn_stack.setStyleSheet("font-weight: bold; font-size: 14px;")
        self._btn_stack.clicked.connect(self._emit_stack)
        layout.addWidget(self._btn_stack)

        layout.addStretch()
        self._on_algo_changed(self._algo.currentText())

    def _on_algo_changed(self, name: str):
        needs_params = name in ("Sigma Clipping", "Kappa-Sigma")
        self._sigma.setEnabled(needs_params)
        self._iters.setEnabled(needs_params)

    def _emit_stack(self):
        self.stack_requested.emit(
            self._algo.currentText(),
            self._sigma.value(),
            self._iters.value(),
        )

    def set_enabled(self, enabled: bool):
        self._btn_stack.setEnabled(enabled)
