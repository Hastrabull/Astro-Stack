"""AstroStack — entry point."""

import sys
from pathlib import Path

# Ensure project root is on sys.path when running as script or frozen exe
sys.path.insert(0, str(Path(__file__).parent))

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPalette, QColor

from ui.main_window import MainWindow


def apply_dark_palette(app: QApplication) -> None:
    app.setStyle("Fusion")
    palette = QPalette()
    dark = QColor(45, 45, 48)
    mid = QColor(63, 63, 70)
    light_text = QColor(220, 220, 220)
    highlight = QColor(0, 120, 215)
    base = QColor(30, 30, 30)

    palette.setColor(QPalette.ColorRole.Window, dark)
    palette.setColor(QPalette.ColorRole.WindowText, light_text)
    palette.setColor(QPalette.ColorRole.Base, base)
    palette.setColor(QPalette.ColorRole.AlternateBase, mid)
    palette.setColor(QPalette.ColorRole.ToolTipBase, dark)
    palette.setColor(QPalette.ColorRole.ToolTipText, light_text)
    palette.setColor(QPalette.ColorRole.Text, light_text)
    palette.setColor(QPalette.ColorRole.Button, dark)
    palette.setColor(QPalette.ColorRole.ButtonText, light_text)
    palette.setColor(QPalette.ColorRole.BrightText, Qt.GlobalColor.white)
    palette.setColor(QPalette.ColorRole.Link, highlight)
    palette.setColor(QPalette.ColorRole.Highlight, highlight)
    palette.setColor(QPalette.ColorRole.HighlightedText, Qt.GlobalColor.white)
    app.setPalette(palette)


def main() -> None:
    app = QApplication(sys.argv)
    app.setApplicationName("AstroStack")
    apply_dark_palette(app)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
