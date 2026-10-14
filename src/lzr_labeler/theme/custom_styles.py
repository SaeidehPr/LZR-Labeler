from __future__ import annotations

from PySide6.QtWidgets import QProxyStyle, QStyle, QStyleFactory
from PySide6.QtCore import Qt, QRect
from PySide6.QtGui import QPainter, QColor, QPen, QBrush

from .palette import get_palette, ThemeMode


class SquareRadioStyle(QProxyStyle):
    def __init__(
        self,
        base_style=None,
        mode: ThemeMode = "light",
        accent_color: str | None = None,
    ):
        super().__init__(base_style)
        
        self._mode = mode
        palette = get_palette(mode)
        
        if accent_color:
            self._color = QColor(accent_color)
        else:
            # Use a lighter blue similar to LZR Labelr: #6EA0E1
            self._color = QColor("#6EA0E1")
        
        # Background color for checked state (transparent for both modes)
        self._checked_bg = Qt.GlobalColor.transparent
    
    def pixelMetric(self, metric, option=None, widget=None) -> int:
        """Force 16x16 indicator size."""
        if metric in (
            QStyle.PixelMetric.PM_ExclusiveIndicatorWidth,
            QStyle.PixelMetric.PM_ExclusiveIndicatorHeight,
        ):
            return 16
        return super().pixelMetric(metric, option, widget)
    
    def drawPrimitive(self, element, option, painter: QPainter, widget=None) -> None:
        """Draw custom square radio indicator."""
        if element != QStyle.PrimitiveElement.PE_IndicatorRadioButton:
            super().drawPrimitive(element, option, painter, widget)
            return
        
        r = option.rect
        
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        
        # Extract states
        checked = bool(option.state & QStyle.StateFlag.State_On)
        hovered = bool(option.state & QStyle.StateFlag.State_MouseOver)
        enabled = bool(option.state & QStyle.StateFlag.State_Enabled)
        
        # Adjust color for disabled state
        c = QColor(self._color)
        if not enabled:
            c.setAlpha(120)
        
        if not checked:
            # Unchecked: transparent background + colored border
            painter.fillRect(r, Qt.GlobalColor.transparent)
            painter.setPen(c)
            painter.drawRect(r.adjusted(0, 0, -1, -1))
            
            # Hover: light blue fill
            if hovered:
                hover_fill = QColor(c)
                hover_fill.setAlphaF(0.20)
                painter.fillRect(r.adjusted(1, 1, -1, -1), hover_fill)
        else:
            # Checked: transparent background + border + inner colored square
            # No white background - keeps the parent's background visible
            painter.fillRect(r, Qt.GlobalColor.transparent)
            painter.setPen(c)
            painter.drawRect(r.adjusted(0, 0, -1, -1))
            
            # Inner square
            margin = 3
            inner = QRect(
                r.left() + margin,
                r.top() + margin,
                r.width() - 2 * margin,
                r.height() - 2 * margin,
            )
            painter.fillRect(inner, self._color)
        
        painter.restore()


class SquareCheckboxStyle(QProxyStyle):
    """
    Custom square checkbox indicator style.
    
    Similar to SquareRadioStyle but for checkboxes.
    Can be used for consistent square indicators across the app.
    """
    
    def __init__(
        self,
        base_style=None,
        mode: ThemeMode = "light",
        accent_color: str | None = None,
    ):
        super().__init__(base_style)
        
        self._mode = mode
        palette = get_palette(mode)
        
        if accent_color:
            self._color = QColor(accent_color)
        else:
            self._color = QColor("#6EA0E1")
    
    def pixelMetric(self, metric, option=None, widget=None) -> int:
        """Force 16x16 indicator size."""
        if metric in (
            QStyle.PixelMetric.PM_IndicatorWidth,
            QStyle.PixelMetric.PM_IndicatorHeight,
        ):
            return 16
        return super().pixelMetric(metric, option, widget)
    
    def drawPrimitive(self, element, option, painter: QPainter, widget=None) -> None:
        """Draw custom square checkbox indicator."""
        if element != QStyle.PrimitiveElement.PE_IndicatorCheckBox:
            super().drawPrimitive(element, option, painter, widget)
            return
        
        r = option.rect
        
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        
        checked = bool(option.state & QStyle.StateFlag.State_On)
        hovered = bool(option.state & QStyle.StateFlag.State_MouseOver)
        enabled = bool(option.state & QStyle.StateFlag.State_Enabled)
        
        c = QColor(self._color)
        if not enabled:
            c.setAlpha(120)
        
        if not checked:
            painter.fillRect(r, Qt.GlobalColor.transparent)
            painter.setPen(c)
            painter.drawRect(r.adjusted(0, 0, -1, -1))
            
            if hovered:
                hover_fill = QColor(c)
                hover_fill.setAlphaF(0.20)
                painter.fillRect(r.adjusted(1, 1, -1, -1), hover_fill)
        else:
            # Transparent background for dark mode compatibility
            painter.fillRect(r, Qt.GlobalColor.transparent)
            painter.setPen(c)
            painter.drawRect(r.adjusted(0, 0, -1, -1))
            
            margin = 3
            inner = QRect(
                r.left() + margin,
                r.top() + margin,
                r.width() - 2 * margin,
                r.height() - 2 * margin,
            )
            painter.fillRect(inner, self._color)
        
        painter.restore()

class ToggleSwitchStyle(QProxyStyle):
    """
    Custom toggle switch indicator style for a QCheckBox.
    Draws a pill track + circular knob (NO BORDER).
    """

    INDICATOR_W = 48
    INDICATOR_H = 22
    KNOB_MARGIN = 3        
    KNOB_INSET = 6        

    def __init__(self, base_style=None, mode: "ThemeMode" = "light"):
        super().__init__(base_style)
        self._mode: "ThemeMode" = mode

    def set_mode(self, mode: "ThemeMode") -> None:
        self._mode = mode

    def pixelMetric(self, metric, option=None, widget=None) -> int:
        if metric == QStyle.PixelMetric.PM_IndicatorWidth:
            return self.INDICATOR_W
        if metric == QStyle.PixelMetric.PM_IndicatorHeight:
            return self.INDICATOR_H
        return super().pixelMetric(metric, option, widget)

    def drawPrimitive(self, element, option, painter: QPainter, widget=None) -> None:
        if element != QStyle.PrimitiveElement.PE_IndicatorCheckBox:
            return super().drawPrimitive(element, option, painter, widget)

        p = get_palette(self._mode)

        r = option.rect
        checked = bool(option.state & QStyle.StateFlag.State_On)
        hovered = bool(option.state & QStyle.StateFlag.State_MouseOver)
        enabled = bool(option.state & QStyle.StateFlag.State_Enabled)

        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        # Colors
        track_off = QColor(p.background_input)
        track_on = QColor(p.background_input)
        knob = QColor(p.accent)

        # Disabled
        if not enabled:
            track_off.setAlpha(120)
            track_on.setAlpha(120)
            knob.setAlpha(180)

        # Hover 
        if hovered:
            c = QColor(track_on if checked else track_off)
            c.setAlpha(min(255, c.alpha() + 25))
            if checked:
                track_on = c
            else:
                track_off = c

        # Track (pill) - NO BORDER
        radius = r.height() / 2.0
        painter.setPen(QStyle.PE_Widget) 
        painter.setPen(Qt.PenStyle.NoPen)  
        painter.setBrush(QBrush(track_on if checked else track_off))
        painter.drawRoundedRect(r.adjusted(0, 0, -1, -1), radius, radius)

        # Knob (circle) - NO BORDER
        knob_d = r.height() - self.KNOB_INSET
        y = r.top() + (r.height() - knob_d) / 2
        x = r.right() - knob_d - self.KNOB_MARGIN if checked else r.left() + self.KNOB_MARGIN

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(knob))
        painter.drawEllipse(QRect(int(x), int(y), int(knob_d), int(knob_d)))

        painter.restore()

    def subElementRect(self, element, option, widget=None):
        if element == QStyle.SubElement.SE_CheckBoxIndicator:
            r = super().subElementRect(element, option, widget)
            w, h = self.INDICATOR_W, self.INDICATOR_H
            y = r.top() + (r.height() - h) // 2
            return QRect(r.left(), y, w, h)
        return super().subElementRect(element, option, widget)

    def sizeFromContents(self, ct, option, contentsSize, widget=None):
        if ct == QStyle.ContentsType.CT_CheckBox:
            sz = super().sizeFromContents(ct, option, contentsSize, widget)
            sz.setWidth(max(sz.width(), self.INDICATOR_W))
            sz.setHeight(max(sz.height(), self.INDICATOR_H))
            return sz
        return super().sizeFromContents(ct, option, contentsSize, widget)

def create_square_radio_style(
    widget,
    mode: ThemeMode = "light",
    accent_color: str | None = None,
) -> SquareRadioStyle:
    """
    Factory function to create a SquareRadioStyle.
    
    Args:
        widget: Widget to get base style from
        mode: Theme mode
        accent_color: Optional custom accent color
        
    Returns:
        Configured SquareRadioStyle instance
    """
    return SquareRadioStyle(
        base_style=QStyleFactory.create("Fusion"),
        mode=mode,
        accent_color=accent_color,
    )


def create_square_checkbox_style(
    widget,
    mode: ThemeMode = "light",
    accent_color: str | None = None,
) -> SquareCheckboxStyle:
    """
    Factory function to create a SquareCheckboxStyle.
    
    Args:
        widget: Widget to get base style from
        mode: Theme mode
        accent_color: Optional custom accent color
        
    Returns:
        Configured SquareCheckboxStyle instance
    """
    return SquareCheckboxStyle(
        base_style=QStyleFactory.create("Fusion"),
        mode=mode,
        accent_color=accent_color,
    )

def create_toggle_switch_style(
    widget,
    mode: ThemeMode = "light",
) -> ToggleSwitchStyle:
    return ToggleSwitchStyle(
        base_style=QStyleFactory.create("Fusion"),
        mode=mode,
    )
