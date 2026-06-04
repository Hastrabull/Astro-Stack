"""Pre-stack dialog: frame review, normalization and performance options."""

import os
import multiprocessing
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict

import numpy as np

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTabWidget, QWidget,
    QTableWidget, QTableWidgetItem, QHeaderView, QLabel,
    QPushButton, QSlider, QDoubleSpinBox, QSpinBox,
    QRadioButton, QButtonGroup, QCheckBox, QDialogButtonBox,
    QAbstractItemView, QSizePolicy, QProgressBar,
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QSize
from PyQt6.QtGui import QPixmap, QImage, QColor, QFont

from core.loader import load_image
from core.stretch import auto_stf


# ---------------------------------------------------------------------------
# Thumbnail + SNR loader (background thread)
# ---------------------------------------------------------------------------

class FrameLoader(QThread):
    """Loads thumbnails and computes SNR for each light frame."""
    frame_ready = pyqtSignal(int, QPixmap, float, str)  # row, thumb, snr, info
    finished_all = pyqtSignal()

    THUMB_W, THUMB_H = 120, 80

    def __init__(self, paths: List[str], n_threads: int = 4):
        super().__init__()
        self._paths = paths
        self._n_threads = n_threads
        self._cancelled = False

    def cancel(self):
        self._cancelled = True

    def run(self):
        def process(args):
            idx, path = args
            if self._cancelled:
                return idx, None, 0.0, ""
            try:
                img = load_image(path)
                snr = float(np.mean(img)) / (float(np.std(img)) + 1e-9)
                stretched = auto_stf(img)
                thumb = self._to_pixmap(stretched)
                size_mb = os.path.getsize(path) / 1_048_576
                info = f"{size_mb:.1f} MB"
                return idx, thumb, round(snr, 2), info
            except Exception as e:
                return idx, None, 0.0, f"Błąd: {e}"

        with ThreadPoolExecutor(max_workers=self._n_threads) as ex:
            futures = {ex.submit(process, (i, p)): i
                       for i, p in enumerate(self._paths)}
            for fut in as_completed(futures):
                if self._cancelled:
                    break
                idx, thumb, snr, info = fut.result()
                if thumb is None:
                    thumb = self._placeholder()
                self.frame_ready.emit(idx, thumb, snr, info)

        self.finished_all.emit()

    def _to_pixmap(self, img: np.ndarray) -> QPixmap:
        data = (np.clip(img, 0, 1) * 255).astype(np.uint8)
        if data.ndim == 2:
            data = np.stack([data, data, data], axis=-1)
        h, w, _ = data.shape
        # Scale down to thumbnail size
        scale = min(self.THUMB_W / w, self.THUMB_H / h)
        nw, nh = int(w * scale), int(h * scale)
        # Simple box downsample
        from PIL import Image as PILImage
        pil = PILImage.fromarray(data, "RGB").resize((nw, nh), PILImage.LANCZOS)
        data_small = np.array(pil)
        qimg = QImage(data_small.tobytes(), nw, nh, 3 * nw, QImage.Format.Format_RGB888)
        return QPixmap.fromImage(qimg)

    def _placeholder(self) -> QPixmap:
        px = QPixmap(self.THUMB_W, self.THUMB_H)
        px.fill(QColor("#333"))
        return px


# ---------------------------------------------------------------------------
# Frames tab
# ---------------------------------------------------------------------------

COL_CHECK  = 0
COL_THUMB  = 1
COL_NAME   = 2
COL_SNR    = 3
COL_SIZE   = 4
COL_STATUS = 5


class FramesTab(QWidget):
    def __init__(self, paths: List[str], n_threads: int, parent=None):
        super().__init__(parent)
        self._paths = paths
        self._snr_values: Dict[int, float] = {}

        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)

        # --- Controls row ---
        ctrl = QHBoxLayout()

        self._btn_all    = QPushButton("Zaznacz wszystkie")
        self._btn_none   = QPushButton("Odznacz wszystkie")
        self._btn_auto   = QPushButton("Auto-odrzuć słabe")
        self._lbl_snr    = QLabel("Próg SNR:")
        self._snr_thresh = QDoubleSpinBox()
        self._snr_thresh.setRange(0.1, 50.0)
        self._snr_thresh.setValue(3.0)
        self._snr_thresh.setSingleStep(0.5)
        self._snr_thresh.setFixedWidth(70)

        self._btn_all.clicked.connect(self._select_all)
        self._btn_none.clicked.connect(self._deselect_all)
        self._btn_auto.clicked.connect(self._auto_reject)

        ctrl.addWidget(self._btn_all)
        ctrl.addWidget(self._btn_none)
        ctrl.addSpacing(16)
        ctrl.addWidget(self._lbl_snr)
        ctrl.addWidget(self._snr_thresh)
        ctrl.addWidget(self._btn_auto)
        ctrl.addStretch()

        self._selected_label = QLabel(f"Zaznaczono: {len(paths)}/{len(paths)}")
        self._selected_label.setStyleSheet("color: #aaa;")
        ctrl.addWidget(self._selected_label)
        layout.addLayout(ctrl)

        # --- Loading progress ---
        self._load_bar = QProgressBar()
        self._load_bar.setRange(0, len(paths))
        self._load_bar.setValue(0)
        self._load_bar.setFixedHeight(14)
        self._load_bar.setFormat("Wczytywanie miniaturek… %v/%m")
        self._load_bar.setStyleSheet("font-size: 10px;")
        layout.addWidget(self._load_bar)

        # --- Table ---
        self._table = QTableWidget(len(paths), 6)
        self._table.setHorizontalHeaderLabels(
            ["", "Podgląd", "Plik", "SNR", "Rozmiar", "Status"]
        )
        self._table.verticalHeader().setVisible(False)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.setAlternatingRowColors(True)
        self._table.setRowHeight(0, self.THUMB_H + 6)

        hdr = self._table.horizontalHeader()
        hdr.setSectionResizeMode(COL_CHECK,  QHeaderView.ResizeMode.Fixed)
        hdr.setSectionResizeMode(COL_THUMB,  QHeaderView.ResizeMode.Fixed)
        hdr.setSectionResizeMode(COL_NAME,   QHeaderView.ResizeMode.Stretch)
        hdr.setSectionResizeMode(COL_SNR,    QHeaderView.ResizeMode.Fixed)
        hdr.setSectionResizeMode(COL_SIZE,   QHeaderView.ResizeMode.Fixed)
        hdr.setSectionResizeMode(COL_STATUS, QHeaderView.ResizeMode.Fixed)

        self._table.setColumnWidth(COL_CHECK,  30)
        self._table.setColumnWidth(COL_THUMB,  self.THUMB_W + 8)
        self._table.setColumnWidth(COL_SNR,    70)
        self._table.setColumnWidth(COL_SIZE,   75)
        self._table.setColumnWidth(COL_STATUS, 110)

        for row, path in enumerate(paths):
            self._table.setRowHeight(row, self.THUMB_H + 6)
            # Checkbox
            chk = QCheckBox()
            chk.setChecked(True)
            chk.stateChanged.connect(self._update_selected_label)
            chk_widget = QWidget()
            chk_layout = QHBoxLayout(chk_widget)
            chk_layout.addWidget(chk)
            chk_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
            chk_layout.setContentsMargins(0, 0, 0, 0)
            self._table.setCellWidget(row, COL_CHECK, chk_widget)

            # Thumb placeholder
            lbl = QLabel()
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setFixedSize(self.THUMB_W + 4, self.THUMB_H + 4)
            lbl.setText("…")
            self._table.setCellWidget(row, COL_THUMB, lbl)

            # Name
            name_item = QTableWidgetItem(os.path.basename(path))
            name_item.setToolTip(path)
            self._table.setItem(row, COL_NAME, name_item)

            # SNR placeholder
            self._table.setItem(row, COL_SNR, QTableWidgetItem("…"))
            self._table.setItem(row, COL_SIZE, QTableWidgetItem("…"))
            self._table.setItem(row, COL_STATUS, QTableWidgetItem("Wczytywanie…"))

        layout.addWidget(self._table)

        # Start loader
        self._loader = FrameLoader(paths, n_threads)
        self._loader.frame_ready.connect(self._on_frame_ready)
        self._loader.finished_all.connect(self._on_all_loaded)
        self._loader.start()

    THUMB_W = FrameLoader.THUMB_W
    THUMB_H = FrameLoader.THUMB_H

    def _on_frame_ready(self, row: int, thumb: QPixmap, snr: float, info: str):
        # Thumbnail
        lbl = self._table.cellWidget(row, COL_THUMB)
        if lbl:
            lbl.setPixmap(thumb.scaled(
                self.THUMB_W, self.THUMB_H,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            ))
            lbl.setText("")

        # SNR
        self._snr_values[row] = snr
        snr_item = QTableWidgetItem(f"{snr:.2f}")
        snr_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        self._table.setItem(row, COL_SNR, snr_item)

        # Size
        size_item = QTableWidgetItem(info)
        size_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        self._table.setItem(row, COL_SIZE, size_item)

        # Status
        status = self._status_text(snr)
        status_item = QTableWidgetItem(status)
        status_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        if snr < 2.0:
            status_item.setForeground(QColor("#ff6b6b"))
        elif snr < 4.0:
            status_item.setForeground(QColor("#ffd93d"))
        else:
            status_item.setForeground(QColor("#6bcb77"))
        self._table.setItem(row, COL_STATUS, status_item)

        self._load_bar.setValue(self._load_bar.value() + 1)

    def _on_all_loaded(self):
        self._load_bar.setFormat("Gotowe")
        self._load_bar.setValue(self._load_bar.maximum())

    def _status_text(self, snr: float) -> str:
        if snr < 2.0:
            return "⚠ Słaby sygnał"
        if snr < 4.0:
            return "~ Przeciętny"
        return "✓ Dobry"

    def _checkbox(self, row: int) -> QCheckBox | None:
        w = self._table.cellWidget(row, COL_CHECK)
        if w:
            return w.findChild(QCheckBox)
        return None

    def _select_all(self):
        for row in range(self._table.rowCount()):
            chk = self._checkbox(row)
            if chk:
                chk.setChecked(True)

    def _deselect_all(self):
        for row in range(self._table.rowCount()):
            chk = self._checkbox(row)
            if chk:
                chk.setChecked(False)

    def _auto_reject(self):
        thresh = self._snr_thresh.value()
        for row in range(self._table.rowCount()):
            snr = self._snr_values.get(row, 999.0)
            chk = self._checkbox(row)
            if chk:
                chk.setChecked(snr >= thresh)

    def _update_selected_label(self):
        total    = self._table.rowCount()
        selected = sum(
            1 for r in range(total)
            if (chk := self._checkbox(r)) and chk.isChecked()
        )
        self._selected_label.setText(f"Zaznaczono: {selected}/{total}")

    def selected_paths(self) -> List[str]:
        result = []
        for row in range(self._table.rowCount()):
            chk = self._checkbox(row)
            if chk and chk.isChecked():
                result.append(self._paths[row])
        return result

    def stop_loader(self):
        if hasattr(self, "_loader"):
            self._loader.cancel()
            self._loader.wait(2000)


# ---------------------------------------------------------------------------
# Normalization tab
# ---------------------------------------------------------------------------

class NormalizationTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(16)

        layout.addWidget(QLabel(
            "<b>Normalizacja klatek</b><br>"
            "<span style='color:#aaa; font-size:12px;'>"
            "Wyrównuje jasność klatek przed stackowaniem.<br>"
            "Przydatna gdy sesja była długa lub warunki się zmieniały.</span>"
        ))

        self._none  = QRadioButton("Brak normalizacji  (domyślne)")
        self._med   = QRadioButton("Normalizacja do mediany  — wyrównuje jasność wszystkich klatek do wspólnego poziomu")
        self._first = QRadioButton("Normalizacja do pierwszej klatki  — pozostałe klatki dopasowują się do klatki #1")

        self._none.setChecked(True)

        grp = QButtonGroup(self)
        grp.addButton(self._none)
        grp.addButton(self._med)
        grp.addButton(self._first)

        layout.addWidget(self._none)
        layout.addWidget(self._med)
        layout.addWidget(self._first)
        layout.addStretch()

        tip = QLabel(
            "<span style='color:#888; font-size:11px;'>"
            "⚠ Normalizacja może nieznacznie zmienić poziom szumu.<br>"
            "Zalecana gdy różnica jasności między klatkami jest widoczna."
            "</span>"
        )
        layout.addWidget(tip)

    def mode(self) -> str:
        if self._med.isChecked():
            return "median"
        if self._first.isChecked():
            return "first"
        return "none"


# ---------------------------------------------------------------------------
# Performance tab
# ---------------------------------------------------------------------------

class PerformanceTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(16)

        layout.addWidget(QLabel("<b>Opcje wydajności</b>"))

        cpu_count = multiprocessing.cpu_count()

        # Threads
        thread_row = QHBoxLayout()
        thread_lbl = QLabel("Wątki ładowania plików:")
        thread_lbl.setFixedWidth(200)
        self._threads = QSpinBox()
        self._threads.setRange(1, min(cpu_count, 16))
        self._threads.setValue(min(4, cpu_count))
        self._threads.setFixedWidth(60)
        thread_tip = QLabel(f"(maks. {cpu_count} rdzeni)")
        thread_tip.setStyleSheet("color: #888; font-size: 11px;")
        thread_row.addWidget(thread_lbl)
        thread_row.addWidget(self._threads)
        thread_row.addWidget(thread_tip)
        thread_row.addStretch()
        layout.addLayout(thread_row)

        layout.addWidget(QLabel(
            "<span style='color:#888; font-size:11px;'>"
            "Więcej wątków = szybsze wczytywanie plików z SSD.<br>"
            "Na HDD optymalnie 1–2 wątki."
            "</span>"
        ))

        layout.addSpacing(8)

        # Low RAM mode
        self._low_ram = QCheckBox("Tryb oszczędny RAM")
        self._low_ram.setToolTip(
            "Klatki są przetwarzane sekwencyjnie — mniejsze zużycie pamięci,\n"
            "ale wolniejsze. Przydatne przy >50 klatkach lub małej ilości RAM."
        )
        layout.addWidget(self._low_ram)
        layout.addWidget(QLabel(
            "<span style='color:#888; font-size:11px;'>"
            "Tryb oszczędny: klatki nie są trzymane razem w RAM.<br>"
            "Uwaga: nie obsługuje Sigma/Kappa-Sigma (wymaga całego stosu naraz)."
            "</span>"
        ))

        layout.addStretch()

        # RAM estimate
        self._ram_label = QLabel("")
        self._ram_label.setStyleSheet("color: #4fc3f7; font-size: 12px;")
        layout.addWidget(self._ram_label)

    def n_threads(self) -> int:
        return self._threads.value()

    def low_ram(self) -> bool:
        return self._low_ram.isChecked()

    def update_ram_estimate(self, n_frames: int, shape: tuple | None):
        if shape is None:
            return
        h, w = shape[0], shape[1]
        ch = shape[2] if len(shape) == 3 else 1
        mb_per_frame = h * w * ch * 4 / 1_048_576
        total_mb = mb_per_frame * n_frames
        if total_mb > 1024:
            self._ram_label.setText(f"Szacowane zużycie RAM: ~{total_mb/1024:.1f} GB")
        else:
            self._ram_label.setText(f"Szacowane zużycie RAM: ~{total_mb:.0f} MB")


# ---------------------------------------------------------------------------
# Main PreStackDialog
# ---------------------------------------------------------------------------

class PreStackDialog(QDialog):
    def __init__(self, paths: List[str], parent=None):
        super().__init__(parent)
        self.setWindowTitle("Opcje stackowania")
        self.resize(900, 620)
        self.setWindowFlags(
            Qt.WindowType.Window |
            Qt.WindowType.WindowCloseButtonHint
        )

        layout = QVBoxLayout(self)

        summary = QLabel(
            f"<b>{len(paths)} klatek Light</b> gotowych do stackowania. "
            "Przejrzyj klatki, ustaw normalizację i opcje wydajności."
        )
        summary.setStyleSheet("padding: 4px 0; color: #ddd;")
        layout.addWidget(summary)

        self._tabs = QTabWidget()

        self._perf_tab  = PerformanceTab()
        self._frame_tab = FramesTab(paths, self._perf_tab.n_threads())
        self._norm_tab  = NormalizationTab()

        self._tabs.addTab(self._frame_tab, f"Klatki ({len(paths)})")
        self._tabs.addTab(self._norm_tab,  "Normalizacja")
        self._tabs.addTab(self._perf_tab,  "Wydajność")

        layout.addWidget(self._tabs)

        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok |
            QDialogButtonBox.StandardButton.Cancel
        )
        btns.button(QDialogButtonBox.StandardButton.Ok).setText("▶  Rozpocznij stackowanie")
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def selected_paths(self) -> List[str]:
        return self._frame_tab.selected_paths()

    def normalization(self) -> str:
        return self._norm_tab.mode()

    def n_threads(self) -> int:
        return self._perf_tab.n_threads()

    def low_ram(self) -> bool:
        return self._perf_tab.low_ram()

    def reject(self):
        self._frame_tab.stop_loader()
        super().reject()

    def accept(self):
        self._frame_tab.stop_loader()
        super().accept()

    def closeEvent(self, event):
        self._frame_tab.stop_loader()
        super().closeEvent(event)
