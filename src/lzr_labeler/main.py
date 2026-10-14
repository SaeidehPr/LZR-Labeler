import sys
import argparse
import logging
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QFontDatabase
from PySide6.QtCore import qInstallMessageHandler, Qt
from pathlib import Path

from lzr_labeler.ui.main_window import MainWindow
from lzr_labeler.core.paths import resource_path

from lzr_labeler.theme import apply_theme


def qt_message_handler(mode, context, message):
    if message.startswith("QPainter::begin: Paint device returned engine == 0") \
       or message.startswith("QPainter::setCompositionMode: Painter not active") \
       or message.startswith("QPainter::fillRect: Painter not active") \
       or message.startswith("QPainter::end: Painter not active"):
        return
    print(message)


def main():
    parser = argparse.ArgumentParser(description="LZR image annotation")
    parser.add_argument("--preset", choices=["general", "pcb"], default="general")
    parser.add_argument("--models-dir", type=Path, help="Folder containing a .pth model and meta_info.json")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    qInstallMessageHandler(qt_message_handler)

    # Important: set high-dpi behavior early (optional but recommended)
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    app = QApplication(sys.argv)
    apply_theme(app, "light", assets_dir=Path(resource_path("")))

    # Fonts
    QFontDatabase.addApplicationFont(resource_path(r"assets/fonts/Inter.ttf"))
    QFontDatabase.addApplicationFont(resource_path(r"assets/fonts/Rubik.ttf"))

    window = MainWindow(preset=args.preset, models_dir=args.models_dir)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
