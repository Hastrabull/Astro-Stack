"""Main application window."""

from pathlib import Path
import numpy as np

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QSplitter, QProgressBar, QLabel,
    QFileDialog, QMessageBox, QFrame, QPlainTextEdit, QDialog,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QAction, QFont

from ui.frames_panel import FramesPanel
from ui.stack_panel import StackPanel
from ui.stretch_panel import StretchPanel
from ui.preview_widget import PreviewWidget
from ui.worker import StackWorker


class BottomPanel(QWidget):
    """Fixed-height status panel: progress row + log row."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(100)
        self.setStyleSheet("background: #1a1a1a; border-top: 1px solid #333;")

        outer = QVBoxLayout(self)
        outer.setContentsMargins(8, 6, 8, 6)
        outer.setSpacing(4)

        # --- Row 1: progress bar + time label ---
        row1 = QHBoxLayout()
        row1.setSpacing(8)

        progress_label = QLabel("Postęp:")
        progress_label.setFixedWidth(52)
        progress_label.setStyleSheet("color: #aaa; font-size: 12px;")
        row1.addWidget(progress_label)

        self._progress = QProgressBar()
        self._progress.setRange(0, 100)
        self._progress.setValue(0)
        self._progress.setFixedHeight(18)
        self._progress.setStyleSheet("""
            QProgressBar {
                border: 1px solid #444; border-radius: 4px;
                background: #2a2a2a; text-align: center;
                color: #ddd; font-size: 11px;
            }
            QProgressBar::chunk {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #1565c0, stop:1 #4fc3f7);
                border-radius: 3px;
            }
        """)
        row1.addWidget(self._progress, stretch=1)

        self._time_label = QLabel("–")
        self._time_label.setFixedWidth(160)
        self._time_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self._time_label.setStyleSheet("color: #aaa; font-size: 11px;")
        row1.addWidget(self._time_label)

        outer.addLayout(row1)

        # --- Row 2: log ---
        row2 = QHBoxLayout()
        row2.setSpacing(8)

        log_label = QLabel("Log:")
        log_label.setFixedWidth(52)
        log_label.setStyleSheet("color: #aaa; font-size: 12px;")
        row2.addWidget(log_label)

        self._log = QPlainTextEdit()
        self._log.setReadOnly(True)
        self._log.setFixedHeight(52)
        self._log.setStyleSheet("""
            QPlainTextEdit {
                background: #111; color: #b0bec5;
                border: 1px solid #333; border-radius: 3px;
                font-family: Consolas, monospace; font-size: 11px;
                padding: 2px 4px;
            }
        """)
        self._log.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        row2.addWidget(self._log)

        outer.addLayout(row2)

    def update_progress(self, pct: int, msg: str, elapsed: float, remaining: float):
        self._progress.setValue(pct)
        self._progress.setFormat(f"{pct}%")

        if pct >= 100:
            self._time_label.setText(f"Czas całkowity: {elapsed:.1f}s")
        elif pct > 0:
            mins, secs = divmod(int(remaining), 60)
            if mins:
                self._time_label.setText(f"Pozostało: ~{mins}m {secs:02d}s")
            else:
                self._time_label.setText(f"Pozostało: ~{secs}s")
        else:
            self._time_label.setText("Szacowanie…")

        self._log.appendPlainText(msg)
        self._log.moveCursor(self._log.textCursor().MoveOperation.End)

    def reset(self):
        self._progress.setValue(0)
        self._progress.setFormat("")
        self._time_label.setText("–")

    def log(self, msg: str):
        self._log.appendPlainText(msg)
        self._log.moveCursor(self._log.textCursor().MoveOperation.End)

    def clear_log(self):
        self._log.clear()


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("AstroStack")
        self.resize(1280, 820)

        self._stacked_img: np.ndarray | None = None
        self._displayed_img: np.ndarray | None = None
        self._worker: StackWorker | None = None

        self._build_menu()
        self._build_ui()

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

        tools_menu = mb.addMenu("Narzędzia")
        act_solve = QAction("🔭  Plate Solving…", self)
        act_solve.setToolTip("Identyfikuj pole gwiazd i wyznacz RA/Dec centrum kadru")
        act_solve.triggered.connect(self._open_plate_solve)
        tools_menu.addAction(act_solve)

        view_menu = mb.addMenu("View")
        act_fit = QAction("Fit image to window", self)
        act_fit.triggered.connect(lambda: self._preview.reset_zoom())
        view_menu.addAction(act_fit)

    def _build_ui(self):
        root_widget = QWidget()
        self.setCentralWidget(root_widget)
        root_layout = QVBoxLayout(root_widget)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # --- Main 3-panel area ---
        main_widget = QWidget()
        main_layout = QHBoxLayout(main_widget)
        main_layout.setContentsMargins(4, 4, 4, 4)
        main_layout.setSpacing(4)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left: frames + stack settings
        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(4)

        self._frames_panel = FramesPanel()
        left_layout.addWidget(self._frames_panel)

        self._stack_panel = StackPanel()
        self._stack_panel.stack_requested.connect(self._on_stack_requested)
        left_layout.addWidget(self._stack_panel)

        left.setMinimumWidth(240)
        left.setMaximumWidth(340)
        splitter.addWidget(left)

        # Center: preview
        self._preview = PreviewWidget()
        splitter.addWidget(self._preview)

        # Right: stretch only
        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(4, 4, 4, 4)

        self._stretch_panel = StretchPanel()
        self._stretch_panel.stretch_changed.connect(self._on_stretch_changed)
        right_layout.addWidget(self._stretch_panel)

        right.setMinimumWidth(260)
        right.setMaximumWidth(360)
        splitter.addWidget(right)

        splitter.setSizes([280, 680, 300])
        main_layout.addWidget(splitter)

        root_layout.addWidget(main_widget, stretch=1)

        # --- Bottom panel ---
        self._bottom = BottomPanel()
        root_layout.addWidget(self._bottom)
        self._bottom.log("Gotowy. Dodaj klatki Light i kliknij ▶ Stack.")

    # ------------------------------------------------------------------
    # Stacking
    # ------------------------------------------------------------------

    def _on_stack_requested(self, algorithm: str, sigma: float, iterations: int):
        paths = self._frames_panel.all_paths()
        if not paths.get("Lights"):
            QMessageBox.warning(self, "Brak Lights", "Dodaj klatki Light przed stackowaniem.")
            return

        from ui.prestack_dialog import PreStackDialog
        dlg = PreStackDialog(paths["Lights"], parent=self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return

        selected = dlg.selected_paths()
        if not selected:
            QMessageBox.warning(self, "Brak klatek", "Wszystkie klatki zostały odznaczone.")
            return

        paths["Lights"] = selected

        self._stack_panel.set_enabled(False)
        self._bottom.reset()
        self._bottom.clear_log()
        self._bottom.log(
            f"Rozpoczynanie stackowania ({algorithm}) — "
            f"{len(selected)} klatek, normalizacja: {dlg.normalization()}, "
            f"wątki: {dlg.n_threads()}"
        )

        self._worker = StackWorker(
            paths, algorithm, sigma, iterations,
            normalization=dlg.normalization(),
            n_threads=dlg.n_threads(),
        )
        self._worker.progress.connect(self._on_progress)
        self._worker.finished.connect(self._on_stack_finished)
        self._worker.error.connect(self._on_stack_error)
        self._worker.start()

    def _on_progress(self, pct: int, msg: str, elapsed: float, remaining: float):
        self._bottom.update_progress(pct, msg, elapsed, remaining)

    def _on_stack_finished(self, result: np.ndarray):
        self._stacked_img = result
        self._displayed_img = result.copy()
        self._stretch_panel.set_source(result)
        self._preview.update_image(result)
        self._stack_panel.set_enabled(True)
        h, w = result.shape[:2]
        ch = "RGB" if result.ndim == 3 else "Mono"
        self._bottom.log(f"Stack gotowy — {w}×{h}px, {ch}")
        self._bottom.log("Możesz teraz uruchomić Plate Solving z menu Narzędzia.")

    def _open_plate_solve(self):
        img = self._stacked_img if self._stacked_img is not None else self._displayed_img
        if img is None:
            QMessageBox.warning(self, "Brak obrazu",
                                "Najpierw wykonaj stackowanie, a następnie uruchom Plate Solving.")
            return
        from ui.platesolve_dialog import PlateSolveDialog
        dlg = PlateSolveDialog(img, parent=self)
        dlg.show()

    def _on_stack_error(self, msg: str):
        QMessageBox.critical(self, "Błąd stackowania", msg)
        self._stack_panel.set_enabled(True)
        self._bottom.log(f"BŁĄD: {msg}")

    # ------------------------------------------------------------------
    # Stretch
    # ------------------------------------------------------------------

    def _on_stretch_changed(self, img: np.ndarray):
        self._displayed_img = img
        self._preview.update_image(img)

    # ------------------------------------------------------------------
    # Export (menu)
    # ------------------------------------------------------------------

    def _export(self, fmt: str):
        if self._displayed_img is None:
            QMessageBox.warning(self, "Brak obrazu", "Najpierw wykonaj stackowanie.")
            return

        filters = {
            "tiff": "TIFF 16-bit (*.tif *.tiff)",
            "png":  "PNG image (*.png)",
            "jpeg": "JPEG image (*.jpg *.jpeg)",
        }
        default_ext = {"tiff": ".tif", "png": ".png", "jpeg": ".jpg"}

        path, _ = QFileDialog.getSaveFileName(
            self, "Eksport obrazu", f"wynik{default_ext[fmt]}", filters[fmt]
        )
        if not path:
            return

        from export.exporter import save_tiff16, save_png, save_jpeg
        try:
            if fmt == "tiff":
                save_tiff16(self._stacked_img or self._displayed_img, path)
            elif fmt == "png":
                save_png(self._displayed_img, path)
            else:
                save_jpeg(self._displayed_img, path)
            self._bottom.log(f"Zapisano: {Path(path).name}")
        except Exception as exc:
            QMessageBox.critical(self, "Błąd eksportu", str(exc))
