from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QImageReader, QImage
from pathlib import Path

class ImageLoaderWorker(QObject):
    finished = Signal(QImage, str)   
    error = Signal(str, str)        

    def __init__(self, path: str):
        super().__init__()
        self._path = path

    def run(self):
        try:
            p = Path(self._path)
            reader = QImageReader(str(p))
            reader.setAutoTransform(True)
            QImageReader.setAllocationLimit(0)
            image = reader.read()
            # print("READ:",
            # "isNull=", image.isNull(),
            # "size=", image.width(), image.height(),
            # "format=", image.format(),
            # "readerError=", reader.error(),
            # "readerErrorString=", reader.errorString())
            if image.isNull():
                self.error.emit(self._path, "Failed to load image")
                return
            self.finished.emit(image, self._path)
        except Exception as e:
            self.error.emit(self._path, str(e))
