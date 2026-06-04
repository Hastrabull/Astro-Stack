"""Stack settings panel — algorithm selector + Stack button."""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QFormLayout, QComboBox,
    QDoubleSpinBox, QSpinBox, QPushButton, QLabel, QHBoxLayout,
)
from PyQt6.QtCore import pyqtSignal

from core.stacking import ALGORITHMS


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
    """Wrap a widget with a ? button on the right."""
    container = QWidget()
    layout = QHBoxLayout(container)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(4)
    layout.addWidget(widget)
    layout.addWidget(_help_btn(chapter_key))
    return container


class StackPanel(QWidget):
    stack_requested = pyqtSignal(str, float, int)  # algorithm, sigma/kappa, iterations

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)

        # Title row with ? for the whole section
        title_row = QHBoxLayout()
        title_row.addWidget(QLabel("<b>Stack Settings</b>"))
        title_row.addStretch()
        title_row.addWidget(_help_btn("stack_settings"))
        layout.addLayout(title_row)

        form = QFormLayout()

        self._algo = QComboBox()
        self._algo.addItems(list(ALGORITHMS.keys()))
        self._algo.currentTextChanged.connect(self._on_algo_changed)
        form.addRow("Algorithm:", _row_with_help(self._algo, "algorithm"))

        self._sigma = QDoubleSpinBox()
        self._sigma.setRange(0.5, 10.0)
        self._sigma.setSingleStep(0.5)
        self._sigma.setValue(3.0)
        form.addRow("Sigma / Kappa:", _row_with_help(self._sigma, "sigma"))

        self._iters = QSpinBox()
        self._iters.setRange(1, 20)
        self._iters.setValue(5)
        form.addRow("Iterations:", _row_with_help(self._iters, "iterations"))

        layout.addLayout(form)

        self._btn_stack = QPushButton("▶  Stack")
        self._btn_stack.setMinimumHeight(36)
        self._btn_stack.setStyleSheet("font-weight: bold; font-size: 14px;")
        self._btn_stack.clicked.connect(self._emit_stack)
        layout.addWidget(self._btn_stack)
        layout.setContentsMargins(4, 4, 4, 8)

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
