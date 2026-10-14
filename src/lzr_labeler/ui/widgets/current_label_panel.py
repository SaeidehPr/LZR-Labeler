from __future__ import annotations

from typing import Dict, Tuple

from PySide6.QtWidgets import (
    QGroupBox,
    QVBoxLayout,
    QListWidget,
    QListWidgetItem,
    QWidget,
    QHBoxLayout,
    QLabel,
    QFrame,
)
from PySide6.QtCore import Qt, Signal, QSize

from lzr_labeler.theme import (
    current_mode,
    get_palette,
    groupbox_with_border_style,
    listwidget_style,
    label_secondary_style,
    scrollbar_style,
)
from lzr_labeler.theme.palette import ThemeMode


class _LabelRow(QWidget):
    def __init__(
        self,
        name: str,
        color: str,
        count: int,
        *,
        row_height: int = 22,
        spacing: int = 8,
        margins=(6, 2, 6, 2),
        swatch_size: int = 12,
        count_width: int = 36,
        parent=None,
    ):
        super().__init__(parent)

        # QSS hooks
        self.setObjectName("labelRow")

        # Ensure selection background shows through
        self.setAttribute(Qt.WA_StyledBackground, False)
        self.setStyleSheet("QWidget#labelRow { background: transparent; }")

        self.setFixedHeight(row_height)

        lay = QHBoxLayout(self)
        lay.setContentsMargins(*margins)
        lay.setSpacing(spacing)

        # Color swatch (opaque by design)
        self.swatch = QFrame(self)
        self.swatch.setObjectName("labelSwatch")
        self.swatch.setFixedSize(QSize(swatch_size, swatch_size))
        self.set_swatch_color(color)

        # Name label (transparent background)
        self.name_lbl = QLabel(name, self)
        self.name_lbl.setObjectName("labelName")
        self.name_lbl.setTextInteractionFlags(Qt.NoTextInteraction)
        self.name_lbl.setAlignment(Qt.AlignVCenter | Qt.AlignLeft)
        self.name_lbl.setStyleSheet("QLabel#labelName { background: transparent; }")

        # Count label (transparent background)
        self.count_lbl = QLabel(str(count), self)
        self.count_lbl.setObjectName("labelCount")
        self.count_lbl.setAlignment(Qt.AlignVCenter | Qt.AlignRight)
        self.count_lbl.setFixedWidth(count_width)
        self.count_lbl.setStyleSheet("QLabel#labelCount { background: transparent; }")

        lay.addWidget(self.swatch, 0, Qt.AlignVCenter)
        lay.addWidget(self.name_lbl, 1, Qt.AlignVCenter)
        lay.addWidget(self.count_lbl, 0, Qt.AlignVCenter)

    def set_swatch_color(self, color: str) -> None:
        # Keep swatch opaque and simple
        self.swatch.setStyleSheet(
            f"QFrame#labelSwatch {{ background: {color}; border: none; border-radius: 0px; }}"
        )


class CurrentLabelBox(QGroupBox):
    labelClicked = Signal(str)

    def __init__(self, parent=None):
        super().__init__("Current Labels", parent)

        self._mode: ThemeMode = current_mode()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 8, 6, 6)

        self.list = QListWidget(self)
        self.list.setSelectionMode(QListWidget.SingleSelection)
        self.list.itemClicked.connect(self._on_item_clicked)
        self.list.setUniformItemSizes(True)
        layout.addWidget(self.list)

        self.row_height = 22
        self.spacing = 8
        self.margins = (6, 2, 6, 2)
        self.swatch_size = 12
        self.count_width = 36

        self._apply_styles(self._mode)

    # ---------------------------
    # Theme API
    # ---------------------------

    def set_theme_mode(self, mode: ThemeMode) -> None:
        self._mode = mode
        self._apply_styles(mode)
        self.update()

        # Re-apply row label styles for existing item widgets
        for i in range(self.list.count()):
            it = self.list.item(i)
            w = self.list.itemWidget(it)
            if isinstance(w, _LabelRow):
                w.update()

    def _apply_styles(self, mode: ThemeMode) -> None:
        p = get_palette(mode)

        self.setStyleSheet("\n".join([
            groupbox_with_border_style(p),
            listwidget_style(p),
            scrollbar_style(p, selector="QListWidget QScrollBar"),

            # Style row text labels inside item widgets
            label_secondary_style(p, selector="QLabel"),
            # Make counts slightly more prominent
            label_secondary_style(p, selector="QLabel"),
        ]))

    # ---------------------------
    # Public API
    # ---------------------------

    def clear_rows(self) -> None:
        self.list.clear()

    def set_counts(self, counts: Dict[str, Tuple[str, int]]) -> None:
        self.list.blockSignals(True)
        try:
            self.list.clear()
            items = sorted(counts.items(), key=lambda kv: (-kv[1][1], kv[0].lower()))

            for name, (color, cnt) in items:
                it = QListWidgetItem()
                it.setData(Qt.UserRole, name)

                row = _LabelRow(
                    name=name,
                    color=color,
                    count=cnt,
                    row_height=self.row_height,
                    spacing=self.spacing,
                    margins=self.margins,
                    swatch_size=self.swatch_size,
                    count_width=self.count_width,
                )

                it.setSizeHint(QSize(0, self.row_height))
                self.list.addItem(it)
                self.list.setItemWidget(it, row)
        finally:
            self.list.blockSignals(False)

    def _on_item_clicked(self, item: QListWidgetItem) -> None:
        name = item.data(Qt.UserRole)
        if isinstance(name, str) and name:
            self.labelClicked.emit(name)
