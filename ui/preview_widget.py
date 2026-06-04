"""Zoomable/pannable image preview widget."""

import numpy as np
from PyQt6.QtWidgets import QGraphicsView, QGraphicsScene, QGraphicsPixmapItem
from PyQt6.QtCore import Qt, QRectF
from PyQt6.QtGui import QPixmap, QImage, QWheelEvent, QMouseEvent


def ndarray_to_qimage(img: np.ndarray) -> QImage:
    """Convert float32 [0,1] array (H,W) or (H,W,3) to QImage RGB888."""
    data = (np.clip(img, 0, 1) * 255).astype(np.uint8)
    if data.ndim == 2:
        data = np.stack([data, data, data], axis=-1)
    h, w, _ = data.shape
    data = np.ascontiguousarray(data)
    return QImage(data.data, w, h, 3 * w, QImage.Format.Format_RGB888)


class PreviewWidget(QGraphicsView):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._scene = QGraphicsScene(self)
        self.setScene(self._scene)
        self._pixmap_item = QGraphicsPixmapItem()
        self._scene.addItem(self._pixmap_item)

        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter)
        self.setRenderHint(self.renderHints())
        self.setBackgroundBrush(Qt.GlobalColor.black)

        self._img_data: np.ndarray | None = None

    def update_image(self, img: np.ndarray | None) -> None:
        self._img_data = img
        if img is None:
            self._pixmap_item.setPixmap(QPixmap())
            return
        qimg = ndarray_to_qimage(img)
        pixmap = QPixmap.fromImage(qimg)
        self._pixmap_item.setPixmap(pixmap)
        self._scene.setSceneRect(QRectF(pixmap.rect()))
        self.fitInView(self._pixmap_item, Qt.AspectRatioMode.KeepAspectRatio)

    def wheelEvent(self, event: QWheelEvent) -> None:
        factor = 1.15 if event.angleDelta().y() > 0 else 1.0 / 1.15
        self.scale(factor, factor)

    def reset_zoom(self) -> None:
        if self._pixmap_item.pixmap().isNull():
            return
        self.fitInView(self._pixmap_item, Qt.AspectRatioMode.KeepAspectRatio)
