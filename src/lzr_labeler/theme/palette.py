from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

ThemeMode = Literal["light", "dark"]


@dataclass(frozen=True)
class ThemePalette:
    # ==================== Mode identifier ====================
    mode: ThemeMode
    
    # ==================== Font Settings ====================
    font_family: str            # Main font family
    font_size_xs: str           # Extra small (11px)
    font_size_sm: str           # Small (12px)
    font_size_md: str           # Medium (13px)
    font_size_lg: str           # Large (14px)
    font_size_xl: str           # Extra large (16px)
    font_size_xxl: str          # Extra extra large (18px)
    
    # ==================== Text Colors ====================
    text_primary: str           # Main text color
    text_secondary: str         # Secondary/subtitle text
    text_disabled: str          # Disabled state text
    text_placeholder: str       # Placeholder text in inputs
    text_on_accent: str         # Text on accent-colored backgrounds
    
    # ==================== Accent Colors ====================
    accent: str                 # Primary accent (buttons, links, active states)
    accent_hover: str           # Accent hover state
    accent_pressed: str         # Accent pressed state
    accent_text: str            # Text in accent color (e.g., AI button)
    accent_light: str           # Light accent for highlights
    
    # ==================== Background Colors ====================
    background: str             # Main window background
    background_card: str        # Card/panel background
    background_input: str       # Input field background
    background_dialog: str      # Dialog background
    background_hover: str       # Hover state background (rgba)
    background_selected: str    # Selected item background (rgba)
    background_disabled: str    # Disabled element background
    
    # ==================== Border Colors ====================
    border: str                 # Standard border
    border_light: str           # Lighter border (input fields)
    border_focus: str           # Focused element border
    
    # ==================== Special Colors ====================
    canvas_background: str      # Canvas/viewport background
    overlay_viewport: str       # Monitoring box viewport overlay
    scrollbar_handle: str       # Scrollbar handle color
    scrollbar_track: str        # Scrollbar track color
    separator: str              # Separator line color
    
    # ==================== Semantic Colors ====================
    success: str                # Success state
    warning: str                # Warning state
    error: str                  # Error state
    info: str                   # Info state
    
    # ==================== Icon Tint ====================
    icon_tint: str              # Color for tinting monochrome icons
    
    # ==================== GroupBox Title ====================
    groupbox_title_bg: str      # Background behind groupbox title text


# ==================== Light Theme Palette ====================

LIGHT_PALETTE = ThemePalette(
    mode="light",
    
    # Font
    font_family="'Inter', 'Segoe UI', 'Roboto', sans-serif",
    font_size_xs="11px",
    font_size_sm="12px",
    font_size_md="13px",
    font_size_lg="14px",
    font_size_xl="16px",
    font_size_xxl="18px",
    
    # Text
    text_primary="#535353",
    text_secondary="#5A5A5A",
    text_disabled="#a7a7a7",
    text_placeholder="#A0A0A0",
    text_on_accent="#dfdfdf",
    
    # Accent (Blue from LZR Labelr)
    accent="#6EA0E1",
    accent_hover="#6EA0E1",
    accent_pressed="#3a8fd9",
    accent_text="#6EA0E1",
    accent_light="rgba(110, 160, 225, 0.7)",
    
    # Backgrounds
    background="#ffffff",
    background_card="#ebebeb",
    background_input="#c2c2c2",
    background_dialog="#dfdfdf",
    background_hover="rgba(110, 160, 225, 0.5)",
    background_selected="rgba(110, 160, 225, 0.35)",
    background_disabled="#f0f0f0",
    
    # Borders
    border="#535353",
    border_light="#c2c2c2",
    border_focus="#6EA0E1",
    
    # Special
    canvas_background="#c0c0c0",  # Qt.lightGray equivalent
    overlay_viewport="#dc3545",
    scrollbar_handle="#6EA0E1",
    scrollbar_track="#c2c2c2",
    separator="#dddddd",
    
    # Semantic
    success="#28a745",
    warning="#ffc107",
    error="#dc3545",
    info="#17a2b8",
    
    # Icon tint
    icon_tint="#5A5A5A",  # Dark gray for light mode
    
    # GroupBox
    groupbox_title_bg="#ffffff",  # Same as background
)


# ==================== Dark Theme Palette ====================

DARK_PALETTE = ThemePalette(
    mode="dark",
    
    # Font
    font_family="'Inter', 'Segoe UI', 'Roboto', sans-serif",
    font_size_xs="11px",
    font_size_sm="12px",
    font_size_md="13px",
    font_size_lg="14px",
    font_size_xl="16px",
    font_size_xxl="18px",
    
    # Text
    text_primary="#dcdcdc",
    text_secondary="#b0b0b0",
    text_disabled="#606060",
    text_placeholder="#707070",
    text_on_accent="#ffffff",
    
    # Accent (Same blue, slightly brighter for dark mode)
    accent="#6EA0E1",
    accent_hover="#6EA0E1",
    accent_pressed="#3a8fd9",
    accent_text="#6EA0E1",
    accent_light="rgba(110, 160, 225, 0.7)",
    
    # Backgrounds
    background="#1e1e1e",
    background_card="#2d2d2d",
    background_input="#3d3d3d",
    background_dialog="#252525",
    background_hover="rgba(110, 160, 225, 0.4)",
    background_selected="rgba(110, 160, 225, 0.45)",
    background_disabled="#353535",
    
    # Borders
    border="#dcdcdc",
    border_light="#3d3d3d",
    border_focus="rgba(110, 160, 225, 1.0)",
    
    # Special
    canvas_background="#3a3a3a",
    overlay_viewport="#e74c3c",
    scrollbar_handle="#6EA0E1",
    scrollbar_track="#3d3d3d",
    separator="#404040",
    
    # Semantic
    success="#2ecc71",
    warning="#f39c12",
    error="#e74c3c",
    info="#3498db",
    
    # Icon tint
    icon_tint="#b0b0b0",  # Light gray for dark mode
    
    # GroupBox
    groupbox_title_bg="#1e1e1e",  # Same as background
)


# ==================== Palette Access Functions ====================

def get_palette(mode: ThemeMode) -> ThemePalette:
    """
    Get the color palette for the specified theme mode.
    
    Args:
        mode: "light" or "dark"
        
    Returns:
        ThemePalette for the specified mode
    """
    if mode == "dark":
        return DARK_PALETTE
    return LIGHT_PALETTE


def get_color(mode: ThemeMode, color_name: str) -> str:
    """
    Get a specific color from the palette.
    
    Args:
        mode: "light" or "dark"
        color_name: Name of the color attribute
        
    Returns:
        Color value as string
        
    Raises:
        AttributeError: If color_name doesn't exist
    """
    palette = get_palette(mode)
    return getattr(palette, color_name)