from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QLabel,
    QScrollArea,
    QMessageBox,
    QSlider,
)
from PySide6.QtGui import QPixmap, QImage, QWheelEvent
from PySide6.QtCore import Qt

from lzr_labeler.core.paths import resource_path

from lzr_labeler.theme import (
    current_mode,
    get_palette,
    generate_dialog_stylesheet,
    get_icon,
)


class PDFScrollArea(QScrollArea):

    def __init__(self, parent=None):
        super().__init__(parent)
        self._zoom_callback = None
        self._page_callback = None  # (direction: int) -> None  direction: +1 next, -1 prev

    def set_zoom_callback(self, cb):
        self._zoom_callback = cb

    def set_page_callback(self, cb):
        self._page_callback = cb

    def wheelEvent(self, event: QWheelEvent) -> None:
        # Zoom
        if event.modifiers() & Qt.ControlModifier:
            if self._zoom_callback:
                delta = event.angleDelta().y()
                self._zoom_callback(+0.1 if delta > 0 else -0.1)
                event.accept()
                return

        # Page navigation via scroll extremes
        vbar = self.verticalScrollBar()
        delta = event.angleDelta().y()

        at_top = vbar.value() <= vbar.minimum()
        at_bottom = vbar.value() >= vbar.maximum()

        if self._page_callback:
            if delta < 0 and at_bottom:
                self._page_callback(+1)  # next
                event.accept()
                return
            if delta > 0 and at_top:
                self._page_callback(-1)  # prev
                event.accept()
                return

        # Normal scroll
        super().wheelEvent(event)


class PDFViewerDialog(QDialog):
    """Dialog for displaying PDF files."""

    MIN_ZOOM = 0.25
    MAX_ZOOM = 4.0
    DEFAULT_ZOOM = 1.0

    def __init__(self, pdf_path: str | Path, parent=None, mode: str | None = None):
        super().__init__(parent)

        self._mode = mode or current_mode()
        self._palette = get_palette(self._mode)

        self._pdf_path = Path(pdf_path)
        self._current_page = 0
        self._total_pages = 0
        self._images: list[QImage] = []
        self._zoom_level = self.DEFAULT_ZOOM

        self._setup_ui()
        self._apply_theme()
        self._load_pdf()

    def _apply_theme(self) -> None:
        self.setStyleSheet(generate_dialog_stylesheet(self._palette))

    def _setup_ui(self) -> None:
        self.setWindowTitle("Help")
        self.setMinimumSize(1000, 800)
        self.resize(900, 700)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        # Scroll area
        self._scroll_area = PDFScrollArea()
        self._scroll_area.setWidgetResizable(True)
        self._scroll_area.setAlignment(Qt.AlignCenter)
        self._scroll_area.set_zoom_callback(self._adjust_zoom)
        self._scroll_area.set_page_callback(self._scroll_change_page)

        self._image_label = QLabel()
        self._image_label.setAlignment(Qt.AlignCenter)
        self._scroll_area.setWidget(self._image_label)

        layout.addWidget(self._scroll_area, stretch=1)

        # Control bar
        control_layout = QHBoxLayout()
        control_layout.setSpacing(10)

        # Navigation
        self._prev_btn = QPushButton(" Prev")
        self._prev_btn.setFixedWidth(80)
        self._prev_btn.clicked.connect(self._prev_page)
        self._prev_btn.setIcon(get_icon("prev", mode=self._mode))  # :contentReference[oaicite:0]{index=0}

        self._page_label = QLabel("Page 1 of 1")
        self._page_label.setAlignment(Qt.AlignCenter)
        self._page_label.setMinimumWidth(120)

        self._next_btn = QPushButton("Next ")
        self._next_btn.setFixedWidth(80)
        self._next_btn.clicked.connect(self._next_page)
        self._next_btn.setIcon(get_icon("next", mode=self._mode))  # :contentReference[oaicite:1]{index=1}

        # Zoom controls (بدون نمایش درصد)
        self._zoom_out_btn = QPushButton("−")
        self._zoom_out_btn.setFixedWidth(34)
        self._zoom_out_btn.clicked.connect(lambda: self._adjust_zoom(-0.25))

        self._zoom_slider = QSlider(Qt.Horizontal)
        self._zoom_slider.setMinimum(int(self.MIN_ZOOM * 100))
        self._zoom_slider.setMaximum(int(self.MAX_ZOOM * 100))
        self._zoom_slider.setValue(int(self.DEFAULT_ZOOM * 100))
        self._zoom_slider.setFixedWidth(160)
        self._zoom_slider.valueChanged.connect(self._on_zoom_slider_changed)

        self._zoom_in_btn = QPushButton("+")
        self._zoom_in_btn.setFixedWidth(34)
        self._zoom_in_btn.clicked.connect(lambda: self._adjust_zoom(0.25))

        self._fit_btn = QPushButton("Fit")
        self._fit_btn.setFixedWidth(60)
        self._fit_btn.clicked.connect(self._fit_to_window)
        self._fit_btn.setIcon(get_icon("zoom fit", mode=self._mode))  # :contentReference[oaicite:2]{index=2}

        control_layout.addWidget(self._prev_btn)
        control_layout.addWidget(self._page_label)
        control_layout.addWidget(self._next_btn)
        control_layout.addStretch()
        control_layout.addWidget(self._zoom_out_btn)
        control_layout.addWidget(self._zoom_slider)
        control_layout.addWidget(self._zoom_in_btn)
        control_layout.addWidget(self._fit_btn)

        layout.addLayout(control_layout)

    def _load_pdf(self) -> None:
        if not self._pdf_path.exists():
            self._image_label.setText(f"File not found:\n{self._pdf_path}")
            self._update_nav_state()
            return

        try:
            import fitz  # PyMuPDF

            doc = fitz.open(str(self._pdf_path))
            self._total_pages = len(doc)
            self._images = []

            for page_num in range(self._total_pages):
                page = doc[page_num]
                mat = fitz.Matrix(2.0, 2.0)
                pix = page.get_pixmap(matrix=mat)

                img = QImage(
                    pix.samples,
                    pix.width,
                    pix.height,
                    pix.stride,
                    QImage.Format_RGB888 if pix.n == 3 else QImage.Format_RGBA8888
                )
                self._images.append(img.copy())

            doc.close()

            if self._images:
                self._fit_to_window()
                self._show_page(0)
            else:
                self._image_label.setText("PDF is empty")

        except ImportError:
            self._image_label.setText(
                "PyMuPDF is required to display PDFs:\n\n"
                "pip install PyMuPDF"
            )
        except Exception as e:
            self._image_label.setText(f"Error opening PDF:\n{e}")

        self._update_nav_state()

    def _scroll_change_page(self, direction: int) -> None:
        # direction: +1 next, -1 prev
        if direction > 0:
            self._next_page()
        else:
            self._prev_page()

    def _show_page(self, page_num: int) -> None:
        if 0 <= page_num < len(self._images):
            self._current_page = page_num

            # وقتی صفحه عوض شد، اسکرول رو برگردون بالا
            self._scroll_area.verticalScrollBar().setValue(self._scroll_area.verticalScrollBar().minimum())

            self._update_display()
            self._update_nav_state()

    def _update_display(self) -> None:
        if not self._images or self._current_page >= len(self._images):
            return

        original = self._images[self._current_page]
        new_width = int(original.width() * self._zoom_level)
        new_height = int(original.height() * self._zoom_level)

        pixmap = QPixmap.fromImage(original)
        scaled = pixmap.scaled(
            new_width,
            new_height,
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation
        )
        self._image_label.setPixmap(scaled)

    def _adjust_zoom(self, delta: float) -> None:
        new_zoom = self._zoom_level + delta
        new_zoom = max(self.MIN_ZOOM, min(self.MAX_ZOOM, new_zoom))

        if new_zoom != self._zoom_level:
            self._zoom_level = new_zoom
            self._zoom_slider.blockSignals(True)
            self._zoom_slider.setValue(int(self._zoom_level * 100))
            self._zoom_slider.blockSignals(False)
            self._update_display()

    def _on_zoom_slider_changed(self, value: int) -> None:
        self._zoom_level = value / 100.0
        self._update_display()

    def _fit_to_window(self) -> None:
        if not self._images:
            return

        scroll_size = self._scroll_area.viewport().size()
        img = self._images[self._current_page]

        width_ratio = (scroll_size.width() - 30) / img.width()
        height_ratio = (scroll_size.height() - 30) / img.height()
        fit_zoom = min(width_ratio, height_ratio)
        fit_zoom = max(self.MIN_ZOOM, min(self.MAX_ZOOM, fit_zoom))

        self._zoom_level = fit_zoom
        self._zoom_slider.blockSignals(True)
        self._zoom_slider.setValue(int(self._zoom_level * 100))
        self._zoom_slider.blockSignals(False)
        self._update_display()

    def _prev_page(self) -> None:
        if self._current_page > 0:
            self._show_page(self._current_page - 1)

    def _next_page(self) -> None:
        if self._current_page < self._total_pages - 1:
            self._show_page(self._current_page + 1)

    def _update_nav_state(self) -> None:
        self._prev_btn.setEnabled(self._current_page > 0)
        self._next_btn.setEnabled(self._current_page < self._total_pages - 1)

        if self._total_pages > 0:
            self._page_label.setText(f"Page {self._current_page + 1} of {self._total_pages}")
        else:
            self._page_label.setText("No pages")

    def keyPressEvent(self, event) -> None:
        if event.key() in (Qt.Key_Plus, Qt.Key_Equal):
            self._adjust_zoom(0.25)
        elif event.key() == Qt.Key_Minus:
            self._adjust_zoom(-0.25)
        elif event.key() == Qt.Key_0:
            self._fit_to_window()
        elif event.key() == Qt.Key_Left:
            self._prev_page()
        elif event.key() == Qt.Key_Right:
            self._next_page()
        else:
            super().keyPressEvent(event)


def show_info_dialog(parent=None) -> None:
    """Display help dialog."""
    pdf_path = resource_path("assets/infos/DEU.pdf")

    if not Path(pdf_path).exists():
        QMessageBox.warning(
            parent,
            "File Not Found",
            f"Help file not found at:\n{pdf_path}"
        )
        return

    dialog = PDFViewerDialog(pdf_path, parent, mode=current_mode())
    dialog.exec()
