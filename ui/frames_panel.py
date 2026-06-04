"""Panel for managing Light / Dark / Bias / Flat frame lists."""

from pathlib import Path
from typing import Dict, List

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTabWidget, QListWidget,
    QPushButton, QFileDialog, QLabel, QAbstractItemView,
)
from PyQt6.QtCore import pyqtSignal, Qt


FRAME_TYPES = ["Lights", "Darks", "Bias", "Flats"]

SUPPORTED_FILTER = (
    "Astro images (*.fit *.fits *.fts *.cr3 *.cr2 *.nef *.arw *.dng *.raf *.orf *.rw2);;"
    "All files (*.*)"
)


class FrameList(QWidget):
    """Single frame-type list with Add/Remove buttons and count label."""

    changed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)

        self._list = QListWidget()
        self._list.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self._list.setAcceptDrops(True)
        self._list.setDragDropMode(QAbstractItemView.DragDropMode.DropOnly)
        layout.addWidget(self._list)

        self._count_label = QLabel("0 files")
        layout.addWidget(self._count_label)

        btn_row = QHBoxLayout()
        self._btn_add = QPushButton("+ Add")
        self._btn_remove = QPushButton("− Remove")
        self._btn_clear = QPushButton("Clear")
        btn_row.addWidget(self._btn_add)
        btn_row.addWidget(self._btn_remove)
        btn_row.addWidget(self._btn_clear)
        layout.addLayout(btn_row)

        self._btn_add.clicked.connect(self._add_files)
        self._btn_remove.clicked.connect(self._remove_selected)
        self._btn_clear.clicked.connect(self._clear)

    def _add_files(self):
        paths, _ = QFileDialog.getOpenFileNames(
            self, "Select frames", "", SUPPORTED_FILTER
        )
        for p in paths:
            self._add_path(p)
        self._update_count()
        self.changed.emit()

    def _add_path(self, path: str):
        existing = {self._list.item(i).text() for i in range(self._list.count())}
        if path not in existing:
            self._list.addItem(path)

    def _remove_selected(self):
        for item in self._list.selectedItems():
            self._list.takeItem(self._list.row(item))
        self._update_count()
        self.changed.emit()

    def _clear(self):
        self._list.clear()
        self._update_count()
        self.changed.emit()

    def _update_count(self):
        n = self._list.count()
        self._count_label.setText(f"{n} file{'s' if n != 1 else ''}")

    def paths(self) -> List[str]:
        return [self._list.item(i).text() for i in range(self._list.count())]

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event):
        for url in event.mimeData().urls():
            self._add_path(url.toLocalFile())
        self._update_count()
        self.changed.emit()


class FramesPanel(QWidget):
    """Tabbed panel containing one FrameList per frame type."""

    changed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._tabs = QTabWidget()
        self._lists: Dict[str, FrameList] = {}

        for ft in FRAME_TYPES:
            fl = FrameList()
            fl.changed.connect(self.changed)
            self._lists[ft] = fl
            self._tabs.addTab(fl, ft)

        layout.addWidget(self._tabs)

    def paths(self, frame_type: str) -> List[str]:
        return self._lists[frame_type].paths()

    def all_paths(self) -> Dict[str, List[str]]:
        return {ft: self._lists[ft].paths() for ft in FRAME_TYPES}
