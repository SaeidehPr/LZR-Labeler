from __future__ import annotations

from PySide6.QtWidgets import (
    QGroupBox,
    QVBoxLayout,
    QHBoxLayout,
    QSlider,
    QLabel,
    QWidget,
    QCheckBox,
    QSizePolicy,
)
from PySide6.QtCore import Qt, Signal, QSize

from lzr_labeler.theme import (
    current_mode,
    get_palette,
    groupbox_with_border_style,
    slider_style,
    label_secondary_style,
    label_accent_style,
    get_pixmap,
)
from lzr_labeler.theme.custom_styles import create_toggle_switch_style


# =============================================================================
# Theme Toggle Switch
# =============================================================================

class ThemeToggleSwitch(QWidget):
    """
    A toggle switch widget for switching between light and dark themes.
    
    Displays sun and moon icons on either side of a toggle switch.
    Emits modeChanged signal when the theme mode changes.
    
    Signals:
        modeChanged(str): Emitted when mode changes ("light" or "dark")
    """
    
    modeChanged = Signal(str)

    def __init__(self, parent=None, icon_size: int = 18) -> None:
        super().__init__(parent)
        
        self._mode = current_mode()
        self._icon_size = icon_size

        # Create icon labels
        self.sun = QLabel()
        self.moon = QLabel()

        for lbl in (self.sun, self.moon):
            lbl.setFixedSize(QSize(icon_size, icon_size))
            lbl.setAlignment(Qt.AlignCenter)

        # Create toggle checkbox (styled as switch)
        self.toggle = QCheckBox()
        self.toggle.setText("")
        self.toggle.setCursor(Qt.PointingHandCursor)

        # Apply custom toggle switch style
        self._toggle_style = create_toggle_switch_style(self.toggle, self._mode)
        self.toggle.setStyle(self._toggle_style)

        # Layout: [sun] [toggle] [moon]
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(10)
        row.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        row.addWidget(self.sun)
        row.addWidget(self.toggle)
        row.addWidget(self.moon)

        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        # Connect signal
        self.toggle.toggled.connect(self._on_toggled)

        # Initialize with current mode
        self.set_mode(self._mode, icon_size)

    # -------------------------------------------------------------------------
    # Public Methods
    # -------------------------------------------------------------------------

    def set_mode(self, mode: str, icon_size: int | None = None) -> None:
        """
        Set the current theme mode and update visuals.
        
        Args:
            mode: Theme mode ("light" or "dark")
            icon_size: Optional new icon size
        """
        if icon_size is None:
            icon_size = self._icon_size
        else:
            self._icon_size = icon_size

        self._mode = mode

        # Update toggle state without triggering signal
        self.toggle.blockSignals(True)
        self.toggle.setChecked(mode == "dark")
        self.toggle.blockSignals(False)

        # Update toggle style
        self._toggle_style.set_mode(mode)
        self.toggle.update()

        # Update icons with theme-appropriate tinting
        self.sun.setPixmap(
            get_pixmap("sun", mode=mode, size=(icon_size, icon_size), tint=True)
        )
        self.moon.setPixmap(
            get_pixmap("moon", mode=mode, size=(icon_size, icon_size), tint=True)
        )
        
        self.updateGeometry()

    # -------------------------------------------------------------------------
    # Private Slots
    # -------------------------------------------------------------------------

    def _on_toggled(self, checked: bool) -> None:
        """Handle toggle state change."""
        mode = "dark" if checked else "light"
        self.modeChanged.emit(mode)


# =============================================================================
# Settings Box
# =============================================================================

class SettingBox(QGroupBox):
    """
    Settings panel containing application configuration options.
    
    Currently includes:
    - AI confidence threshold slider (10% - 100%)
    - Theme mode toggle (light/dark)
    
    Signals:
        confidenceChanged(float): Emitted when confidence changes (0.0 - 1.0)
        themeModeChanged(str): Emitted when theme mode changes ("light" or "dark")
    """

    confidenceChanged = Signal(float)
    themeModeChanged = Signal(str)

    DEFAULT_CONFIDENCE = 90  # Default confidence percentage

    def __init__(self, parent=None) -> None:
        super().__init__("Settings", parent)
        
        self._setup_ui()
        self._apply_styles()

    # -------------------------------------------------------------------------
    # UI Setup
    # -------------------------------------------------------------------------

    def _setup_ui(self) -> None:
        """Build the settings panel UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 12, 8, 8)
        layout.setSpacing(8)

        # AI Confidence slider section
        confidence_widget = self._create_confidence_slider()
        layout.addWidget(confidence_widget)

        # Theme toggle section
        self.themeToggle = ThemeToggleSwitch()
        self.themeToggle.modeChanged.connect(self.themeModeChanged.emit)
        layout.addWidget(self.themeToggle)

        layout.addStretch(1)

    def _create_confidence_slider(self) -> QWidget:
        """
        Create the AI confidence slider widget.
        
        Returns:
            QWidget containing the slider and labels
        """
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        # Label row: [Title] ... [Value%]
        label_row = QHBoxLayout()
        label_row.setContentsMargins(0, 0, 0, 0)

        title_label = QLabel("AI Confidence")
        title_label.setObjectName("settingTitle")

        self._confidence_value_label = QLabel(f"{self.DEFAULT_CONFIDENCE}%")
        self._confidence_value_label.setObjectName("settingValue")
        self._confidence_value_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        label_row.addWidget(title_label)
        label_row.addWidget(self._confidence_value_label)

        # Slider
        self._confidence_slider = QSlider(Qt.Horizontal)
        self._confidence_slider.setMinimum(10)    # 10%
        self._confidence_slider.setMaximum(100)   # 100%
        self._confidence_slider.setValue(self.DEFAULT_CONFIDENCE)
        self._confidence_slider.setTickPosition(QSlider.TicksBelow)
        self._confidence_slider.setTickInterval(10)
        self._confidence_slider.setCursor(Qt.PointingHandCursor)
        self._confidence_slider.valueChanged.connect(self._on_confidence_changed)

        layout.addLayout(label_row)
        layout.addWidget(self._confidence_slider)

        return widget

    # -------------------------------------------------------------------------
    # Public API
    # -------------------------------------------------------------------------

    def confidence(self) -> float:
        """
        Get current confidence value.
        
        Returns:
            Confidence as float (0.0 - 1.0)
        """
        return self._confidence_slider.value() / 100.0

    def set_confidence(self, value: float) -> None:
        """
        Set confidence value.
        
        Args:
            value: Confidence as float (0.0 - 1.0)
        """
        int_value = int(value * 100)
        int_value = max(10, min(100, int_value))
        self._confidence_slider.setValue(int_value)

    def reset_to_default(self) -> None:
        """Reset confidence to default value (90%)."""
        self._confidence_slider.setValue(self.DEFAULT_CONFIDENCE)

    def set_theme_mode(self, mode: str) -> None:
        """
        Update theme mode for this widget.
        
        Args:
            mode: Theme mode ("light" or "dark")
        """
        self.themeToggle.set_mode(mode)
        self._apply_styles(mode)

    # -------------------------------------------------------------------------
    # Private Slots
    # -------------------------------------------------------------------------

    def _on_confidence_changed(self, value: int) -> None:
        """Handle slider value change."""
        self._confidence_value_label.setText(f"{value}%")
        self.confidenceChanged.emit(value / 100.0)

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

        self.setStyleSheet("\n".join([
            groupbox_with_border_style(p),
            slider_style(p),
            label_secondary_style(p, "QLabel#settingTitle"),
            label_accent_style(p, "QLabel#settingValue"),
        ]))