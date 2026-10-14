from __future__ import annotations

from pathlib import Path
from typing import Optional

from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QColor

# Re-export from submodules
from .palette import (
    ThemePalette,
    ThemeMode,
    LIGHT_PALETTE,
    DARK_PALETTE,
    get_palette,
    get_color,
)

from .styles import (
    # Typography
    FONT_FAMILY,
    FONT_SIZE_XS,
    FONT_SIZE_SM,
    FONT_SIZE_MD,
    FONT_SIZE_LG,
    FONT_SIZE_XL,
    FONT_SIZE_XXL,
    # Individual widget styles
    groupbox_style,
    groupbox_with_border_style,
    button_flat_style,
    button_flat_special_style,
    button_primary_style,
    button_outlined_style,
    label_style,
    label_secondary_style,
    label_accent_style,
    slider_style,
    slider_thin_style,
    listwidget_style,
    scrollarea_style,
    scrollarea_bordered_style,
    dialog_style,
    frame_separator_style,
    frame_viewport_overlay_style,
    lineedit_style,
    combobox_style,
    checkbox_style,
    radiobutton_style,
    toolbutton_swatch_style,
    scrollbar_style,
    menu_style,
    tooltip_style,
    messagebox_style,
    inputdialog_style,
    mainwindow_style,
    widget_base_style,
    # Combined generators
    generate_full_stylesheet,
    generate_minimal_stylesheet,
    generate_dialog_stylesheet,
)

from .icons import (
    get_icon,
    get_pixmap,
    get_icon_with_color,
    tint_pixmap,
    tint_pixmap_with_color,
    create_color_swatch,
    init_icons,
    add_icon_search_path,
    AssetPaths,
)

from .custom_styles import (
    SquareRadioStyle,
    SquareCheckboxStyle,
    create_square_radio_style,
    create_square_checkbox_style,
)


# ==================== Current Theme State ====================

_current_mode: ThemeMode = "light"


def current_mode() -> ThemeMode:
    """Get the current theme mode."""
    return _current_mode


def current_palette() -> ThemePalette:
    """Get the current theme palette."""
    return get_palette(_current_mode)


# ==================== Theme Application ====================

def apply_theme(
    app: QApplication,
    mode: ThemeMode,
    *,
    assets_dir: Optional[Path] = None,
    minimal: bool = True,
) -> None:
    """
    Apply theme to the entire application.
    
    This sets the global stylesheet and updates icon paths.
    
    Args:
        app: QApplication instance
        mode: "light" or "dark"
        assets_dir: Optional custom assets directory
        minimal: If True (default), only apply base styles (colors, fonts, scrollbars).
                 Individual widgets keep their own _apply_styles().
                 If False, apply full stylesheet (may override widget styles).
        
    Example:
        app = QApplication(sys.argv)
        apply_theme(app, "dark")  # minimal=True by default
        apply_theme(app, "dark", minimal=False)  # full override
    """
    global _current_mode
    
    if mode not in ("light", "dark"):
        raise ValueError(f"Invalid theme mode: {mode}. Use 'light' or 'dark'.")
    
    _current_mode = mode
    
    # Initialize icon paths
    if assets_dir:
        init_icons(assets_dir)
    else:
        init_icons()
    
    # Generate and apply stylesheet
    palette = get_palette(mode)
    
    if minimal:
        stylesheet = generate_minimal_stylesheet(palette)
    else:
        stylesheet = generate_full_stylesheet(palette)
    
    # Clear existing stylesheet first
    app.setStyleSheet("")
    app.setStyleSheet(stylesheet)


def apply_widget_theme(widget, mode: ThemeMode) -> None:
    """
    Apply theme to a specific widget (and its children).
    
    Useful for widgets created after apply_theme() was called,
    or for applying theme to a specific subtree.
    
    Args:
        widget: QWidget to theme
        mode: "light" or "dark"
    """
    palette = get_palette(mode)
    stylesheet = generate_full_stylesheet(palette)
    widget.setStyleSheet(stylesheet)


def get_stylesheet(mode: ThemeMode) -> str:
    """
    Get the full stylesheet for a theme mode.
    
    Args:
        mode: "light" or "dark"
        
    Returns:
        Complete QSS stylesheet string
    """
    palette = get_palette(mode)
    return generate_full_stylesheet(palette)


def get_dialog_stylesheet(mode: ThemeMode) -> str:
    """
    Get stylesheet optimized for dialogs.
    
    Args:
        mode: "light" or "dark"
        
    Returns:
        Dialog-specific QSS stylesheet string
    """
    palette = get_palette(mode)
    return generate_dialog_stylesheet(palette)


# ==================== Color Helpers ====================

def themed_color(color_name: str, mode: Optional[ThemeMode] = None) -> str:
    """
    Get a color from the current (or specified) theme.
    
    Args:
        color_name: Name of color attribute (e.g., "accent", "text_primary")
        mode: Theme mode (uses current if not specified)
        
    Returns:
        Color value as string
    """
    if mode is None:
        mode = _current_mode
    return get_color(mode, color_name)


def qcolor(color_name: str, mode: Optional[ThemeMode] = None) -> QColor:
    """
    Get a QColor from the current (or specified) theme.
    
    Args:
        color_name: Name of color attribute
        mode: Theme mode (uses current if not specified)
        
    Returns:
        QColor instance
    """
    return QColor(themed_color(color_name, mode))


# ==================== Convenience Functions ====================

def is_dark_mode() -> bool:
    """Check if current theme is dark mode."""
    return _current_mode == "dark"


def is_light_mode() -> bool:
    """Check if current theme is light mode."""
    return _current_mode == "light"


def toggle_mode() -> ThemeMode:
    """
    Toggle between light and dark mode.
    
    Note: This only changes the internal state. You still need to
    call apply_theme() to actually update the UI.
    
    Returns:
        The new mode after toggling
    """
    global _current_mode
    _current_mode = "dark" if _current_mode == "light" else "light"
    return _current_mode


# ==================== Module Exports ====================

__all__ = [
    # Mode type
    "ThemeMode",
    
    # Palettes
    "ThemePalette",
    "LIGHT_PALETTE",
    "DARK_PALETTE",
    "get_palette",
    "get_color",
    "current_palette",
    "current_mode",
    
    # Application
    "apply_theme",
    "apply_widget_theme",
    "get_stylesheet",
    "get_dialog_stylesheet",
    
    # Icons
    "get_icon",
    "get_pixmap",
    "get_icon_with_color",
    "tint_pixmap",
    "tint_pixmap_with_color",
    "create_color_swatch",
    "init_icons",
    "add_icon_search_path",
    
    # Custom styles
    "SquareRadioStyle",
    "SquareCheckboxStyle",
    "create_square_radio_style",
    "create_square_checkbox_style",
    
    # Individual style functions (for custom widgets)
    "groupbox_style",
    "groupbox_with_border_style",
    "button_flat_style",
    "button_flat_special_style",
    "button_primary_style",
    "button_outlined_style",
    "label_style",
    "label_secondary_style",
    "label_accent_style",
    "slider_style",
    "slider_thin_style",
    "listwidget_style",
    "scrollarea_style",
    "scrollarea_bordered_style",
    "dialog_style",
    "lineedit_style",
    "combobox_style",
    "checkbox_style",
    "radiobutton_style",
    "scrollbar_style",
    "menu_style",
    "tooltip_style",
    
    # Typography
    "FONT_FAMILY",
    "FONT_SIZE_SM",
    "FONT_SIZE_MD",
    "FONT_SIZE_LG",
    
    # Color helpers
    "themed_color",
    "qcolor",
    
    # Convenience
    "is_dark_mode",
    "is_light_mode",
    "toggle_mode",
]