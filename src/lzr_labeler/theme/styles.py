from __future__ import annotations

from .palette import ThemePalette


# ==================== Legacy Typography Constants (for backward compatibility) ====================
# These are kept for backward compatibility but you should use palette.font_* instead

FONT_FAMILY = "'Inter', 'Segoe UI', 'Roboto', sans-serif"
FONT_SIZE_XS = "11px"
FONT_SIZE_SM = "12px"
FONT_SIZE_MD = "13px"
FONT_SIZE_LG = "14px"
FONT_SIZE_XL = "16px"
FONT_SIZE_XXL = "18px"


# ==================== Widget Styles ====================

def groupbox_style(p: ThemePalette) -> str:
    """QGroupBox style - used for panels like Settings, Draw Shapes, etc."""
    return f"""
        QGroupBox {{
            color: {p.text_primary};
            font-family: {p.font_family};
            font-size: {p.font_size_md};
            font-weight: 600;
            border: none;
            
        }}
        QGroupBox::title {{
            subcontrol-origin: margin;
            left: 2px;
            padding: 0px 2px;
            background: {p.groupbox_title_bg};
        }}
    """


def groupbox_with_border_style(p: ThemePalette) -> str:
    """QGroupBox with visible border - for contained panels."""
    return f"""
        QGroupBox {{
            color: {p.text_secondary};
            font-family: {p.font_family};
            font-size: {p.font_size_md};
            font-weight: 600;
            border: 2px solid {p.border};
            border-radius: 4px;
            margin-top: 10px;
            padding: 6px;
        }}
        QGroupBox::title {{
            subcontrol-origin: margin;
            left: 8px;
            padding: 0px 4px;
            background: {p.groupbox_title_bg};
            color: {p.text_primary};
        }}
    """


def button_flat_style(p: ThemePalette) -> str:
    """Flat button style - for toolbar/sidebar buttons (SelectionPanel style)."""
    return f"""
        QPushButton {{
            color: {p.text_secondary};
            font-family: {p.font_family};
            font-size: {p.font_size_sm};
            font-weight: 400;
            background-color: transparent;
            text-align: left;
            padding: 4px 6px;
            border: none;
        }}
        QPushButton:hover {{
            background-color: {p.background_hover};
        }}
        QPushButton:pressed {{
            background-color: {p.background_hover};
        }}
        QPushButton:checked {{
            background-color: {p.background_hover};
        }}
        QPushButton:disabled {{
            color: {p.text_disabled};
            background-color: {p.background_disabled};
        }}
    """


def button_flat_special_style(p: ThemePalette, object_name: str) -> str:
    """Special styled flat button (e.g., AI Detect button)."""
    return f"""
        QPushButton#{object_name} {{
            color: {p.accent_text};
            font-weight: 500;
        }}
        QPushButton#{object_name}:hover {{
            background-color: rgba(26, 95, 180, 0.2);
        }}
    """


def button_primary_style(p: ThemePalette) -> str:
    """Primary action button style (PDFViewer buttons, Apply, etc.)."""
    return f"""
        QPushButton {{
            background-color: {p.accent};
            color: {p.text_on_accent};
            font-family: {p.font_family};
            font-size: {p.font_size_sm};
            font-weight: 700;
            border: none;
            padding: 6px 12px;
            border-radius: 4px;
        }}
        QPushButton:hover {{
            background-color: {p.accent_hover};
        }}
        QPushButton:pressed {{
            background-color: {p.accent_pressed};
        }}
        QPushButton:disabled {{
            background-color: {p.border_light};
            color: {p.text_disabled};
        }}
    """


def button_outlined_style(p: ThemePalette) -> str:
    """Outlined button style (MonitoringBox buttons)."""
    return f"""
        QPushButton {{
            color: {p.text_primary};
            font-family: {p.font_family};
            font-size: {p.font_size_sm};
            font-weight: 400;
            background-color: transparent;
            text-align: center;
            padding: 4px 8px;
            border: 1px solid {p.border_light};
        }}
        QPushButton:hover {{
            background-color: {p.background_hover};
            border: 1px solid {p.border_focus};
        }}
        QPushButton:pressed {{
            background-color: {p.background_hover};
            border: 1px solid {p.border_focus};
        }}
        QPushButton:checked {{
            background-color: {p.background_hover};
            border: 1px solid {p.border_focus};
        }}
        QPushButton:disabled {{
            color: {p.text_disabled};
            background-color: {p.background_disabled};
        }}
    """


def label_style(p: ThemePalette) -> str:
    """Standard QLabel style."""
    return f"""
        QLabel {{
            color: {p.text_primary};
            font-family: {p.font_family};
            font-size: {p.font_size_sm};
        }}
    """

def label_secondary_style(p: ThemePalette, selector: str = "QLabel") -> str:
    return f"""
        {selector} {{
            color: {p.text_secondary};
            font-family: {p.font_family};
            font-size: {p.font_size_sm};
            font-weight: 500;
        }}
    """

def label_accent_style(p: ThemePalette, selector: str = "QLabel") -> str:
    return f"""
        {selector} {{
            color: {p.accent_text};
            font-family: {p.font_family};
            font-size: {p.font_size_sm};
            font-weight: 600;
            min-width: 40px;
        }}
    """

def slider_style(p: ThemePalette) -> str:
    """QSlider horizontal style (Settings, PDFViewer)."""
    return f"""
        QSlider::groove:horizontal {{
            height: 6px;
            background: {p.background_input};
            border-radius: 3px;
        }}
        QSlider::handle:horizontal {{
            background: {p.accent};
            width: 16px;
            height: 16px;
            margin: -5px 0;
            border-radius: 8px;
        }}
        QSlider::handle:horizontal:hover {{
            background: {p.accent_hover};
        }}
        QSlider::sub-page:horizontal {{
            background: {p.accent_light};
            border-radius: 3px;
        }}
    """


def slider_thin_style(p: ThemePalette) -> str:
    """Thinner slider style (PDFViewer zoom)."""
    return f"""
        QSlider::groove:horizontal {{
            height: 6px;
            background: {p.scrollbar_track};
            border-radius: 3px;
        }}
        QSlider::handle:horizontal {{
            background: {p.accent};
            width: 14px;
            margin: -4px 0;
            border-radius: 7px;
        }}
        QSlider::handle:horizontal:hover {{
            background: {p.accent_hover};
        }}
    """


def listwidget_style(p: ThemePalette) -> str:
    """QListWidget style (CurrentLabelBox)."""
    return f"""
        QListWidget {{
            border: none;
            background: {p.background};
        }}
        QListWidget::item {{
            padding: 2px;
        }}
        QListWidget::item:focus {{
            outline: none;
       }}
    """


def scrollarea_style(p: ThemePalette) -> str:
    """QScrollArea style (DefectTypesPanel, etc.)."""
    return f"""
        QScrollArea {{
            border: none;
            background: transparent;
        }}
        QScrollArea > QWidget > QWidget {{
            background: transparent;
        }}
    """


def scrollarea_bordered_style(p: ThemePalette) -> str:
    """Bordered QScrollArea style (PDFViewer)."""
    return f"""
        QScrollArea {{
            border: 1px solid {p.border_light};
            background-color: {p.background_input};
        }}
    """


def dialog_style(p: ThemePalette) -> str:
    """QDialog base style."""
    return f"""
        QDialog {{
            background-color: {p.background_dialog};
        }}
    """


def frame_separator_style(p: ThemePalette) -> str:
    """QFrame separator line style."""
    return f"""
        QFrame[frameShape="4"] {{
            background: {p.separator};
            border: none;
            max-height: 1px;
        }}
        QFrame[frameShape="5"] {{
            background: {p.separator};
            border: none;
            max-width: 1px;
        }}
    """


def frame_viewport_overlay_style(p: ThemePalette) -> str:
    """Viewport overlay frame (MonitoringBox)."""
    return f"""
        QFrame {{
            border: 2px solid {p.overlay_viewport};
            background: transparent;
        }}
    """


def lineedit_style(p: ThemePalette) -> str:
    """QLineEdit style."""
    return f"""
        QLineEdit {{
            color: {p.text_primary};
            background-color: {p.background_card};
            border: 1px solid {p.border};
            border-radius: 4px;
            padding: 4px 8px;
            font-family: {p.font_family};
            font-size: {p.font_size_sm};
        }}
        QLineEdit:focus {{
            border: 1px solid {p.border_focus};
        }}
        QLineEdit:disabled {{
            background-color: {p.background_disabled};
            color: {p.text_disabled};
        }}
        QLineEdit::placeholder {{
            color: {p.text_placeholder};
        }}
    """


def combobox_style(p: ThemePalette) -> str:
    """QComboBox style."""
    return f"""
        QComboBox {{
            color: {p.text_primary};
            background-color: {p.background_card};
            border: 1px solid {p.border};
            border-radius: 4px;
            padding: 4px 8px;
            font-family: {p.font_family};
            font-size: {p.font_size_sm};
            min-width: 80px;
        }}
        QComboBox:hover {{
            border: 1px solid {p.border_focus};
        }}
        QComboBox:disabled {{
            background-color: {p.background_disabled};
            color: {p.text_disabled};
        }}
        QComboBox::drop-down {{
            border: none;
            width: 20px;
        }}
        QComboBox QAbstractItemView {{
            color: {p.text_primary};
            background-color: {p.background_card};
            border: 1px solid {p.border};
            selection-background-color: {p.background_selected};
        }}
    """


def checkbox_style(p: ThemePalette) -> str:
    """QCheckBox style."""
    return f"""
        QCheckBox {{
            color: {p.text_primary};
            font-family: {p.font_family};
            font-size: {p.font_size_sm};
            spacing: 6px;
        }}
        QCheckBox::indicator {{
            width: 16px;
            height: 16px;
            border: 1px solid {p.border_light};
            border-radius: 3px;
            background: {p.background_card};
        }}
        QCheckBox::indicator:hover {{
            border: 1px solid {p.border_focus};
        }}
        QCheckBox::indicator:checked {{
            background: {p.accent};
            border: 1px solid {p.accent};
        }}
        QCheckBox::indicator:disabled {{
            background: {p.background_disabled};
            border: 1px solid {p.border};
        }}
    """


def radiobutton_style(p: ThemePalette) -> str:
    """
    QRadioButton label style (for use with custom indicator styles too).
    ShapeBox draws the indicator via QProxyStyle (SquareRadioStyle),
    so we don't style ::indicator here.
    """
    return f"""
        QRadioButton {{
            color: {p.text_secondary};
            font-family: {p.font_family};
            font-size: {p.font_size_sm};
            spacing: 6px;
        }}
        QRadioButton:disabled {{
            color: {p.text_disabled};
        }}
    """


def toolbutton_swatch_style(p: ThemePalette) -> str:
    """QToolButton swatch style (DefectTypesPanel color swatches)."""
    return f"""
        QToolButton[defect_swatch="true"] {{
            border: none;
            padding: 0px;
            margin: 0px;
            min-width: 16px;
            min-height: 16px;
            max-width: 16px;
            max-height: 16px;
            background-color: transparent;
        }}
    """


def scrollbar_style(p: ThemePalette, selector: str = "QScrollBar") -> str:
    return f"""
        {selector}:vertical {{
            background: {p.scrollbar_track};
            width: 10px;
            margin: 0px;
            border-radius: 5px;
        }}
        {selector}::handle:vertical {{
            background: {p.scrollbar_handle};
            min-height: 30px;
            border-radius: 5px;
        }}
        {selector}::handle:vertical:hover {{
            background: {p.accent_hover};
        }}
        {selector}::add-line:vertical, {selector}::sub-line:vertical {{
            height: 0px;
        }}
        {selector}::add-page:vertical, {selector}::sub-page:vertical {{
            background: none;
        }}

        {selector}:horizontal {{
            background: {p.scrollbar_track};
            height: 10px;
            margin: 0px;
            border-radius: 5px;
        }}
        {selector}::handle:horizontal {{
            background: {p.scrollbar_handle};
            min-width: 30px;
            border-radius: 5px;
        }}
        {selector}::handle:horizontal:hover {{
            background: {p.accent_hover};
        }}
        {selector}::add-line:horizontal, {selector}::sub-line:horizontal {{
            width: 0px;
        }}
        {selector}::add-page:horizontal, {selector}::sub-page:horizontal {{
            background: none;
        }}
    """


def menu_style(p: ThemePalette) -> str:
    """QMenu style (context menus)."""
    return f"""
        QMenu {{
            background: {p.background_card};
            color: {p.text_primary};
            border: 1px solid {p.border};
            border-radius: 8px;
            padding: 4px;
        }}
        QMenu::item {{
            padding: 4px 16px;
            border-radius: 4px;
        }}
        QMenu::item:selected {{
            background: {p.accent};
            color: {p.text_on_accent};
        }}
        QMenu::separator {{
            height: 1px;
            background: {p.separator};
            margin: 4px 8px;
        }}
    """


def tooltip_style(p: ThemePalette) -> str:
    """QToolTip style."""
    return f"""
        QToolTip {{
            color: {p.text_primary};
            background-color: {p.background_card};
            border: 1px solid {p.border};
            border-radius: 4px;
            padding: 4px 8px;
            font-family: {p.font_family};
            font-size: {p.font_size_sm};
        }}
    """


def messagebox_style(p: ThemePalette) -> str:
    """QMessageBox style."""
    return f"""
        QMessageBox {{
            background-color: {p.background_dialog};
        }}
        QMessageBox QLabel {{
            color: {p.text_primary};
            font-family: {p.font_family};
            font-size: {p.font_size_sm};
        }}
        QMessageBox QPushButton {{
            min-width: 70px;
        }}
    """


def inputdialog_style(p: ThemePalette) -> str:
    """QInputDialog style."""
    return f"""
        QInputDialog {{
            background-color: {p.background_dialog};
        }}
        QInputDialog QLabel {{
            color: {p.text_primary};
            font-family: {p.font_family};
            font-size: {p.font_size_sm};
        }}
        QInputDialog QLineEdit {{
            color: {p.text_primary};
            background-color: {p.background_card};
            border: 1px solid {p.border};
            border-radius: 4px;
            padding: 4px 8px;
        }}
    """


def mainwindow_style(p: ThemePalette) -> str:
    """QMainWindow base style."""
    return f"""
        QMainWindow {{
            background-color: {p.background};
        }}
    """


def widget_base_style(p: ThemePalette) -> str:
    """Base QWidget style."""
    return f"""
        QWidget {{
            background-color: {p.background};
            color: {p.text_primary};
            font-family: {p.font_family};
        }}
    """


# ==================== Combined Stylesheet Generator ====================

def generate_full_stylesheet(p: ThemePalette) -> str:
    """
    Generate complete application stylesheet.
    
    This combines all widget styles into a single QSS string
    that can be applied to QApplication.
    
    NOTE: This is a MINIMAL base stylesheet. Widget-specific styles
    should be applied by individual widgets using the style functions.
    """
    return "\n".join([
        widget_base_style(p),
        mainwindow_style(p),
        scrollbar_style(p),
        menu_style(p),
        tooltip_style(p),
    ])


def generate_minimal_stylesheet(p: ThemePalette) -> str:
    """
    Generate minimal stylesheet - only colors and fonts, no widget-specific styles.
    
    Use this when widgets have their own _apply_styles() methods.
    """
    return f"""
        QWidget {{
            background-color: {p.background};
            color: {p.text_primary};
            font-family: {p.font_family};
        }}
        QMainWindow {{
            background-color: {p.background};
        }}
        QMenu {{
            background: {p.background_card};
            color: {p.text_primary};
            border: 1px solid {p.border};
            border-radius: 8px;
            padding: 4px;
        }}
        QMenu::item {{
            padding: 4px 16px;
            border-radius: 4px;
        }}
        QMenu::item:selected {{
            background: {p.accent};
            color: {p.text_on_accent};
        }}
        QToolTip {{
            color: {p.text_primary};
            background-color: {p.background_card};
            border: 1px solid {p.border};
            border-radius: 4px;
            padding: 4px 8px;
        }}
        QScrollBar:vertical {{
            background: {p.scrollbar_track};
            width: 10px;
            border-radius: 5px;
        }}
        QScrollBar::handle:vertical {{
            background: {p.scrollbar_handle};
            min-height: 30px;
            border-radius: 5px;
        }}
        QScrollBar::handle:vertical:hover {{
            background: {p.accent_hover};
        }}
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
            height: 0px;
        }}
        QScrollBar:horizontal {{
            background: {p.scrollbar_track};
            height: 10px;
            border-radius: 5px;
        }}
        QScrollBar::handle:horizontal {{
            background: {p.scrollbar_handle};
            min-width: 30px;
            border-radius: 5px;
        }}
        QScrollBar::handle:horizontal:hover {{
            background: {p.accent_hover};
        }}
        QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
            width: 0px;
        }}
    """


def generate_dialog_stylesheet(p: ThemePalette) -> str:
    """Generate stylesheet for dialogs."""
    return "\n".join([
        dialog_style(p),
        button_primary_style(p),
        slider_thin_style(p),
        scrollbar_style(p, selector="QListWidget QScrollBar"),
        label_style(p),
    ])