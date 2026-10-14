"""
Theme Icons - Icon loading and tinting for theme support.

Handles automatic tinting of monochrome icons based on theme mode.
Colored icons (like defect icons) can be loaded without tinting.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional, Tuple, List

from PySide6.QtGui import QIcon, QPixmap, QPainter, QColor
from PySide6.QtCore import Qt, QSize

from .palette import ThemePalette, get_palette, ThemeMode


# ==================== Asset Path Management ====================

class AssetPaths:
    """
    Manages asset search paths for the application.
    """
    
    _search_paths: List[Path] = []
    _initialized: bool = False
    
    @classmethod
    def initialize(cls, base_dir: Optional[Path] = None) -> None:
        """
        Initialize asset search paths.
        
        Args:
            base_dir: Base directory for assets. If None, auto-detects.
        """
        if cls._initialized:
            return
        
        if base_dir is None:
            base_dir = cls._detect_base_directory()
        
        cls._search_paths = [
            (base_dir / "assets").resolve(),
            (base_dir / "assets" / "icons").resolve(),
        ]
        cls._initialized = True
    
    @classmethod
    def _detect_base_directory(cls) -> Path:
        """Detect application base directory."""
        if hasattr(sys, "_MEIPASS"):
            # PyInstaller --onefile mode
            return Path(sys._MEIPASS)
        elif getattr(sys, "frozen", False):
            # PyInstaller --onedir mode
            return Path(sys.executable).parent
        else:
            # Development mode - assume we're in a package
            return Path(__file__).resolve().parent.parent
    
    @classmethod
    def add_search_path(cls, path: Path) -> None:
        """Add a search path for assets."""
        if not cls._initialized:
            cls.initialize()
        
        resolved = path.resolve()
        if resolved not in cls._search_paths:
            cls._search_paths.append(resolved)
    
    @classmethod
    def find_asset(cls, filename: str) -> Optional[Path]:
        """
        Find an asset file in search paths.
        
        Args:
            filename: Asset filename (with or without extension)
            
        Returns:
            Path to asset or None if not found
        """
        if not cls._initialized:
            cls.initialize()
        
        # Generate filename variations
        names = [filename]
        if not Path(filename).suffix:
            names.extend([f"{filename}.png", f"{filename}.svg", f"{filename}.ico"])
        
        for search_dir in cls._search_paths:
            if not search_dir.exists():
                continue
            for name in names:
                asset_path = search_dir / name
                if asset_path.exists():
                    return asset_path
        
        return None


# ==================== Icon Tinting ====================

def _apply_tint(pixmap: QPixmap, color: QColor) -> QPixmap:
    """
    Apply a solid color tint to a pixmap while preserving alpha.
    
    Args:
        pixmap: Source pixmap (should be grayscale or black)
        color: Tint color to apply
        
    Returns:
        Tinted pixmap
    """
    if pixmap.isNull():
        return pixmap
    
    tinted = QPixmap(pixmap.size())
    tinted.fill(Qt.GlobalColor.transparent)
    
    painter = QPainter(tinted)
    painter.drawPixmap(0, 0, pixmap)
    painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
    painter.fillRect(tinted.rect(), color)
    painter.end()
    
    return tinted


def _load_and_scale(path: Path, size: Optional[Tuple[int, int]]) -> QPixmap:
    """
    Load a pixmap and optionally scale it.
    
    Args:
        path: Path to image file
        size: Optional (width, height) tuple for scaling
        
    Returns:
        Loaded (and possibly scaled) pixmap
    """
    pixmap = QPixmap(str(path))
    
    if pixmap.isNull() or size is None:
        return pixmap
    
    return pixmap.scaled(
        QSize(*size),
        Qt.AspectRatioMode.KeepAspectRatio,
        Qt.TransformationMode.SmoothTransformation,
    )


# ==================== Public API ====================

def get_icon(
    filename: str,
    mode: ThemeMode = "light",
    size: Optional[Tuple[int, int]] = None,
    tint: bool = True,
) -> QIcon:
    """
    Load an icon with optional theme-aware tinting.
    
    For UI icons (toolbar, buttons): use tint=True
    For colored icons (defect types): use tint=False
    
    Args:
        filename: Icon filename
        mode: Theme mode ("light" or "dark")
        size: Optional (width, height) for scaling
        tint: Whether to apply theme-based tinting
        
    Returns:
        QIcon (may be null if file not found)
    """
    asset_path = AssetPaths.find_asset(filename)
    pixmap = _load_and_scale(asset_path, size)
    if pixmap.isNull():
        return QIcon()
    
    if tint:
        palette = get_palette(mode)
        tint_color = QColor(palette.icon_tint)
        pixmap = _apply_tint(pixmap, tint_color)
    
    return QIcon(pixmap)


def get_pixmap(
    filename: str,
    mode: ThemeMode = "light",
    size: Optional[Tuple[int, int]] = None,
    tint: bool = True,
) -> QPixmap:
    """
    Load a pixmap with optional theme-aware tinting.
    
    Args:
        filename: Image filename
        mode: Theme mode ("light" or "dark")
        size: Optional (width, height) for scaling
        tint: Whether to apply theme-based tinting
        
    Returns:
        QPixmap (may be null if file not found)
    """
    asset_path = AssetPaths.find_asset(filename)
    if not asset_path:
        return QPixmap()
    
    pixmap = _load_and_scale(asset_path, size)
    if pixmap.isNull():
        return QPixmap()
    
    if tint:
        palette = get_palette(mode)
        tint_color = QColor(palette.icon_tint)
        pixmap = _apply_tint(pixmap, tint_color)
    
    return pixmap


def get_icon_with_color(
    filename: str,
    color: str | QColor,
    size: Optional[Tuple[int, int]] = None,
) -> QIcon:
    """
    Load an icon and tint it with a specific color.
    
    Useful for status indicators or custom-colored icons.
    
    Args:
        filename: Icon filename
        color: Tint color (hex string or QColor)
        size: Optional (width, height) for scaling
        
    Returns:
        QIcon with specified tint
    """
    asset_path = AssetPaths.find_asset(filename)
    if not asset_path:
        return QIcon()
    
    pixmap = _load_and_scale(asset_path, size)
    if pixmap.isNull():
        return QIcon()
    
    if isinstance(color, str):
        color = QColor(color)
    
    pixmap = _apply_tint(pixmap, color)
    return QIcon(pixmap)


def tint_pixmap(pixmap: QPixmap, mode: ThemeMode) -> QPixmap:
    """
    Apply theme-based tint to an existing pixmap.
    
    Args:
        pixmap: Source pixmap
        mode: Theme mode for tint color selection
        
    Returns:
        Tinted pixmap
    """
    if pixmap.isNull():
        return pixmap
    
    palette = get_palette(mode)
    tint_color = QColor(palette.icon_tint)
    return _apply_tint(pixmap, tint_color)


def tint_pixmap_with_color(pixmap: QPixmap, color: str | QColor) -> QPixmap:
    """
    Apply a specific color tint to an existing pixmap.
    
    Args:
        pixmap: Source pixmap
        color: Tint color
        
    Returns:
        Tinted pixmap
    """
    if pixmap.isNull():
        return pixmap
    
    if isinstance(color, str):
        color = QColor(color)
    
    return _apply_tint(pixmap, color)


# ==================== Swatch Icon Generation ====================

def create_color_swatch(
    color: str | QColor,
    size: int = 16,
    checked: bool = False,
    border_color: Optional[str | QColor] = None,
) -> QIcon:
    """
    Create a color swatch icon (for defect type selection).
    
    This replicates the swatch style from DefectTypesPanel and ShapeBox.
    
    Args:
        color: Fill color for the swatch
        size: Swatch size in pixels
        checked: Whether to show checked state (inner square)
        border_color: Border color (defaults to same as fill)
        
    Returns:
        QIcon with the swatch
    """
    if isinstance(color, str):
        color = QColor(color)
    
    if border_color is None:
        border_color = color
    elif isinstance(border_color, str):
        border_color = QColor(border_color)
    
    pm = QPixmap(size, size)
    pm.fill(Qt.GlobalColor.transparent)
    
    painter = QPainter(pm)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
    
    if not checked:
        # Unchecked: solid color fill with border
        painter.fillRect(0, 0, size, size, color)
        painter.setPen(border_color)
        painter.drawRect(0, 0, size - 1, size - 1)
    else:
        # Checked: transparent background, border, inner colored square
        # No white background for dark mode compatibility
        painter.fillRect(0, 0, size, size, Qt.GlobalColor.transparent)
        painter.setPen(border_color)
        painter.drawRect(0, 0, size - 1, size - 1)
        
        margin = 3
        inner_size = size - 2 * margin
        painter.fillRect(margin, margin, inner_size, inner_size, color)
    
    painter.end()
    return QIcon(pm)


# ==================== Initialization Helper ====================

def init_icons(base_dir: Optional[Path] = None) -> None:
    """
    Initialize the icon system with asset paths.
    
    Call this once at application startup.
    
    Args:
        base_dir: Base directory for assets (auto-detected if None)
    """
    AssetPaths.initialize(base_dir)


def add_icon_search_path(path: Path) -> None:
    """
    Add an additional search path for icons.
    
    Args:
        path: Directory path to add
    """
    AssetPaths.add_search_path(path)