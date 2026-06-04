"""Pre-stack dialog: frame review, normalization and performance options."""

import os
import multiprocessing
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict

import numpy as np

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTabWidget, QWidget,
    QTableWidget, QTableWidgetItem, QHeaderView, QLabel,
    QPushButton, QDoubleSpinBox, QSpinBox, QComboBox,
    QRadioButton, QButtonGroup, QCheckBox, QDialogButtonBox,
    QAbstractItemView, QProgressBar,
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QPixmap, QImage, QColor

from core.loader import load_image
from core.stretch import auto_stf


# ---------------------------------------------------------------------------
# Column indices
# ---------------------------------------------------------------------------
COL_CHECK  = 0
COL_THUMB  = 1
COL_NAME   = 2
COL_STARS  = 3
COL_FWHM   = 4
COL_SNR    = 5
COL_SIZE   = 6
COL_STATUS = 7
COL_RANK   = 8

THUMB_W, THUMB_H = 120, 80


# ---------------------------------------------------------------------------
# Frame loader (background thread)
# ---------------------------------------------------------------------------

class FrameLoader(QThread):
    """Loads thumbnails, computes star count, FWHM and SNR for each frame."""

    # row, thumb, n_stars, fwhm, snr, size_str
    frame_ready  = pyqtSignal(int, QPixmap, int, float, float, str)
    finished_all = pyqtSignal()

    def __init__(self, paths: List[str], n_threads: int = 4):
        super().__init__()
        self._paths     = paths
        self._n_threads = n_threads
        self._cancelled = False

    def cancel(self):
        self._cancelled = True

    def run(self):
        def process(args):
            idx, path = args
            if self._cancelled:
                return idx, None, 0, 0.0, 0.0, ""
            try:
                img      = load_image(path)
                stretched = auto_stf(img)
                thumb    = self._to_pixmap(stretched)
                size_mb  = os.path.getsize(path) / 1_048_576

                from core.stardetect import detect_stars
                result = detect_stars(img)

                return idx, thumb, result["n_stars"], result["median_fwhm"], result["snr"], f"{size_mb:.1f} MB"
            except Exception as e:
                return idx, None, 0, 0.0, 0.0, f"Błąd: {e}"

        with ThreadPoolExecutor(max_workers=self._n_threads) as ex:
            futures = {ex.submit(process, (i, p)): i
                       for i, p in enumerate(self._paths)}
            for fut in as_completed(futures):
                if self._cancelled:
                    break
                idx, thumb, n_stars, fwhm, snr, size_str = fut.result()
                if thumb is None:
                    thumb = self._placeholder()
                self.frame_ready.emit(idx, thumb, n_stars, fwhm, snr, size_str)

        self.finished_all.emit()

    def _to_pixmap(self, img: np.ndarray) -> QPixmap:
        data = (np.clip(img, 0, 1) * 255).astype(np.uint8)
        if data.ndim == 2:
            data = np.stack([data, data, data], axis=-1)
        h, w, _ = data.shape
        scale    = min(THUMB_W / w, THUMB_H / h)
        nw, nh   = int(w * scale), int(h * scale)
        from PIL import Image as PILImage
        pil      = PILImage.fromarray(data, "RGB").resize((nw, nh), PILImage.LANCZOS)
        data_s   = np.array(pil)
        qimg     = QImage(data_s.tobytes(), nw, nh, 3 * nw, QImage.Format.Format_RGB888)
        return QPixmap.fromImage(qimg)

    def _placeholder(self) -> QPixmap:
        px = QPixmap(THUMB_W, THUMB_H)
        px.fill(QColor("#333"))
        return px


# ---------------------------------------------------------------------------
# Frames tab
# ---------------------------------------------------------------------------

class FramesTab(QWidget):
    def __init__(self, paths: List[str], n_threads: int, parent=None):
        super().__init__(parent)
        self._paths      = paths
        self._snr_data:  Dict[int, float] = {}
        self._fwhm_data: Dict[int, float] = {}
        self._star_data: Dict[int, int]   = {}

        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)

        # --- Controls ---
        ctrl = QHBoxLayout()

        self._btn_all  = QPushButton("Zaznacz wszystkie")
        self._btn_none = QPushButton("Odznacz wszystkie")
        self._btn_auto = QPushButton("Auto-odrzuć słabe")
        self._btn_all.clicked.connect(self._select_all)
        self._btn_none.clicked.connect(self._deselect_all)
        self._btn_auto.clicked.connect(self._auto_reject)

        ctrl.addWidget(self._btn_all)
        ctrl.addWidget(self._btn_none)
        ctrl.addSpacing(12)

        # Rejection criterion
        ctrl.addWidget(QLabel("Kryterium:"))
        self._criterion = QComboBox()
        self._criterion.addItems(["SNR", "FWHM (ostrość)", "Gwiazdy"])
        self._criterion.setFixedWidth(130)
        ctrl.addWidget(self._criterion)

        ctrl.addWidget(QLabel("Próg:"))
        self._thresh = QDoubleSpinBox()
        self._thresh.setRange(0.1, 999.0)
        self._thresh.setValue(3.0)
        self._thresh.setSingleStep(0.5)
        self._thresh.setFixedWidth(75)
        ctrl.addWidget(self._thresh)
        ctrl.addWidget(self._btn_auto)
        ctrl.addStretch()

        self._selected_label = QLabel(f"Zaznaczono: {len(paths)}/{len(paths)}")
        self._selected_label.setStyleSheet("color: #aaa;")
        ctrl.addWidget(self._selected_label)
        layout.addLayout(ctrl)

        # Sort row
        sort_row = QHBoxLayout()
        sort_row.addWidget(QLabel("Sortuj po:"))
        self._sort_by = QComboBox()
        self._sort_by.addItems(["Nazwa", "Gwiazdy ↓", "FWHM ↑ (ostrzejsze)", "SNR ↓"])
        self._sort_by.currentIndexChanged.connect(self._sort_table)
        sort_row.addWidget(self._sort_by)
        sort_row.addStretch()
        layout.addLayout(sort_row)

        # Loading progress
        self._load_bar = QProgressBar()
        self._load_bar.setRange(0, len(paths))
        self._load_bar.setValue(0)
        self._load_bar.setFixedHeight(14)
        self._load_bar.setFormat("Wczytywanie i analiza klatek… %v/%m")
        self._load_bar.setStyleSheet("font-size: 10px;")
        layout.addWidget(self._load_bar)

        # Table
        self._table = QTableWidget(len(paths), 9)
        self._table.setHorizontalHeaderLabels(
            ["", "Podgląd", "Plik", "Gwiazdy", "FWHM\n[px]", "SNR", "Rozmiar", "Status", "Rank"]
        )
        self._table.verticalHeader().setVisible(False)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.setAlternatingRowColors(True)

        hdr = self._table.horizontalHeader()
        hdr.setSectionResizeMode(COL_CHECK,  QHeaderView.ResizeMode.Fixed)
        hdr.setSectionResizeMode(COL_THUMB,  QHeaderView.ResizeMode.Fixed)
        hdr.setSectionResizeMode(COL_NAME,   QHeaderView.ResizeMode.Stretch)
        for col in (COL_STARS, COL_FWHM, COL_SNR, COL_SIZE, COL_STATUS, COL_RANK):
            hdr.setSectionResizeMode(col, QHeaderView.ResizeMode.Fixed)

        self._table.setColumnWidth(COL_CHECK,  30)
        self._table.setColumnWidth(COL_THUMB,  THUMB_W + 8)
        self._table.setColumnWidth(COL_STARS,  72)
        self._table.setColumnWidth(COL_FWHM,   70)
        self._table.setColumnWidth(COL_SNR,    65)
        self._table.setColumnWidth(COL_SIZE,   75)
        self._table.setColumnWidth(COL_STATUS, 115)
        self._table.setColumnWidth(COL_RANK,   55)

        for row, path in enumerate(paths):
            self._table.setRowHeight(row, THUMB_H + 6)
            # Checkbox
            chk = QCheckBox()
            chk.setChecked(True)
            chk.stateChanged.connect(self._update_selected_label)
            chk_w = QWidget()
            chk_l = QHBoxLayout(chk_w)
            chk_l.addWidget(chk)
            chk_l.setAlignment(Qt.AlignmentFlag.AlignCenter)
            chk_l.setContentsMargins(0, 0, 0, 0)
            self._table.setCellWidget(row, COL_CHECK, chk_w)

            # Thumb placeholder
            lbl = QLabel("…")
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._table.setCellWidget(row, COL_THUMB, lbl)

            # Name
            name_item = QTableWidgetItem(os.path.basename(path))
            name_item.setToolTip(path)
            self._table.setItem(row, COL_NAME, name_item)

            for col in (COL_STARS, COL_FWHM, COL_SNR, COL_SIZE, COL_STATUS, COL_RANK):
                self._table.setItem(row, col, QTableWidgetItem("…"))

        layout.addWidget(self._table)

        # Start loader
        self._loader = FrameLoader(paths, n_threads)
        self._loader.frame_ready.connect(self._on_frame_ready)
        self._loader.finished_all.connect(self._on_all_loaded)
        self._loader.start()

    # ------------------------------------------------------------------

    def _on_frame_ready(self, row: int, thumb: QPixmap, n_stars: int,
                        fwhm: float, snr: float, size_str: str):
        # Thumbnail
        lbl = self._table.cellWidget(row, COL_THUMB)
        if lbl:
            lbl.setPixmap(thumb.scaled(
                THUMB_W, THUMB_H,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            ))
            lbl.setText("")

        self._star_data[row] = n_stars
        self._fwhm_data[row] = fwhm
        self._snr_data[row]  = snr

        def _center_item(text):
            it = QTableWidgetItem(text)
            it.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            return it

        self._table.setItem(row, COL_STARS, _center_item(str(n_stars) if n_stars else "–"))
        self._table.setItem(row, COL_FWHM,  _center_item(f"{fwhm:.2f}" if fwhm else "–"))
        self._table.setItem(row, COL_SNR,   _center_item(f"{snr:.2f}"))
        self._table.setItem(row, COL_SIZE,  _center_item(size_str))

        status_text, color = self._status(snr, fwhm, n_stars)
        status_item = _center_item(status_text)
        status_item.setForeground(QColor(color))
        self._table.setItem(row, COL_STATUS, status_item)

        self._load_bar.setValue(self._load_bar.value() + 1)
        self._update_ranks()

    def _on_all_loaded(self):
        self._load_bar.setFormat("Analiza zakończona ✓")
        self._load_bar.setValue(self._load_bar.maximum())
        self._update_ranks()

    def _status(self, snr: float, fwhm: float, n_stars: int):
        if snr < 2.0:
            return "⚠ Słaby sygnał", "#ff6b6b"
        if fwhm > 6.0:
            return "⚠ Rozmyte gwiazdy", "#ff9f43"
        if n_stars < 10:
            return "~ Mało gwiazd", "#ffd93d"
        if snr < 4.0:
            return "~ Przeciętny", "#ffd93d"
        return "✓ Dobry", "#6bcb77"

    def _update_ranks(self):
        """Rank frames: 1 = best. Composite score: higher SNR + lower FWHM + more stars."""
        if not self._snr_data:
            return
        rows = sorted(self._snr_data.keys())

        snrs  = np.array([self._snr_data.get(r, 0) for r in rows], dtype=float)
        fwhms = np.array([self._fwhm_data.get(r, 99) or 99 for r in rows], dtype=float)
        stars = np.array([self._star_data.get(r, 0) for r in rows], dtype=float)

        def norm(arr, higher_better=True):
            rng = arr.max() - arr.min()
            if rng == 0:
                return np.zeros_like(arr)
            n = (arr - arr.min()) / rng
            return n if higher_better else 1 - n

        score = 0.4 * norm(snrs) + 0.4 * norm(fwhms, False) + 0.2 * norm(stars)
        ranked = np.argsort(-score)  # highest score = rank 1

        rank_map = {row: rank + 1 for rank, row in enumerate(ranked)}
        for row in rows:
            rank = rank_map.get(row, "–")
            it = QTableWidgetItem(str(rank))
            it.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            if isinstance(rank, int) and rank <= 3:
                it.setForeground(QColor("#4fc3f7"))
            self._table.setItem(row, COL_RANK, it)

    def _sort_table(self, idx: int):
        col_map = {0: COL_NAME, 1: COL_STARS, 2: COL_FWHM, 3: COL_SNR}
        col = col_map.get(idx, COL_NAME)
        order = Qt.SortOrder.AscendingOrder if idx in (0, 2) else Qt.SortOrder.DescendingOrder
        self._table.sortItems(col, order)

    def _checkbox(self, row: int) -> QCheckBox | None:
        w = self._table.cellWidget(row, COL_CHECK)
        return w.findChild(QCheckBox) if w else None

    def _select_all(self):
        for r in range(self._table.rowCount()):
            chk = self._checkbox(r)
            if chk:
                chk.setChecked(True)

    def _deselect_all(self):
        for r in range(self._table.rowCount()):
            chk = self._checkbox(r)
            if chk:
                chk.setChecked(False)

    def _auto_reject(self):
        criterion = self._criterion.currentIndex()
        thresh    = self._thresh.value()
        for r in range(self._table.rowCount()):
            chk = self._checkbox(r)
            if not chk:
                continue
            if criterion == 0:    # SNR >=
                keep = self._snr_data.get(r, 0) >= thresh
            elif criterion == 1:  # FWHM <= thresh (lower = sharper = keep)
                fwhm = self._fwhm_data.get(r, 0)
                keep = (fwhm <= thresh) if fwhm > 0 else True
            else:                 # Stars >=
                keep = self._star_data.get(r, 0) >= int(thresh)
            chk.setChecked(keep)

    def _update_selected_label(self):
        total    = self._table.rowCount()
        selected = sum(1 for r in range(total) if (c := self._checkbox(r)) and c.isChecked())
        self._selected_label.setText(f"Zaznaczono: {selected}/{total}")

    def selected_paths(self) -> List[str]:
        result = []
        for row in range(self._table.rowCount()):
            chk = self._checkbox(row)
            if chk and chk.isChecked():
                # Reconstruct path from original list via name match
                name = self._table.item(row, COL_NAME)
                if name:
                    # Find original path
                    basename = name.text()
                    for p in self._paths:
                        if os.path.basename(p) == basename:
                            result.append(p)
                            break
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
        for r in (self._none, self._med, self._first):
            grp.addButton(r)
            layout.addWidget(r)

        layout.addStretch()
        layout.addWidget(QLabel(
            "<span style='color:#888; font-size:11px;'>"
            "⚠ Normalizacja może nieznacznie zmienić poziom szumu.<br>"
            "Zalecana gdy różnica jasności między klatkami jest widoczna."
            "</span>"
        ))

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
        self._low_ram = QCheckBox("Tryb oszczędny RAM")
        layout.addWidget(self._low_ram)
        layout.addWidget(QLabel(
            "<span style='color:#888; font-size:11px;'>"
            "Tryb oszczędny: klatki nie są trzymane razem w RAM.<br>"
            "Uwaga: nie obsługuje Sigma/Kappa-Sigma."
            "</span>"
        ))

        layout.addStretch()
        self._ram_label = QLabel("")
        self._ram_label.setStyleSheet("color: #4fc3f7; font-size: 12px;")
        layout.addWidget(self._ram_label)

    def n_threads(self) -> int:
        return self._threads.value()

    def low_ram(self) -> bool:
        return self._low_ram.isChecked()


# ---------------------------------------------------------------------------
# Main PreStackDialog
# ---------------------------------------------------------------------------

class PreStackDialog(QDialog):
    def __init__(self, paths: List[str], parent=None):
        super().__init__(parent)
        self.setWindowTitle("Opcje stackowania")
        self.resize(980, 660)
        self.setWindowFlags(
            Qt.WindowType.Window |
            Qt.WindowType.WindowCloseButtonHint
        )

        layout = QVBoxLayout(self)

        summary = QLabel(
            f"<b>{len(paths)} klatek Light</b> — analiza gwiazd i rankowanie w toku. "
            "Odznacz słabe klatki, ustaw normalizację i opcje wydajności."
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
