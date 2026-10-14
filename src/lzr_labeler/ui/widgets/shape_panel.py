from __future__ import annotations

from PySide6.QtWidgets import (
    QGroupBox,
    QVBoxLayout,
    QRadioButton,
)
from PySide6.QtCore import Qt, Signal

from lzr_labeler.theme import (
    current_mode,
    get_palette,
    groupbox_with_border_style,
    create_square_radio_style,
    radiobutton_style,
)
from lzr_labeler.theme.palette import ThemeMode


class ShapeBox(QGroupBox):
    """
    Shape selection panel using square radio indicators.
    """

    shapeChanged = Signal(str)

    def __init__(self, parent=None):
        super().__init__("Draw Shapes", parent)

        self._mode: ThemeMode = current_mode()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        self._radios: dict[str, QRadioButton] = {}

        entries = [
            ("rect", "Rectangle"),
            ("circle", "Circle"),
            ("poly", "Polygon"),
        ]

        self._radio_style = create_square_radio_style(
            widget=self,
            mode=self._mode,
        )

        for key, text in entries:
            rb = QRadioButton(text, self)
            rb.setCursor(Qt.PointingHandCursor)
            rb.setAttribute(Qt.WA_Hover, True)
            rb.setStyle(self._radio_style)

            rb.toggled.connect(
                lambda checked, m=key: checked and self.shapeChanged.emit(m)
            )

            layout.addWidget(rb)
            self._radios[key] = rb

        self.set_mode("rect")
        self.setCursor(Qt.PointingHandCursor)

        self._apply_styles(self._mode)

    # ------------------------------------------------------------------
    # Theme API
    # ------------------------------------------------------------------

    def set_theme_mode(self, mode: ThemeMode) -> None:
        self._mode = mode

        self._radio_style = create_square_radio_style(
            widget=self,
            mode=self._mode,
        )

        for rb in self._radios.values():
            rb.setStyle(self._radio_style)
            rb.update()

        self._apply_styles(self._mode)
        self.update()

    def _apply_styles(self, mode: ThemeMode) -> None:
        p = get_palette(mode)

        self.setStyleSheet(
            "\n".join([
                groupbox_with_border_style(p),
                radiobutton_style(p),
            ])
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def current_mode(self) -> str:
        for mode, rb in self._radios.items():
            if rb.isChecked():
                return mode
        return "rect"

    def set_mode(self, mode: str) -> None:
        rb = self._radios.get(mode)
        if not rb:
            return

        was_blocked = rb.blockSignals(True)
        rb.setChecked(True)
        rb.blockSignals(was_blocked)
