from __future__ import annotations

import os
from typing import Dict

from PySide6.QtWidgets import (
    QGroupBox,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QToolButton,
    QButtonGroup,
    QWidget,
    QPushButton,
    QInputDialog,
    QScrollArea,
)
from PySide6.QtCore import Qt, Signal, QSize
from PySide6.QtGui import QPixmap, QShortcut, QKeySequence

from lzr_labeler.core.defects import DefectType
from lzr_labeler.core.label_manager import LabelManager
from lzr_labeler.core.paths import resource_path

from lzr_labeler.theme import (
    current_mode,
    get_palette,
    groupbox_with_border_style,
    scrollarea_style,
    toolbutton_swatch_style,
    button_flat_style,
    button_primary_style,
    label_secondary_style,
    scrollbar_style,
)
from lzr_labeler.theme.palette import ThemeMode
from lzr_labeler.theme.icons import create_color_swatch


class ClickableLabel(QLabel):
    """Clickable QLabel used as a proxy to click the swatch button."""
    clicked = Signal()

    def __init__(self, text: str = "", parent=None):
        super().__init__(text, parent)
        self.setCursor(Qt.PointingHandCursor)

    def mousePressEvent(self, event):
        self.clicked.emit()
        return super().mousePressEvent(event)


class DefectTypesPanel(QGroupBox):
    """
    Defect types list with:
      - scrollable rows
      - exclusive swatch selection
      - optional per-defect icon from assets/icons
      - bottom actions: add + apply

    Theme:
      - call set_theme_mode(mode) from MainWindow on theme change
    """

    defectSelected = Signal(str)
    defectAdded = Signal(str, str)  # (name, color)

    def __init__(self, label_manager: LabelManager, parent=None):
        super().__init__("Labels", parent)

        # -----------------------------
        # State
        # -----------------------------
        self._label_manager = label_manager
        self._mode: ThemeMode = current_mode()

        self._icons_dir = resource_path("assets/icons")
        self._icon_size = 35

        self._icon_labels: Dict[str, QLabel] = {}

        # Exclusive swatch selection
        self._button_group = QButtonGroup(self)
        self._button_group.setExclusive(True)

        # UI mappings
        self._swatch_buttons: Dict[str, QToolButton] = {}
        self._name_labels: Dict[str, ClickableLabel] = {}
        self._row_widgets: Dict[str, QWidget] = {}

        # Pending (UI-only) selection
        self._pending_selection: str | None = None

        # Ordering policy
        initial_defects = list(self._label_manager.all_defects)
        self._builtin_order: list[str] = [d.name for d in initial_defects]
        self._custom_order: list[str] = []

        # -----------------------------
        # Layout
        # -----------------------------
        outer = QVBoxLayout(self)
        outer.setContentsMargins(4, 4, 4, 4)
        outer.setSpacing(8)

        # Scroll area (rows)
        self._scroll = QScrollArea(self)
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QScrollArea.NoFrame)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)

        self._rows_container = QWidget()
        self._rows_layout = QVBoxLayout(self._rows_container)
        self._rows_layout.setContentsMargins(0, 0, 0, 0)
        self._rows_layout.setSpacing(8)

        self._scroll.setWidget(self._rows_container)
        outer.addWidget(self._scroll, 1)

        # Bottom bar (fixed)
        bottom_bar = QWidget(self)
        bottom_lay = QHBoxLayout(bottom_bar)
        bottom_lay.setContentsMargins(0, 0, 0, 0)
        bottom_lay.setSpacing(8)

        self._btn_add = QPushButton("+ New label")
        self._btn_add.setFlat(True)
        self._btn_add.setCursor(Qt.PointingHandCursor)
        self._btn_add.clicked.connect(self._on_add_clicked)

        self._btn_apply = QPushButton("Apply")
        self._btn_apply.setCursor(Qt.PointingHandCursor)
        self._btn_apply.setEnabled(False)
        self._btn_apply.clicked.connect(self._on_apply_clicked)

        bottom_lay.addWidget(self._btn_add, 0, Qt.AlignLeft)
        bottom_lay.addStretch(1)
        bottom_lay.addWidget(self._btn_apply, 0, Qt.AlignRight)

        outer.addWidget(bottom_bar, 0)

        # -----------------------------
        # Build initial rows (builtin order)
        # -----------------------------
        for defect in initial_defects:
            self._create_defect_row(defect)

        self._rebuild_rows_layout()

        # Pre-select first builtin defect if exists
        if initial_defects:
            self.select_defect(initial_defects[0].name)

        # Apply initial theme
        self._apply_styles(self._mode)

        # Enter/Return should apply when focus is inside this panel (or its children)
        sc_return = QShortcut(QKeySequence(Qt.Key_Return), self)
        sc_return.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        sc_return.activated.connect(self.apply_pending)

        sc_enter = QShortcut(QKeySequence(Qt.Key_Enter), self)
        sc_enter.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        sc_enter.activated.connect(self.apply_pending)


    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_theme_mode(self, mode: ThemeMode) -> None:
        """Apply theme to this module."""
        self._mode = mode
        self._apply_styles(mode)
        self.update()

    def current_selection(self) -> str | None:
        return self._pending_selection

    def color_for(self, name: str) -> str:
        return self._label_manager.get_color(name)

    def select_defect(self, name: str) -> None:
        if name not in self._swatch_buttons:
            return
        self._pending_selection = name
        self._update_selection_visuals(name)
        self._update_apply_button_state()

    def all_defects(self) -> list[DefectType]:
        return self._label_manager.all_defects

    def ensure_defect_type(self, name: str) -> None:
        if name in self._swatch_buttons:
            return

        new_defect = self._label_manager.add_defect_if_not_exists(name)
        self._create_defect_row(new_defect)

        if name not in self._builtin_order and name not in self._custom_order:
            self._custom_order.append(name)

        self._rebuild_rows_layout()

    def refresh_from_manager(self) -> None:
        current_names = {d.name for d in self._label_manager.all_defects}

        # Remove missing
        for name in list(self._row_widgets.keys()):
            if name not in current_names:
                self._remove_defect_row(name)

        # Add new ones
        for defect in self._label_manager.all_defects:
            if defect.name not in self._row_widgets:
                self._create_defect_row(defect)
                if defect.name not in self._builtin_order and defect.name not in self._custom_order:
                    self._custom_order.append(defect.name)

        self._rebuild_rows_layout()

    def apply_pending(self) -> None:
        if self._pending_selection:
            self.defectSelected.emit(self._pending_selection)

    # ------------------------------------------------------------------
    # Theme
    # ------------------------------------------------------------------

    def _apply_styles(self, mode: ThemeMode) -> None:
        p = get_palette(mode)

        # Panel-level styles
        self.setStyleSheet("\n".join([
            groupbox_with_border_style(p),
            toolbutton_swatch_style(p),
            label_secondary_style(p, selector="QGroupBox QLabel"),
        ]))

        # Scroll area + its scrollbars (scoped to this scroll area)
        self._scroll.setStyleSheet("\n".join([
            scrollarea_style(p),
            scrollbar_style(p),
        ]))

        # Buttons: apply per-widget styles to avoid global QPushButton selector conflicts
        self._btn_add.setStyleSheet(button_flat_style(p))
        self._btn_apply.setStyleSheet(button_primary_style(p))

    # ------------------------------------------------------------------
    # Row UI creation
    # ------------------------------------------------------------------

    def _create_defect_row(self, defect: DefectType) -> None:
        """Create row widgets & store refs. Layout order is handled elsewhere."""
        row = QWidget(self._rows_container)
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(6)

        # Swatch button
        swatch = QToolButton(row)
        swatch.setCheckable(True)
        swatch.setProperty("defect_swatch", True)
        swatch.setIconSize(QSize(16, 16))
        swatch.setCursor(Qt.PointingHandCursor)
        swatch.setIcon(create_color_swatch(defect.color, size=16, checked=False))
        self._button_group.addButton(swatch)

        swatch.clicked.connect(lambda checked, name=defect.name: self._on_swatch_clicked(name, checked))

        # Optional icon label (colored icon, no tint)
        icon_label = QLabel(row)
        icon_label.setFixedSize(self._icon_size, self._icon_size)
        self._load_icon(icon_label, defect.name)

        # Clickable name label
        label = ClickableLabel(defect.name, row)
        label.setAlignment(Qt.AlignVCenter | Qt.AlignLeft)
        label.clicked.connect(swatch.click)

        row_layout.addWidget(swatch)
        row_layout.addWidget(icon_label)
        row_layout.addWidget(label)
        row_layout.addStretch(1)

        self._swatch_buttons[defect.name] = swatch
        self._name_labels[defect.name] = label
        self._icon_labels[defect.name] = icon_label
        self._row_widgets[defect.name] = row

    def _remove_defect_row(self, name: str) -> None:
        row = self._row_widgets.pop(name, None)
        if row:
            row.setParent(None)
            row.deleteLater()

        self._swatch_buttons.pop(name, None)
        self._name_labels.pop(name, None)
        self._icon_labels.pop(name, None)

        if name in self._custom_order:
            self._custom_order.remove(name)

        if self._pending_selection == name:
            self._pending_selection = None
            self._update_apply_button_state()

    # ------------------------------------------------------------------
    # Layout rebuild (order policy)
    # ------------------------------------------------------------------

    def _clear_rows_layout(self) -> None:
        """Remove all items from rows layout without deleting stored row widgets."""
        while self._rows_layout.count():
            item = self._rows_layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.setParent(None)

    def _rebuild_rows_layout(self) -> None:
        """Order = builtin (initial order) + custom (added order) + stretch."""
        self._clear_rows_layout()

        # Builtins
        for name in self._builtin_order:
            row = self._row_widgets.get(name)
            if row is not None:
                self._rows_layout.addWidget(row)

        # Customs
        for name in self._custom_order:
            row = self._row_widgets.get(name)
            if row is not None:
                self._rows_layout.addWidget(row)

        self._rows_layout.addStretch(1)

        if self._pending_selection:
            self._update_selection_visuals(self._pending_selection)

        self._update_apply_button_state()

    # ------------------------------------------------------------------
    # Icons
    # ------------------------------------------------------------------

    def _load_icon(self, label: QLabel, defect_name: str) -> None:
        icon_path = self._icon_path_for_defect(defect_name)
        if icon_path:
            pm = QPixmap(str(icon_path))
            if not pm.isNull():
                pm = pm.scaled(
                    self._icon_size,
                    self._icon_size,
                    Qt.KeepAspectRatio,
                    Qt.SmoothTransformation,
                )
                label.setPixmap(pm)
                return
        label.setPixmap(QPixmap())

    def _icon_path_for_defect(self, name: str) -> str | None:
        if not os.path.isdir(self._icons_dir):
            return None

        base_names = [
            name,
            name.replace(" ", "_"),
            name.replace("-", "_"),
            name.lower(),
            name.lower().replace(" ", "_"),
        ]
        exts = [".png", ".jpg", ".jpeg", ".svg", ".ico", ".bmp", ".webp"]

        for base in base_names:
            for ext in exts:
                path = os.path.join(self._icons_dir, base + ext)
                if os.path.isfile(path):
                    return path
        return None

    # ------------------------------------------------------------------
    # Events
    # ------------------------------------------------------------------

    def _on_swatch_clicked(self, name: str, checked: bool) -> None:
        if not checked:
            return

        self._pending_selection = name
        self._update_selection_visuals(name)
        self._update_apply_button_state()

    def _on_apply_clicked(self) -> None:
        if self._pending_selection:
            self.defectSelected.emit(self._pending_selection)

    def _on_add_clicked(self) -> None:
        text, ok = QInputDialog.getText(
            self,
            "New Label",
            "Enter new defect name:",
        )
        name = text.strip()

        if not ok or not name:
            return

        # If exists, just select it
        if name in self._swatch_buttons:
            self.select_defect(name)
            return

        # Add via label manager (handles persistence)
        try:
            new_defect = self._label_manager.add_defect(name)
        except ValueError as e:
            print(f"Could not add defect: {e}")
            return

        # Create row + register as custom
        self._create_defect_row(new_defect)
        if name not in self._custom_order and name not in self._builtin_order:
            self._custom_order.append(name)

        self._rebuild_rows_layout()

        self.select_defect(name)
        self.defectAdded.emit(new_defect.name, new_defect.color)

        # Scroll to bottom so the added item is visible
        sb = self._scroll.verticalScrollBar()
        sb.setValue(sb.maximum())

    # ------------------------------------------------------------------
    # UI updates
    # ------------------------------------------------------------------

    def _update_selection_visuals(self, selected_name: str) -> None:
        for name, btn in self._swatch_buttons.items():
            defect = self._label_manager.get_defect(name)
            color = defect.color if defect else "#000000"
            is_selected = (name == selected_name)

            btn.setIcon(create_color_swatch(color, size=16, checked=is_selected))
            btn.setChecked(is_selected)

    def _update_apply_button_state(self) -> None:
        self._btn_apply.setEnabled(self._pending_selection is not None)
