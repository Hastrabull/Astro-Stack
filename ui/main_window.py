"""Main application window."""

from pathlib import Path
import numpy as np

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QSplitter, QStatusBar, QProgressBar, QLabel,
    QMenuBar, QMenu, QFileDialog, QMessageBox,
)
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QAction

from ui.frames_panel import FramesPanel
from ui.stack_panel import StackPanel
from ui.stretch_panel import StretchPanel
from ui.preview_widget import PreviewWidget
from ui.worker import StackWorker


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("AstroStack")
        self.resize(1280, 780)

        self._stacked_img: np.ndarray | None = None
        self._displayed_img: np.ndarray | None = None
        self._worker: StackWorker | None = None

        self._build_menu()
        self._build_ui()
        self._build_statusbar()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_menu(self):
        mb = self.menuBar()

        file_menu = mb.addMenu("File")
        act_exit = QAction("Exit", self)
        act_exit.triggered.connect(self.close)
        file_menu.addAction(act_exit)

        export_menu = mb.addMenu("Export")
        act_tiff = QAction("Save as TIFF 16-bit…", self)
        act_tiff.triggered.connect(lambda: self._export("tiff"))
        act_png = QAction("Save as PNG…", self)
        act_png.triggered.connect(lambda: self._export("png"))
        act_jpg = QAction("Save as JPEG…", self)
        act_jpg.triggered.connect(lambda: self._export("jpeg"))
        export_menu.addAction(act_tiff)
        export_menu.addAction(act_png)
        export_menu.addAction(act_jpg)

        view_menu = mb.addMenu("View")
        act_fit = QAction("Fit image to window", self)
        act_fit.triggered.connect(lambda: self._preview.reset_zoom())
        view_menu.addAction(act_fit)

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QHBoxLayout(central)
        root.setContentsMargins(4, 4, 4, 4)
        root.setSpacing(4)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left — frames panel
        self._frames_panel = FramesPanel()
        self._frames_panel.setMinimumWidth(220)
        self._frames_panel.setMaximumWidth(320)
        splitter.addWidget(self._frames_panel)

        # Center — preview
        self._preview = PreviewWidget()
        splitter.addWidget(self._preview)

        # Right — stack + stretch
        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(4, 4, 4, 4)

        self._stack_panel = StackPanel()
        self._stack_panel.stack_requested.connect(self._on_stack_requested)
        right_layout.addWidget(self._stack_panel)

        self._stretch_panel = StretchPanel()
        self._stretch_panel.stretch_changed.connect(self._on_stretch_changed)
        right_layout.addWidget(self._stretch_panel)

        right.setMinimumWidth(260)
        right.setMaximumWidth(360)
        splitter.addWidget(right)

        splitter.setSizes([260, 720, 300])
        root.addWidget(splitter)

    def _build_statusbar(self):
        sb = QStatusBar()
        self.setStatusBar(sb)

        self._status_label = QLabel("Ready")
        self._progress = QProgressBar()
        self._progress.setRange(0, 100)
        self._progress.setValue(0)
        self._progress.setMaximumWidth(220)
        self._progress.setVisible(False)

        sb.addWidget(self._status_label, 1)
        sb.addPermanentWidget(self._progress)

    # ------------------------------------------------------------------
    # Stacking
    # ------------------------------------------------------------------

    def _on_stack_requested(self, algorithm: str, sigma: float, iterations: int):
        paths = self._frames_panel.all_paths()
        if not paths.get("Lights"):
            QMessageBox.warning(self, "No Lights", "Please add Light frames before stacking.")
            return

        self._stack_panel.set_enabled(False)
        self._progress.setVisible(True)
        self._progress.setValue(0)
        self._status_label.setText("Starting…")

        self._worker = StackWorker(paths, algorithm, sigma, iterations)
        self._worker.progress.connect(self._on_progress)
        self._worker.finished.connect(self._on_stack_finished)
        self._worker.error.connect(self._on_stack_error)
        self._worker.start()

    def _on_progress(self, pct: int, msg: str):
        self._progress.setValue(pct)
        self._status_label.setText(msg)

    def _on_stack_finished(self, result: np.ndarray):
        self._stacked_img = result
        self._displayed_img = result.copy()
        self._stretch_panel.set_source(result)
        self._preview.update_image(result)
        self._progress.setVisible(False)
        self._stack_panel.set_enabled(True)
        self._status_label.setText(f"Stack complete — shape: {result.shape}, dtype: {result.dtype}")

    def _on_stack_error(self, msg: str):
        QMessageBox.critical(self, "Stack error", msg)
        self._progress.setVisible(False)
        self._stack_panel.set_enabled(True)
        self._status_label.setText("Error.")

    # ------------------------------------------------------------------
    # Stretch
    # ------------------------------------------------------------------

    def _on_stretch_changed(self, img: np.ndarray):
        self._displayed_img = img
        self._preview.update_image(img)

    # ------------------------------------------------------------------
    # Export
    # ------------------------------------------------------------------

    def _export(self, fmt: str):
        if self._displayed_img is None:
            QMessageBox.warning(self, "Nothing to export", "Stack an image first.")
            return

        filters = {
            "tiff": "TIFF 16-bit (*.tif *.tiff)",
            "png": "PNG image (*.png)",
            "jpeg": "JPEG image (*.jpg *.jpeg)",
        }
        default_ext = {"tiff": ".tif", "png": ".png", "jpeg": ".jpg"}

        path, _ = QFileDialog.getSaveFileName(
            self, "Export image", f"result{default_ext[fmt]}", filters[fmt]
        )
        if not path:
            return

        from export.exporter import save_tiff16, save_png, save_jpeg
        try:
            if fmt == "tiff":
                save_tiff16(self._stacked_img if self._stacked_img is not None else self._displayed_img, path)
            elif fmt == "png":
                save_png(self._displayed_img, path)
            else:
                save_jpeg(self._displayed_img, path)
            self._status_label.setText(f"Saved: {Path(path).name}")
        except Exception as exc:
            QMessageBox.critical(self, "Export error", str(exc))
