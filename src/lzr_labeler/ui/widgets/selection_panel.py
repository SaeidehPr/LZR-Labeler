from __future__ import annotations

from PySide6.QtWidgets import (
    QGroupBox,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QSizePolicy,
    QFrame,
    QWidget,
    QLabel,
    QLineEdit,
)
from PySide6.QtCore import QSize, Signal, Qt
from PySide6.QtGui import QIntValidator

from lzr_labeler.theme import (
    current_mode,
    get_palette,
    get_icon,
    groupbox_style,
    button_flat_style,
    button_flat_special_style,
)


class SelectionPanel(QGroupBox):
    """
    Vertical toolbar panel with file, navigation, and tool buttons.
    
    Signals:
        fileRequested: Open single file dialog
        folderRequested: Open folder dialog
        prevRequested: Navigate to previous image
        nextRequested: Navigate to next image
        annotationToggled(bool): Annotation mode toggled
        editToggled(bool): Edit mode toggled
        zoomFitRequested: Fit image to viewport
        zoomActualRequested: Show image at actual size
        deleteRequested: Delete selected shapes
        undoRequested: Undo last action
        redoRequested: Redo last undone action
        infoRequested: Show info dialog
        aiRequested: Run AI detection
    """

    # File/Folder signals
    fileRequested = Signal()
    folderRequested = Signal()

    # Navigation signals
    prevRequested = Signal()
    nextRequested = Signal()
    indexRequested = Signal(int)

    # Mode signals
    annotationToggled = Signal(bool)
    editToggled = Signal(bool)

    # Zoom signals
    zoomFitRequested = Signal()
    zoomActualRequested = Signal()

    # Action signals
    deleteRequested = Signal()
    undoRequested = Signal()
    redoRequested = Signal()
    infoRequested = Signal()

    # AI signal
    aiRequested = Signal()

    # Button configuration: (label, icon_name, separator_before, checkable)
    BUTTON_CONFIG = [
        ("File", "file", False, False),
        ("Folder", "folder", False, False),
        ("Prev", "prev", True, False),
        ("Next", "next", False, False),
        ("Annotation", "annotation", True, True),
        ("Edit", "edit mode", False, True),
        ("AI Detect", "ai", True, False),
        ("Zoom Fit", "zoom fit", True, False),
        ("Actual Size", "actual size", False, False),
        ("Delete", "delete", True, False),
        ("Undo", "undo", False, False),
        ("Redo", "redo", False, False),
        ("Info", "info", True, False),
    ]

    def __init__(self, parent=None) -> None:
        super().__init__("", parent)

        self._mode = current_mode()
        self._separators: list[QFrame] = []
        
        self._setup_ui()
        self._connect_signals()
        self._apply_styles()

    # -------------------------------------------------------------------------
    # UI Setup
    # -------------------------------------------------------------------------

    def _setup_ui(self) -> None:
        """Build the panel UI with buttons."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(2, 2, 2, 2)
        layout.setSpacing(15)

        self.buttons: dict[str, QPushButton] = {}

        for label, icon_name, separator, checkable in self.BUTTON_CONFIG:
            # Add separator if needed
            if separator:
                line = QFrame(self)
                line.setFrameShape(QFrame.HLine)
                line.setFrameShadow(QFrame.Sunken)
                line.setFixedHeight(1)
                layout.addWidget(line)
                self._separators.append(line)

            # Create button
            btn = QPushButton(label, self)
            btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            btn.setFlat(True)
            btn.setObjectName(f"btn_{label.replace(' ', '_')}")
            btn.setIcon(get_icon(icon_name, mode=self._mode))
            btn.setIconSize(QSize(19, 19))

            if checkable:
                btn.setCheckable(True)

            layout.addWidget(btn)
            self.buttons[label] = btn

            # Add jump-to-image box exactly under "Next"
            if label == "Next":
                self._nav_widget = QWidget(self)
                nav_layout = QHBoxLayout(self._nav_widget)
                nav_layout.setContentsMargins(0, 0, 0, 0)
                nav_layout.setSpacing(4)

                self._index_edit = QLineEdit(self._nav_widget)
                self._index_edit.setText("1")
                self._index_edit.setPlaceholderText("1")
                self._index_edit.setAlignment(Qt.AlignCenter)
                self._index_edit.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
                self._index_edit.setFixedWidth(42)

                self._index_max_label = QLabel("/ 1", self._nav_widget)
                self._index_max_label.setAlignment(Qt.AlignVCenter | Qt.AlignLeft)

                nav_layout.addWidget(self._index_edit)
                nav_layout.addWidget(self._index_max_label)
                nav_layout.addStretch(1)

                self._nav_widget.hide()
                layout.addWidget(self._nav_widget)

        layout.addStretch(1)

    def _connect_signals(self) -> None:
        """Connect button signals to panel signals."""
        # File/Folder
        self.buttons["File"].clicked.connect(self.fileRequested.emit)
        self.buttons["Folder"].clicked.connect(self.folderRequested.emit)

        # Navigation
        self.buttons["Prev"].clicked.connect(self.prevRequested.emit)
        self.buttons["Next"].clicked.connect(self.nextRequested.emit)
        self._index_edit.returnPressed.connect(self._emit_requested_index)
        self._index_edit.editingFinished.connect(self._normalize_index_text)

        # Modes (with mutual exclusion)
        self.buttons["Annotation"].toggled.connect(self._on_annotation_toggled)
        self.buttons["Edit"].toggled.connect(self._on_edit_toggled)

        # AI
        self.buttons["AI Detect"].clicked.connect(self.aiRequested.emit)

        # Zoom
        self.buttons["Zoom Fit"].clicked.connect(self.zoomFitRequested.emit)
        self.buttons["Actual Size"].clicked.connect(self.zoomActualRequested.emit)

        # Actions
        self.buttons["Delete"].clicked.connect(self.deleteRequested.emit)
        self.buttons["Undo"].clicked.connect(self.undoRequested.emit)
        self.buttons["Redo"].clicked.connect(self.redoRequested.emit)
        self.buttons["Info"].clicked.connect(self.infoRequested.emit)

    # -------------------------------------------------------------------------
    # Mode Toggle Handlers
    # -------------------------------------------------------------------------

    def _on_annotation_toggled(self, checked: bool) -> None:
        """Handle annotation toggle - turn off edit if annotation is on."""
        if checked:
            self._set_button_checked("Edit", False)
        self.annotationToggled.emit(checked)

    def _on_edit_toggled(self, checked: bool) -> None:
        """Handle edit toggle - turn off annotation if edit is on."""
        if checked:
            self._set_button_checked("Annotation", False)
        self.editToggled.emit(checked)

    def _set_button_checked(self, name: str, checked: bool) -> None:
        """Set button checked state without triggering signals."""
        btn = self.buttons.get(name)
        if btn and btn.isCheckable():
            btn.blockSignals(True)
            btn.setChecked(checked)
            btn.blockSignals(False)

    # -------------------------------------------------------------------------
    # Public API
    # -------------------------------------------------------------------------

    def set_annotation_checked(self, on: bool) -> None:
        """Set annotation button state (called from canvas)."""
        self._set_button_checked("Annotation", on)

    def set_edit_checked(self, on: bool) -> None:
        """Set edit button state (called from canvas)."""
        self._set_button_checked("Edit", on)

    def set_annotation_mode(self, on: bool) -> None:
        """Programmatically set annotation mode."""
        self._set_button_checked("Annotation", on)
        self._on_annotation_toggled(on)

    def set_edit_mode(self, on: bool) -> None:
        """Programmatically set edit mode."""
        self._set_button_checked("Edit", on)
        self._on_edit_toggled(on)

    def set_ai_enabled(self, enabled: bool) -> None:
        """Enable/disable AI button."""
        btn = self.buttons.get("AI Detect")
        if btn:
            btn.setEnabled(enabled)

    def set_ai_loading(self, loading: bool) -> None:
        """Set AI button loading state."""
        btn = self.buttons.get("AI Detect")
        if btn:
            if loading:
                btn.setText("AI Loading...")
                btn.setEnabled(False)
            else:
                btn.setText("AI Detect")
                btn.setEnabled(True)

    def _emit_requested_index(self) -> None:
        """Emit the 1-based image index requested by the user."""
        text = self._index_edit.text().strip()
        if not text:
            return

        try:
            value = int(text)
        except ValueError:
            return

        self.indexRequested.emit(value)

    def _normalize_index_text(self) -> None:
        """Clamp text box value into valid image range."""
        text = self._index_edit.text().strip()
        if not text:
            self._index_edit.setText("1")
            return

        try:
            value = int(text)
        except ValueError:
            self._index_edit.setText("1")
            return

        max_text = self._index_max_label.text().replace("/", "").strip()
        try:
            max_value = max(1, int(max_text))
        except ValueError:
            max_value = 1

        value = max(1, min(value, max_value))
        self._index_edit.setText(str(value))

    def set_navigation_visible(self, visible: bool) -> None:
        """Show/hide folder-only jump navigation."""
        self._nav_widget.setVisible(visible)

    def set_navigation_range(self, total: int) -> None:
        """Set max image count for jump navigation."""
        total = max(1, int(total))

        self._index_edit.setValidator(QIntValidator(1, total, self._index_edit))
        self._index_max_label.setText(f"/ {total}")

        text = self._index_edit.text().strip()
        if not text:
            self._index_edit.setText("1")
            return

        try:
            value = int(text)
        except ValueError:
            value = 1

        value = max(1, min(value, total))
        self._index_edit.setText(str(value))

    def set_navigation_value(self, index_1_based: int) -> None:
        """Update current visible image index (1-based)."""
        value = max(1, int(index_1_based))
        self._index_edit.setText(str(value))

    def reset_navigation(self) -> None:
        """Hide and reset folder navigation."""
        self._index_edit.setText("1")
        self._index_edit.setValidator(QIntValidator(1, 1, self._index_edit))
        self._index_max_label.setText("/ 1")
        self._nav_widget.hide()

    # -------------------------------------------------------------------------
    # Styling
    # -------------------------------------------------------------------------

    def _apply_styles(self, mode: str | None = None) -> None:
        """
        Apply theme-aware styles to the widget.
        
        Args:
            mode: Theme mode (uses current_mode() if None)
        """
        if mode is None:
            mode = current_mode()

        p = get_palette(mode)

        # Apply stylesheet
        self.setStyleSheet("\n".join([
            groupbox_style(p),
            button_flat_style(p),
            button_flat_special_style(p, "btn_AI_Detect"),
        ]))

        # Update button icons with new theme tint
        for label, icon_name, _, _ in self.BUTTON_CONFIG:
            btn = self.buttons.get(label)
            if btn:
                btn.setIcon(get_icon(icon_name, mode=mode))

        # Update separator 
        separator_color = p.separator
        for sep in self._separators:
            sep.setStyleSheet(f"""
                              background-color: {separator_color};
                              height: 1px; border: none;
                              """)