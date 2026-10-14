from __future__ import annotations

from typing import List, Dict, Optional, Tuple, Any, Literal

from PySide6.QtWidgets import (
    QGraphicsView,
    QGraphicsScene,
    QGraphicsPathItem,
    QGraphicsItem,
    QGraphicsRectItem,
    QGraphicsEllipseItem,
    QGraphicsSimpleTextItem,
    QStyleOptionGraphicsItem,
    QGraphicsLineItem,
)
from PySide6.QtGui import (
    QImage,
    QColor,
    QPen,
    QBrush,
    QPolygonF,
    QPainterPath,
    QKeyEvent,
    QFont,
    QPainter,
)
from PySide6.QtCore import Qt, QRectF, QPointF, Signal, QTimer

from lzr_labeler.core.shapes import BaseShape, RectShape, CircleShape, PolygonShape, ShapeModel


OpState = Literal["idle", "move", "resize", "pan", "draw"]

class QImageItem(QGraphicsItem):
    def __init__(self, image: QImage | None = None):
        super().__init__()
        self._image: QImage | None = image
        self.setCacheMode(QGraphicsItem.NoCache)

    def set_image(self, image: QImage | None) -> None:
        self.prepareGeometryChange()
        self._image = image
        self.update()

    def image(self) -> QImage | None:
        return self._image

    def boundingRect(self) -> QRectF:
        if self._image is None or self._image.isNull():
            return QRectF()
        return QRectF(0, 0, self._image.width(), self._image.height())

    def paint(self, painter: QPainter, option: QStyleOptionGraphicsItem, widget=None) -> None:
        if self._image is None or self._image.isNull():
            return
        exposed = option.exposedRect.intersected(self.boundingRect())
        if exposed.isEmpty():
            return
        painter.drawImage(exposed, self._image, exposed)



class Canvas(QGraphicsView):
    # ==================== Constants ====================
    MIN_ZOOM = 0.02
    MAX_ZOOM = 30.0
    DEFAULT_LABEL = "Unbeschriftet"
    DEFAULT_COLOR = "#FFEE00"

    # ==================== Signals ====================
    annotationModeChanged = Signal(bool)
    editModeChanged = Signal(bool)
    shapesChanged = Signal()
    zoomChanged = Signal(float, float, float, str)
    viewportChanged = Signal(float, float, float, float)  # nx, ny, nw, nh
    applyRequested = Signal()

    def __init__(self, parent=None, shape_manager: ShapeModel | None = None) -> None:
        super().__init__(parent)

        self._shape_manager: ShapeModel | None = shape_manager
        self._scene = QGraphicsScene(self)
        self.setScene(self._scene)
        self._image_item: QImageItem | None = None

        # Zoom
        self._zoom: float = 1.0
        self._mode: str = "fit"  # 'fit' or 'free'

        self._min_zoom: float = self.MIN_ZOOM
        self._max_zoom: float = self.MAX_ZOOM

        # Modes
        self._draw_enabled: bool = False
        self._edit_enabled: bool = False
        self._shape_mode: str = "rect"  # rect / circle / poly

        # Active label/color (for external use)
        self._current_label: str = self.DEFAULT_LABEL
        self._current_color: str = self.DEFAULT_COLOR

        # Temp drawing state
        self._drag_start_scene: Optional[QPointF] = None
        self._temp_item: Optional[QGraphicsItem] = None
        self._circle_center: Optional[QPointF] = None

        # Polygon temp
        self._poly_points: List[QPointF] = []
        self._poly_temp_item: Optional[QGraphicsPathItem] = None
        self._poly_mouse_scene: Optional[QPointF] = None
        self._poly_handle_items: List[QGraphicsItem] = []

        # Grid
        self._grid_divisions: int = 1
        self._current_cell: Optional[tuple[int, int]] = None

        # Shape maps (sid = id(shape))
        self._shape_items: Dict[int, QGraphicsItem] = {}
        self._handle_items: Dict[int, List[QGraphicsItem]] = {}
        self._label_items: Dict[int, List[QGraphicsItem]] = {}
        self._cross_items: Dict[int, List[QGraphicsLineItem]] = {}
        self._shape_by_id: Dict[int, BaseShape] = {}

        # Selection
        self._selected_shape: Optional[BaseShape] = None
        self._selected_shape_ids: set[int] = set()
        self._hover_shape: Optional[BaseShape] = None

        # Clipboard
        self._clipboard: List[BaseShape] = []
        self._paste_offset: float = 20.0
        self._paste_count: int = 0

        # Operation state machine
        self._op: OpState = "idle"
        self._drag_last_scene: Optional[QPointF] = None

        # Resize info
        self._resize_sid: Optional[int] = None
        self._resize_handle_index: Optional[int] = None
        self._resize_group: List[int] = []
        self._resize_anchor: Optional[Dict[str, Any]] = None

        # Pan state
        self._pan_last_view: Optional[QPointF] = None

        # Undo / Redo
        self.MAX_HISTORY = 50
        self._undo_stack: list[list[BaseShape]] = []
        self._redo_stack: list[list[BaseShape]] = []
        self._history_blocked: bool = False
        self._pending_snapshot: Optional[list[BaseShape]] = None
        self._pending_changed: bool = False

        # Unlabeled blink
        self._unlabeled_timer = QTimer(self)
        self._unlabeled_timer.setInterval(350)
        self._unlabeled_timer.timeout.connect(self._unlabeled_tick)
        self._unlabeled_on: bool = False
        self._unlabeled_blinking_sids: set[int] = set()

        # Label blink
        self._label_blink_timer: Optional[QTimer] = None
        self._label_blink_sids: list[int] = []
        self._label_blink_phase: int = 0
        self._label_blink_cycles: int = 0

        # Attention blink selection restore
        self._attention_prev_selected_ids: set[int] = set()
        self._attention_prev_selected_shape: Optional[BaseShape] = None

        # View settings
        self._setup_view()

        # Keyboard move (undo)
        self._kb_move_timer = QTimer(self)
        self._kb_move_timer.setSingleShot(True)
        self._kb_move_timer.setInterval(180)
        self._kb_move_timer.timeout.connect(self._commit_keyboard_move)
        self._kb_pending_snapshot: Optional[list[BaseShape]] = None
        self._kb_pending_changed: bool = False

        # Viewport sync (debounced)
        self._viewport_debounce = QTimer(self)
        self._viewport_debounce.setSingleShot(True)
        self._viewport_debounce.setInterval(0)
        self._viewport_debounce.timeout.connect(self._emit_viewport_changed)

    # ==================== Setup ====================

    def _setup_view(self) -> None:
        """Configure view settings."""
        self.setRenderHint(QPainter.Antialiasing, True)
        self.setRenderHint(QPainter.SmoothPixmapTransform, True)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.AnchorViewCenter)
        self.setBackgroundBrush(Qt.lightGray)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setMouseTracking(True)
        self.setDragMode(QGraphicsView.NoDrag)
        self._apply_cursor(None)
        self.horizontalScrollBar().valueChanged.connect(self._request_viewport_emit)
        self.verticalScrollBar().valueChanged.connect(self._request_viewport_emit)

    # ==================== Helper Methods ====================

    def _request_viewport_emit(self, *args) -> None:
        # debounce to coalesce multiple updates in the same event loop
        if hasattr(self, "_viewport_debounce"):
            self._viewport_debounce.start()

    def _make_pen(
        self,
        color: QColor | str,
        width: int = 2,
        style: Qt.PenStyle = Qt.SolidLine
    ) -> QPen:
        """Create a cosmetic pen with given parameters."""
        if not isinstance(color, QColor):
            color = QColor(color)
        pen = QPen(color)
        pen.setWidth(width)
        pen.setStyle(style)
        pen.setCosmetic(True)
        return pen

    def _norm_rect(self, x1: float, y1: float, x2: float, y2: float) -> QRectF:
        """Normalize coordinates to proper rectangle."""
        return QRectF(
            min(x1, x2),
            min(y1, y2),
            abs(x2 - x1),
            abs(y2 - y1)
        )

    def _make_polygon_path(self, points: list[tuple[float, float]]) -> QPainterPath:
        """Create closed polygon path from points."""
        poly = QPolygonF([QPointF(x, y) for x, y in points])
        path = QPainterPath()
        path.addPolygon(poly)
        path.closeSubpath()
        return path

    def _set_shape_opacity(self, sid: int, opacity: float = 1.0) -> None:
        """Set opacity for shape and all its related items."""
        item = self._shape_items.get(sid)
        if item:
            try:
                item.setOpacity(opacity)
            except RuntimeError:
                pass

        for it in self._label_items.get(sid, []):
            try:
                it.setOpacity(opacity)
            except RuntimeError:
                pass

        for ln in self._cross_items.get(sid, []):
            try:
                ln.setOpacity(opacity)
            except RuntimeError:
                pass

    def _can_mouse_move(self) -> bool:
        return self._edit_enabled

    def _can_keyboard_move(self) -> bool:
        return self._edit_enabled or self._draw_enabled

    def _can_resize(self) -> bool:
        return self._edit_enabled

    # ==================== Cursor Management ====================

    def _apply_cursor(self, scene_pos: Optional[QPointF]) -> None:
        """Set viewport cursor based on current mode/operation."""
        if self._draw_enabled:
            self.viewport().setCursor(Qt.ArrowCursor)
            return

        if self._op in ("move", "pan"):
            self.viewport().setCursor(Qt.ClosedHandCursor)
            return

        if self._op == "resize":
            self._apply_resize_cursor(scene_pos)
            return

        if self._edit_enabled and scene_pos is not None:
            if self._apply_hover_cursor(scene_pos):
                return

        self.viewport().setCursor(Qt.OpenHandCursor)

    def _apply_resize_cursor(self, scene_pos: Optional[QPointF]) -> None:
        """Apply appropriate resize cursor."""
        if scene_pos is not None and self._resize_sid is not None:
            shape = self._shape_by_id.get(self._resize_sid)

            if isinstance(shape, CircleShape):
                self.viewport().setCursor(self._cursor_for_circle_perimeter(shape, scene_pos))
                return

            if isinstance(shape, PolygonShape) and self._resize_handle_index is not None:
                self.viewport().setCursor(self._cursor_for_polygon_vertex(shape, self._resize_handle_index))
                return

            if self._resize_handle_index is not None:
                self.viewport().setCursor(self._cursor_for_handle_index(self._resize_handle_index))
                return

        self.viewport().setCursor(Qt.SizeAllCursor)

    def _apply_hover_cursor(self, scene_pos: QPointF) -> bool:
        """Apply cursor for hover state. Returns True if cursor was set."""
        hit = self._hit_test_any_handle(scene_pos)
        if hit is not None:
            sid, idx = hit
            shape = self._shape_by_id.get(sid)

            if isinstance(shape, CircleShape):
                self.viewport().setCursor(self._cursor_for_circle_perimeter(shape, scene_pos))
            elif isinstance(shape, PolygonShape):
                self.viewport().setCursor(self._cursor_for_polygon_vertex(shape, idx))
            else:
                self.viewport().setCursor(self._cursor_for_handle_index(idx))
            return True

        hit2 = self._hit_test_circle_perimeter(scene_pos)
        if hit2 is not None:
            sid, _ = hit2
            shape = self._shape_by_id.get(sid)
            if isinstance(shape, CircleShape):
                self.viewport().setCursor(self._cursor_for_circle_perimeter(shape, scene_pos))
                return True

        return False

    def _cursor_for_handle_index(self, idx: int) -> Qt.CursorShape:
        """Get cursor for rectangle handle index."""
        return Qt.SizeFDiagCursor if idx in (0, 2) else Qt.SizeBDiagCursor

    def _cursor_for_circle_perimeter(self, shape: CircleShape, scene_pos: QPointF) -> Qt.CursorShape:
        """Get cursor for circle perimeter based on angle."""
        import math

        dx = scene_pos.x() - shape.cx
        dy = scene_pos.y() - shape.cy

        if abs(dx) < 1e-6 and abs(dy) < 1e-6:
            return Qt.SizeAllCursor

        ang = (math.degrees(math.atan2(dy, dx)) + 360.0) % 360.0

        if (ang >= 337.5 or ang < 22.5) or (157.5 <= ang < 202.5):
            return Qt.SizeHorCursor
        if (67.5 <= ang < 112.5) or (247.5 <= ang < 292.5):
            return Qt.SizeVerCursor
        if (22.5 <= ang < 67.5) or (202.5 <= ang < 247.5):
            return Qt.SizeFDiagCursor
        return Qt.SizeBDiagCursor

    def _cursor_for_polygon_vertex(self, shape: PolygonShape, idx: int) -> Qt.CursorShape:
        """Get cursor for polygon vertex."""
        pts = [QPointF(x, y) for x, y in shape.points]
        if not pts or idx < 0 or idx >= len(pts):
            return Qt.SizeAllCursor

        center = QPolygonF(pts).boundingRect().center()
        p = pts[idx]
        dx, dy = p.x() - center.x(), p.y() - center.y()

        if abs(dx) < 1e-6 and abs(dy) < 1e-6:
            return Qt.SizeAllCursor

        if (dx >= 0 and dy >= 0) or (dx < 0 and dy < 0):
            return Qt.SizeFDiagCursor
        return Qt.SizeBDiagCursor

    def _reset_operation_state(self) -> None:
        """Reset operation state to idle."""
        self._op = "idle"
        self._drag_last_scene = None
        self._resize_sid = None
        self._resize_handle_index = None
        self._resize_group = []
        self._resize_anchor = None
        self._pan_last_view = None

    # ==================== Hit Testing ====================

    def _hit_test_any_handle(self, scene_pos: QPointF) -> Optional[tuple[int, int]]:
        """Test if position hits any handle of selected shapes."""
        for sid, handles in self._handle_items.items():
            if sid not in self._selected_shape_ids:
                continue
            for idx, h in enumerate(handles):
                if h.contains(h.mapFromScene(scene_pos)):
                    return sid, idx
        return None

    def _hit_test_circle_perimeter(self, scene_pos: QPointF) -> Optional[tuple[int, int]]:
        """Test if position hits circle perimeter."""
        tol = 8.0 / max(self._zoom, 0.001)

        for sid in list(self._selected_shape_ids):
            shape = self._shape_by_id.get(sid)
            if not isinstance(shape, CircleShape):
                continue

            dx = scene_pos.x() - shape.cx
            dy = scene_pos.y() - shape.cy
            dist = (dx * dx + dy * dy) ** 0.5

            if abs(dist - shape.r) <= tol:
                return sid, 0

        return None

    def _shape_contains_point(self, shape: BaseShape, pos: QPointF) -> bool:
        """Check if shape contains point."""
        if isinstance(shape, RectShape):
            return self._norm_rect(shape.x1, shape.y1, shape.x2, shape.y2).contains(pos)

        if isinstance(shape, CircleShape):
            dx, dy = pos.x() - shape.cx, pos.y() - shape.cy
            return dx * dx + dy * dy <= shape.r * shape.r

        if isinstance(shape, PolygonShape):
            poly = QPolygonF([QPointF(x, y) for x, y in shape.points])
            return poly.containsPoint(pos, Qt.OddEvenFill)

        return False
    
    def _shape_area(self, shape) -> float:
        if isinstance(shape, RectShape):
            return abs((shape.x2 - shape.x1) * (shape.y2 - shape.y1))

        if isinstance(shape, CircleShape):
            return shape.r * shape.r

        if isinstance(shape, PolygonShape):
            pts = shape.points
            if len(pts) < 3:
                return float("inf")

            # Shoelace formula
            area2 = 0.0
            for i in range(len(pts)):
                x1, y1 = pts[i]
                x2, y2 = pts[(i + 1) % len(pts)]
                area2 += x1 * y2 - x2 * y1
            return abs(area2) / 2.0

        return float("inf")

    def _find_shape_at(self, pos: QPointF):
        """Find topmost shape at position."""
        hits = []
        for shape in self._shape_by_id.values():
            if self._shape_contains_point(shape, pos):
                hits.append(shape)

        if not hits:
            return None

        hits.sort(key=self._shape_area)  
        return hits[0]

    # ==================== Handle Management ====================

    def _make_handle(self, scene_pt: QPointF, size: float = 10.0) -> QGraphicsEllipseItem:
        """Create a resize handle at given position."""
        half = size / 2.0
        h = QGraphicsEllipseItem(-half, -half, size, size)
        h.setPos(scene_pt)
        h.setPen(self._make_pen(Qt.black, 2, Qt.SolidLine))
        h.setBrush(QBrush(Qt.white))
        h.setFlag(QGraphicsItem.ItemIgnoresTransformations, True)
        h.setZValue(999999)
        h.setVisible(True)
        self._scene.addItem(h)
        return h

    def _clear_handles(self, sid: int) -> None:
        """Remove all handles for a shape."""
        for h in self._handle_items.get(sid, []):
            try:
                if h.scene() is not None:
                    h.scene().removeItem(h)
            except RuntimeError:
                pass
        self._handle_items[sid] = []

    def _refresh_all_handles(self) -> None:
        """Refresh handles for all shapes."""
        for shape in list(self._shape_by_id.values()):
            self._refresh_handles_for_shape(shape)

    def _refresh_handles_for_shape(self, shape: BaseShape) -> None:
        """Refresh handles for a specific shape."""
        sid = id(shape)

        if isinstance(shape, RectShape):
            rect = self._norm_rect(shape.x1, shape.y1, shape.x2, shape.y2)
            self._create_rect_handles(shape, rect)

        elif isinstance(shape, CircleShape):
            self._create_circle_handle(shape, shape.cx, shape.cy, shape.r)

        elif isinstance(shape, PolygonShape):
            self._clear_handles(sid)
            pts = [QPointF(x, y) for x, y in shape.points]
            self._handle_items[sid] = [self._make_handle(p) for p in pts]

    def _create_rect_handles(self, shape: RectShape, rect: QRectF) -> None:
        """Create handles for rectangle corners."""
        sid = id(shape)
        self._clear_handles(sid)
        corners = [rect.topLeft(), rect.topRight(), rect.bottomRight(), rect.bottomLeft()]
        self._handle_items[sid] = [self._make_handle(pt) for pt in corners]

    def _create_circle_handle(self, shape: CircleShape, cx: float, cy: float, r: float) -> None:
        """Create handle for circle."""
        sid = id(shape)
        self._clear_handles(sid)
        self._handle_items[sid] = [self._make_handle(QPointF(cx + r, cy))]

    # ==================== History (Undo/Redo) ====================

    def _snapshot_shapes(self) -> list[BaseShape]:
        """Create deep copy of current shapes."""
        return [self._clone_shape(s, 0.0, 0.0) for s in self.all_shapes()]

    def _push_undo_snapshot(self, snap: list[BaseShape]) -> None:
        """Push snapshot to undo stack."""
        if self._history_blocked:
            return

        self._undo_stack.append(snap)
        if len(self._undo_stack) > self.MAX_HISTORY:
            self._undo_stack.pop(0)
        self._redo_stack.clear()

    def _restore_snapshot(self, snap: list[BaseShape]) -> None:
        """Restore shapes from snapshot."""
        self._history_blocked = True
        try:
            self.load_shapes([self._clone_shape(s, 0.0, 0.0) for s in snap])
        finally:
            self._history_blocked = False

    def undo(self) -> None:
        """Undo last action."""
        if not self._undo_stack:
            return

        current = self._snapshot_shapes()
        prev = self._undo_stack.pop()
        self._redo_stack.append(current)
        self._restore_snapshot(prev)
        self._emit_shapes_changed()

    def redo(self) -> None:
        """Redo last undone action."""
        if not self._redo_stack:
            return

        current = self._snapshot_shapes()
        nxt = self._redo_stack.pop()
        self._undo_stack.append(current)
        self._restore_snapshot(nxt)
        self._emit_shapes_changed()

    # ==================== Unlabeled Shapes ====================

    def has_unlabeled_shapes(self) -> bool:
        """Check if any shapes are unlabeled."""
        for s in self.all_shapes():
            lbl = (getattr(s, "label", "") or "").strip()
            if lbl == "" or lbl == self.DEFAULT_LABEL:
                return True
        return False

    def _unlabeled_sids(self) -> list[int]:
        """Get list of unlabeled shape IDs."""
        return [
            id(s) for s in self.all_shapes()
            if (getattr(s, "label", "") or "").strip() in ("", self.DEFAULT_LABEL)
        ]

    def start_unlabeled_blink(self) -> None:
        """Start blinking unlabeled shapes."""
        if not self.has_unlabeled_shapes():
            self.stop_unlabeled_blink()
            return

        sids = self._unlabeled_sids()
        self._unlabeled_blinking_sids = set(sids)
        self._select_many(sids)
        self.focus_on_shapes(sids)

        if not self._unlabeled_timer.isActive():
            self._unlabeled_on = False
            self._unlabeled_timer.start()
            self._unlabeled_tick()

    def stop_unlabeled_blink(self) -> None:
        """Stop unlabeled blink and restore appearance."""
        if self._unlabeled_timer.isActive():
            self._unlabeled_timer.stop()

        self._unlabeled_on = False

        # Reset all shapes that were blinking
        for sid in self._unlabeled_blinking_sids:
            shape = self._shape_by_id.get(sid)
            item = self._shape_items.get(sid)

            if item is None:
                continue

            color = getattr(shape, "color", self.DEFAULT_COLOR) if shape else self.DEFAULT_COLOR

            try:
                item.setPen(self._make_pen(color, 3, Qt.SolidLine))
            except RuntimeError:
                pass

            self._set_shape_opacity(sid, 1.0)

        self._unlabeled_blinking_sids.clear()

    def _unlabeled_tick(self) -> None:
        """Timer tick for unlabeled blink animation."""
        sids = self._unlabeled_sids()
        if not sids:
            self.stop_unlabeled_blink()
            return

        self._unlabeled_on = not self._unlabeled_on

        for sid in sids:
            item = self._shape_items.get(sid)
            shape = self._shape_by_id.get(sid)

            if item is None or shape is None:
                continue

            color = getattr(shape, "color", self.DEFAULT_COLOR)

            try:
                if self._unlabeled_on:
                    item.setPen(self._make_pen(color, 5, Qt.DashLine))
                else:
                    item.setPen(self._make_pen(color, 3, Qt.SolidLine))

                self._set_shape_opacity(sid, 1.0)
            except RuntimeError:
                pass

    # ==================== Label Blink ====================

    def blink_by_label(self, label: str, cycles: int = 6, interval_ms: int = 160) -> None:
        """Blink shapes with specific label."""
        if not label:
            return

        self._stop_label_blink()

        targets = [
            id(sh) for sh in self._shape_by_id.values()
            if (getattr(sh, "label", None) or "").strip() == label.strip()
        ]

        if not targets:
            return

        self._select_many(targets)
        self.focus_on_shapes(targets)

        self._label_blink_sids = targets
        self._label_blink_phase = 0
        self._label_blink_cycles = max(2, int(cycles))

        self._label_blink_timer = QTimer(self)
        self._label_blink_timer.timeout.connect(self._label_blink_step)
        self._label_blink_timer.start(interval_ms)

    def _label_blink_step(self) -> None:
        """Timer tick for label blink animation."""
        if not self._label_blink_sids:
            self._stop_label_blink()
            return

        on = (self._label_blink_phase % 2 == 0)
        opacity = 1.0 if on else 0.2

        for sid in self._label_blink_sids:
            self._set_shape_opacity(sid, opacity)

        self._label_blink_phase += 1
        if self._label_blink_phase >= self._label_blink_cycles:
            self._stop_label_blink()

    def _stop_label_blink(self) -> None:
        """Stop label blink and restore appearance."""
        if self._label_blink_timer is not None:
            self._label_blink_timer.stop()
            self._label_blink_timer.deleteLater()
            self._label_blink_timer = None

        for sid in self._label_blink_sids:
            self._set_shape_opacity(sid, 1.0)

        self._label_blink_sids = []
        self._label_blink_phase = 0
        self._label_blink_cycles = 0

        if self._attention_prev_selected_ids:
            self._select_many(list(self._attention_prev_selected_ids))
        else:
            self.clear_selection()

    # ==================== Modes ====================

    def set_draw_enabled(self, enabled: bool) -> None:
        """Enable/disable annotation mode."""
        prev_draw, prev_edit = self._draw_enabled, self._edit_enabled

        self._draw_enabled = enabled
        if enabled and self._edit_enabled:
            self._edit_enabled = False

        self._cancel_temp_drawing()
        self._reset_operation_state()
        self._hover_shape = None
        self._update_label_visibility()
        self._refresh_all_handles()
        self._apply_cursor(None)

        if self._draw_enabled != prev_draw:
            self.annotationModeChanged.emit(self._draw_enabled)
        if self._edit_enabled != prev_edit:
            self.editModeChanged.emit(self._edit_enabled)

    def set_edit_mode(self, enabled: bool) -> None:
        """Enable/disable edit mode."""
        prev_draw, prev_edit = self._draw_enabled, self._edit_enabled

        self._edit_enabled = enabled
        if enabled and self._draw_enabled:
            self._draw_enabled = False
            self._cancel_temp_drawing()

        self._reset_operation_state()
        self._update_label_visibility()
        self._refresh_all_handles()
        self._apply_cursor(None)

        if self._edit_enabled != prev_edit:
            self.editModeChanged.emit(self._edit_enabled)
        if self._draw_enabled != prev_draw:
            self.annotationModeChanged.emit(self._draw_enabled)

    def set_shape_mode(self, shape: str) -> None:
        """Set current shape drawing mode."""
        if shape in ("rect", "circle", "poly"):
            self._shape_mode = shape
            self._cancel_temp_drawing()

    def set_current_label(self, name: str, color: str) -> None:
        """Set current label and color for new shapes."""
        self._current_label = name or self.DEFAULT_LABEL
        self._current_color = color or self.DEFAULT_COLOR

    # ==================== Image ====================

    def set_image(self, image: QImage) -> None:
        """Set the image to display"""
        if self._image_item is None:
            self._image_item = QImageItem()
            self._scene.addItem(self._image_item)

            self._image_item.setZValue(-100)

        self._image_item.set_image(image)

        rect = self._image_item.boundingRect()
        self._scene.setSceneRect(rect)

        if self._grid_divisions > 1:
            self._current_cell = (0, 0)
        else:
            self._current_cell = None

        self._update_zoom_limits_from_image()
        self.zoom_fit()

    def clear_image(self) -> None:
        """Clear the current image."""
        if self._image_item is not None:
            self._scene.removeItem(self._image_item)
            self._image_item = None

        self._grid_divisions = 1
        self._current_cell = None
        self._scene.setSceneRect(0, 0, 0, 0)

    # ==================== Zoom / Grid ====================

    def _current_view_scene_rect(self) -> QRectF:
        # viewport rect in view coords -> scene rect
        return self.mapToScene(self.viewport().rect()).boundingRect()

    def _emit_viewport_changed(self) -> None:
        if self._image_item is None:
            return

        full = self._image_item.boundingRect()
        if full.isEmpty():
            return

        view = self._current_view_scene_rect().intersected(full)
        if view.isEmpty():
            # outside image (rare), treat as full
            self.viewportChanged.emit(0.0, 0.0, 1.0, 1.0)
            return

        nx = (view.left() - full.left()) / full.width()
        ny = (view.top() - full.top()) / full.height()
        nw = view.width() / full.width()
        nh = view.height() / full.height()

        # clamp
        nx = max(0.0, min(1.0, float(nx)))
        ny = max(0.0, min(1.0, float(ny)))
        nw = max(0.0, min(1.0, float(nw)))
        nh = max(0.0, min(1.0, float(nh)))

        self.viewportChanged.emit(nx, ny, nw, nh)

    def _current_target_rect(self) -> QRectF:
        """Get current view target rectangle."""
        if self._image_item is None:
            return QRectF()

        full = self._image_item.boundingRect()
        if full.isEmpty():
            return QRectF()

        if self._grid_divisions > 1 and self._current_cell is not None:
            n = self._grid_divisions
            row, col = self._current_cell

            iw, ih = full.width(), full.height()
            tile_w, tile_h = iw / n, ih / n
            x = col * tile_w
            y = row * tile_h
            return QRectF(x, y, tile_w, tile_h)

        return full

    def _compute_fit_zoom(self) -> float:
        """Compute zoom level to fit target rect in view."""
        if self._image_item is None:
            return 1.0

        rect = self._current_target_rect()
        if rect.isEmpty():
            return 1.0

        vw, vh = self.viewport().width(), self.viewport().height()
        if vw <= 0 or vh <= 0:
            return 1.0

        return min(vw / rect.width(), vh / rect.height())


    def _update_zoom_limits_from_image(self) -> None:
        """Update per-image zoom limits.

        Rule:
        - if both width and height are < 5000px -> max zoom = 10
        - otherwise -> max zoom = 30
        """
        if self._image_item is None:
            self._max_zoom = self.MAX_ZOOM
            return

        img = self._image_item.image()
        if img is None or img.isNull():
            self._max_zoom = self.MAX_ZOOM
            return

        w, h = int(img.width()), int(img.height())
        self._max_zoom = 10.0 if (w < 5000 and h < 5000) else 30.0

        # Keep consistency (min must not exceed max)
        if self._min_zoom > self._max_zoom:
            self._min_zoom = self._max_zoom

    def _clamp_zoom(self, z: float) -> float:
        return max(self._min_zoom, min(self._max_zoom, float(z)))

    def _emit_zoom_changed(self) -> None:
        """Notify listeners (e.g., main window status bar) about zoom range/current."""
        self.zoomChanged.emit(self._min_zoom, self._max_zoom, self._zoom, self._mode)

    def zoom_info_text(self) -> str:
        """Human-readable zoom info for status bar."""
        return (
            f"Zoom: {self._zoom:.2f}x  (min: {self._min_zoom:.2f}x  |  max: {self._max_zoom:.2f}x)  [{self._mode}]"
        )

    def zoom_fit(self) -> None:
        """Fit view to target rectangle.

        Note: in this app, minimum zoom is always the "fit" zoom for the current target.
        """
        if self._image_item is None:
            return

        self._update_zoom_limits_from_image()

        fit_zoom = max(self.MIN_ZOOM, min(self._max_zoom, self._compute_fit_zoom()))
        self._mode = "fit"
        self._zoom = fit_zoom
        self._min_zoom = fit_zoom

        rect = self._current_target_rect()
        self.resetTransform()
        self.scale(self._zoom, self._zoom)

        if not rect.isEmpty():
            self.centerOn(rect.center())


        self._emit_zoom_changed()
        self._emit_viewport_changed()

    def zoom_actual(self) -> None:
        """Set zoom to 100% (1.0x).

        If fit zoom is bigger than 1.0x (e.g., small images), minimum zoom is still fit.
        """
        if self._image_item is None:
            return

        rect = self._current_target_rect()
        if rect.isEmpty():
            rect = self._image_item.boundingRect()

        self._mode = "free"
        self._zoom = self._clamp_zoom(1.0)

        self.resetTransform()
        self.scale(self._zoom, self._zoom)
        self.centerOn(rect.center())

        self._emit_zoom_changed()
        self._emit_viewport_changed()

    def set_grid_divisions(self, n: int) -> None:
        """Set grid division count."""
        self._grid_divisions = max(1, int(n))
        self._current_cell = None

    def focus_on_grid_cell(self, row: int, col: int) -> None:
        """Focus on specific grid cell."""
        if self._image_item is None:
            return
        self._current_cell = None if self._grid_divisions <= 1 else (row, col)
        self.zoom_fit()

    def focus_on_shapes(self, sids: list[int], padding: float = 40.0) -> None:
        """Focus view on given shapes."""
        if not sids:
            return

        rect: Optional[QRectF] = None
        for sid in sids:
            it = self._shape_items.get(sid)
            if it is None:
                continue
            r = it.mapToScene(it.boundingRect()).boundingRect()
            rect = r if rect is None else rect.united(r)

        if rect is None:
            return

        rect = rect.adjusted(-padding, -padding, padding, padding)
        self.fitInView(rect, Qt.KeepAspectRatio)
        self._zoom = self.transform().m11()
        self._mode = "free"

        if self._zoom < self._min_zoom:
            self._zoom = self._min_zoom
            self.resetTransform()
            self.scale(self._zoom, self._zoom)
            self.centerOn(rect.center())

        self._emit_zoom_changed()
        self._emit_viewport_changed()

    # ==================== Temp Drawing ====================

    def _cancel_temp_drawing(self) -> None:
        """Cancel any in-progress drawing."""
        if self._temp_item is not None:
            self._scene.removeItem(self._temp_item)
            self._temp_item = None

        if self._poly_temp_item is not None:
            self._scene.removeItem(self._poly_temp_item)
            self._poly_temp_item = None

        for h in self._poly_handle_items:
            self._scene.removeItem(h)
        self._poly_handle_items.clear()

        self._drag_start_scene = None
        self._circle_center = None
        self._poly_points.clear()
        self._poly_mouse_scene = None

    def _update_poly_preview(self) -> None:
        """Update polygon preview graphics."""
        # Clear existing preview
        if self._poly_temp_item is not None:
            self._scene.removeItem(self._poly_temp_item)
            self._poly_temp_item = None

        for h in self._poly_handle_items:
            self._scene.removeItem(h)
        self._poly_handle_items.clear()

        if not self._poly_points:
            return

        # Build path
        path = QPainterPath(self._poly_points[0])
        for p in self._poly_points[1:]:
            path.lineTo(p)

        if self._poly_mouse_scene is not None:
            path.lineTo(self._poly_mouse_scene)

        # Draw preview
        pen = self._make_pen(self.DEFAULT_COLOR, 2, Qt.DashLine)
        self._poly_temp_item = self._scene.addPath(path, pen, QBrush(Qt.NoBrush))
        self._poly_temp_item.setZValue(10)

        # Draw vertex handles
        # size, half = 8.0, 4.0
        # for p in self._poly_points:
        #     h = self._scene.addEllipse(
        #         QRectF(p.x() - half, p.y() - half, size, size),
        #         self._make_pen(Qt.black, 2, Qt.SolidLine),
        #         QBrush(Qt.white),
        #     )
        #     h.setFlag(QGraphicsItem.ItemIgnoresTransformations, True)
        #     h.setZValue(11)
        #     h.setVisible(True)
        #     self._poly_handle_items.append(h)
        for p in self._poly_points:
            h = self._make_handle(p)          # same as finalized polygon handles
            self._poly_handle_items.append(h)


    def _clear_poly_preview_items(self) -> None:
        """Remove polygon preview graphics (path + vertex handles) only."""
        if self._poly_temp_item is not None:
            self._scene.removeItem(self._poly_temp_item)
            self._poly_temp_item = None

        for h in self._poly_handle_items:
            self._scene.removeItem(h)
        self._poly_handle_items.clear()

    def _cancel_polygon_drawing(self) -> None:
        """Cancel current polygon drawing session (clear points + preview)."""
        self._poly_points.clear()
        self._poly_mouse_scene = None
        self._clear_poly_preview_items()
        self._op = "idle"

    def _pop_polygon_last_point(self) -> None:
        """Remove last polygon point (if any) and refresh preview."""
        if not self._poly_points:
            return
        self._poly_points.pop()
        # keep mouse anchor consistent
        self._poly_mouse_scene = self._poly_points[-1] if self._poly_points else None

        # Refresh preview: easiest is clear + rebuild
        self._clear_poly_preview_items()
        self._update_poly_preview()

    def _finalize_polygon_from_points(self) -> None:
        """Finalize polygon from collected points."""
        if not self._poly_points or len(self._poly_points) < 3 or self._shape_manager is None:
            return

        self._push_undo_snapshot(self._snapshot_shapes())

        shape = PolygonShape(
            label=self.DEFAULT_LABEL,
            color=self.DEFAULT_COLOR,
            shape_type="poly",
            points=[(p.x(), p.y()) for p in self._poly_points],
        )

        self._shape_manager.add_shape(shape)
        self._finalize_polygon_graphics(shape, self._poly_points)

        # Cleanup
        self._poly_points.clear()
        self._poly_mouse_scene = None

        if self._poly_temp_item is not None:
            self._scene.removeItem(self._poly_temp_item)
            self._poly_temp_item = None

        for h in self._poly_handle_items:
            self._scene.removeItem(h)
        self._poly_handle_items.clear()

        self._emit_shapes_changed()

    # ==================== Graphics Creation ====================

    def _finalize_rect_graphics(self, shape: RectShape, rect: QRectF) -> None:
        """Create graphics for rectangle shape."""
        item = self._temp_item if isinstance(self._temp_item, QGraphicsRectItem) else self._scene.addRect(rect)
        item.setPen(self._make_pen(shape.color, 3, Qt.SolidLine))
        item.setBrush(Qt.NoBrush)
        item.setZValue(5)
        item.setData(0, shape)

        sid = id(shape)
        self._shape_by_id[sid] = shape
        self._shape_items[sid] = item

        self._create_rect_handles(shape, rect)
        self._create_label_chip(shape, rect.topLeft())
        self._set_selected_shape(shape)
        self._emit_shapes_changed()

    def _finalize_circle_graphics(self, shape: CircleShape, cx: float, cy: float, r: float) -> None:
        """Create graphics for circle shape."""
        rect = QRectF(cx - r, cy - r, 2 * r, 2 * r)
        item = self._temp_item if isinstance(self._temp_item, QGraphicsEllipseItem) else self._scene.addEllipse(rect)

        item.setPen(self._make_pen(shape.color, 3, Qt.SolidLine))
        item.setBrush(Qt.NoBrush)
        item.setZValue(5)
        item.setData(0, shape)

        sid = id(shape)
        self._shape_by_id[sid] = shape
        self._shape_items[sid] = item

        self._create_circle_handle(shape, cx, cy, r)
        self._create_label_chip(shape, rect.topLeft())
        self._set_selected_shape(shape)
        self._emit_shapes_changed()

    def _finalize_polygon_graphics(self, shape: PolygonShape, points: List[QPointF]) -> None:
        """Create graphics for polygon shape."""
        sid = id(shape)
        path = self._make_polygon_path(shape.points)

        item = self._scene.addPath(path, self._make_pen(shape.color, 3, Qt.SolidLine), QBrush(Qt.NoBrush))
        item.setZValue(5)
        item.setData(0, shape)

        self._shape_by_id[sid] = shape
        self._shape_items[sid] = item

        self._clear_handles(sid)
        self._handle_items[sid] = [self._make_handle(p) for p in points]

        bbox = QPolygonF(points).boundingRect()
        self._create_label_chip(shape, bbox.topLeft())
        self._set_selected_shape(shape)

    def _create_label_chip(self, shape: BaseShape, anchor: QPointF) -> None:
        """Create label chip for shape."""
        text = getattr(shape, "label", "") or self.DEFAULT_LABEL
        font = QFont("Arial", 9)

        text_item = QGraphicsSimpleTextItem(text)
        text_item.setFont(font)
        text_item.setBrush(QBrush(Qt.black))
        text_item.setZValue(31)
        text_item.setPos(anchor.x() + 4.0, anchor.y() - 20.0)
        self._scene.addItem(text_item)

        br = text_item.mapToScene(text_item.boundingRect()).boundingRect()
        pad = 2.0
        bg_rect = br.adjusted(-pad, -pad, pad, pad)

        bg_item = QGraphicsRectItem(bg_rect)
        bg_item.setBrush(QColor("#F5E6C8"))
        bg_item.setPen(self._make_pen("#222222", 1, Qt.SolidLine))
        bg_item.setZValue(30)
        self._scene.addItem(bg_item)

        text_item.setZValue(bg_item.zValue() + 1)
        bg_item.setVisible(False)
        text_item.setVisible(False)

        self._label_items[id(shape)] = [bg_item, text_item]

    # ==================== Selection / Hover ====================

    def _set_hover_shape(self, shape: Optional[BaseShape]) -> None:
        """Set currently hovered shape."""
        if shape is self._hover_shape:
            return
        self._hover_shape = shape
        self._update_label_visibility()

    def _set_selected_shape(self, shape: Optional[BaseShape], additive: bool = False) -> None:
        """Set selected shape(s)."""
        if not additive:
            for sid in list(self._selected_shape_ids):
                sh = self._shape_by_id.get(sid)
                if sh is not None:
                    self._update_shape_highlight(sh, False)
                    self._remove_crosshair(sh)
            self._selected_shape_ids.clear()
            self._selected_shape = None

        if shape is None:
            self._update_label_visibility()
            return

        sid = id(shape)
        if sid not in self._selected_shape_ids:
            self._selected_shape_ids.add(sid)
            self._update_shape_highlight(shape, True)
            self._create_crosshair(shape)

        self._selected_shape = shape
        self._update_label_visibility()

    def _select_many(self, sids: list[int]) -> None:
        """Select multiple shapes by ID."""
        self._attention_prev_selected_ids = set(self._selected_shape_ids)
        self._attention_prev_selected_shape = self._selected_shape

        # Clear current selection
        for sid in list(self._selected_shape_ids):
            sh = self._shape_by_id.get(sid)
            if sh is not None:
                self._update_shape_highlight(sh, False)
                self._remove_crosshair(sh)

        self._selected_shape_ids.clear()
        self._selected_shape = None

        # Add new selection
        for sid in sids:
            sh = self._shape_by_id.get(sid)
            if sh is None:
                continue
            self._selected_shape_ids.add(sid)
            self._update_shape_highlight(sh, True)
            self._create_crosshair(sh)

        if sids:
            self._selected_shape = self._shape_by_id.get(sids[-1])

        self._update_label_visibility()

    def _update_shape_highlight(self, shape: BaseShape, on: bool) -> None:
        """Update shape highlight state."""
        item = self._shape_items.get(id(shape))
        if not item:
            return
        pen = item.pen()
        pen.setWidth(3 if on else 2)
        pen.setCosmetic(True)
        item.setPen(pen)

    def _update_label_visibility(self) -> None:
        """Update visibility of all label chips."""
        for sid, items in self._label_items.items():
            shape = self._shape_by_id.get(sid)
            visible = shape is not None and (sid in self._selected_shape_ids or shape is self._hover_shape)
            for it in items:
                it.setVisible(visible)

    def _create_crosshair(self, shape: BaseShape) -> None:
        """Create crosshair lines for selected shape."""
        sid = id(shape)
        self._remove_crosshair(shape)

        item = self._shape_items.get(sid)
        if item is None:
            return

        center = item.mapToScene(item.boundingRect()).boundingRect().center()
        scene_rect = self._scene.sceneRect()
        color_str = getattr(shape, "color", self.DEFAULT_COLOR)
        pen = self._make_pen(color_str, 3, Qt.SolidLine)

        hline = self._scene.addLine(scene_rect.left(), center.y(), scene_rect.right(), center.y(), pen)
        vline = self._scene.addLine(center.x(), scene_rect.top(), center.x(), scene_rect.bottom(), pen)
        hline.setZValue(100)
        vline.setZValue(100)

        self._cross_items[sid] = [hline, vline]

    def _remove_crosshair(self, shape: BaseShape) -> None:
        """Remove crosshair for shape."""
        for ln in self._cross_items.pop(id(shape), []):
            self._scene.removeItem(ln)

    def selected_shape(self) -> Optional[BaseShape]:
        """Get currently selected shape."""
        return self._selected_shape

    def clear_selection(self) -> None:
        """Clear all selection."""
        self._set_selected_shape(None, additive=False)

    # ==================== Apply Label ====================

    def apply_label_to_selection(self, label: str, color: str) -> None:
        """Apply label and color to selected shapes."""
        if not self._selected_shape_ids:
            return

        self._push_undo_snapshot(self._snapshot_shapes())

        for sid in list(self._selected_shape_ids):
            shape = self._shape_by_id.get(sid)
            if shape is None:
                continue

            shape.label = label
            shape.color = color

            item = self._shape_items.get(sid)
            if item is not None:
                item.setPen(self._make_pen(color, 3, Qt.SolidLine))

            # Recreate label chip
            old_chip = self._label_items.pop(sid, None)
            if old_chip is not None:
                for it in old_chip:
                    self._scene.removeItem(it)

            if item is not None:
                br = item.mapToScene(item.boundingRect()).boundingRect()
                self._create_label_chip(shape, br.topLeft())

            # Recreate crosshair with new color
            self._remove_crosshair(shape)
            self._create_crosshair(shape)

        self._update_label_visibility()
        self._refresh_all_handles()

        if not self.has_unlabeled_shapes():
            self.stop_unlabeled_blink()

        self._emit_shapes_changed()

    # ==================== Group Resize ====================

    def _begin_group_resize(self, base_sid: int, handle_idx: int, start_mouse: QPointF) -> None:
        """Begin group resize operation."""
        base = self._shape_by_id.get(base_sid)

        if isinstance(base, RectShape):
            group = [s for s in self._selected_shape_ids if isinstance(self._shape_by_id.get(s), RectShape)]
            start_rects = {
                s: (sh.x1, sh.y1, sh.x2, sh.y2)
                for s in group
                if isinstance((sh := self._shape_by_id.get(s)), RectShape)
            }
            self._resize_group = group
            self._resize_anchor = {
                "kind": "rect",
                "handle": handle_idx,
                "start_mouse": start_mouse,
                "start_rects": start_rects,
            }
            return

        if isinstance(base, CircleShape):
            group = [s for s in self._selected_shape_ids if isinstance(self._shape_by_id.get(s), CircleShape)]
            start_rs = {
                s: sh.r
                for s in group
                if isinstance((sh := self._shape_by_id.get(s)), CircleShape)
            }
            self._resize_group = group
            self._resize_anchor = {
                "kind": "circle",
                "base_sid": base_sid,
                "start_mouse": start_mouse,
                "start_r": start_rs,
                "base_start_r": base.r,
            }
            return

        self._resize_group = [base_sid]
        self._resize_anchor = None

    def _apply_group_resize_rect(self, current_mouse: QPointF) -> None:
        """Apply group resize for rectangles."""
        if not self._resize_anchor or self._resize_anchor.get("kind") != "rect":
            return

        handle = int(self._resize_anchor["handle"])
        start_mouse: QPointF = self._resize_anchor["start_mouse"]
        start_rects: Dict[int, Tuple[float, float, float, float]] = self._resize_anchor["start_rects"]

        dx = current_mouse.x() - start_mouse.x()
        dy = current_mouse.y() - start_mouse.y()

        for sid in (self._resize_group or list(start_rects.keys())):
            if sid not in start_rects:
                continue

            sh = self._shape_by_id.get(sid)
            if not isinstance(sh, RectShape):
                continue

            x1, y1, x2, y2 = start_rects[sid]

            # Apply delta based on handle: 0=TL, 1=TR, 2=BR, 3=BL
            if handle == 0:
                x1 += dx
                y1 += dy
            elif handle == 1:
                x2 += dx
                y1 += dy
            elif handle == 2:
                x2 += dx
                y2 += dy
            elif handle == 3:
                x1 += dx
                y2 += dy

            # Normalize and enforce minimum size
            left, right = min(x1, x2), max(x1, x2)
            top, bottom = min(y1, y2), max(y1, y2)

            min_size = 3.0
            if right - left < min_size:
                right = left + min_size
            if bottom - top < min_size:
                bottom = top + min_size

            sh.x1, sh.y1, sh.x2, sh.y2 = left, top, right, bottom

            rect = QRectF(left, top, right - left, bottom - top)
            item = self._shape_items.get(sid)
            if isinstance(item, QGraphicsRectItem):
                item.setRect(rect)

            self._create_rect_handles(sh, rect)
            self._sync_label_chip_and_crosshair_for_shape(sh)

        self._update_label_visibility()

    def _apply_group_resize_circle(self, current_mouse: QPointF) -> None:
        """Apply group resize for circles."""
        if not self._resize_anchor or self._resize_anchor.get("kind") != "circle":
            return

        base_sid = int(self._resize_anchor["base_sid"])
        base = self._shape_by_id.get(base_sid)
        if not isinstance(base, CircleShape):
            return

        start_r: Dict[int, float] = self._resize_anchor["start_r"]
        base_start_r: float = float(self._resize_anchor["base_start_r"])

        dx0 = current_mouse.x() - base.cx
        dy0 = current_mouse.y() - base.cy
        new_r0 = (dx0 * dx0 + dy0 * dy0) ** 0.5
        delta_r = new_r0 - base_start_r

        for sid in (self._resize_group or list(start_r.keys())):
            sh = self._shape_by_id.get(sid)
            if not isinstance(sh, CircleShape):
                continue

            sh.r = max(2.0, start_r.get(sid, sh.r) + delta_r)

            item = self._shape_items.get(sid)
            if isinstance(item, QGraphicsEllipseItem):
                rect = QRectF(sh.cx - sh.r, sh.cy - sh.r, 2 * sh.r, 2 * sh.r)
                item.setRect(rect)

            self._create_circle_handle(sh, sh.cx, sh.cy, sh.r)
            self._sync_label_chip_and_crosshair_for_shape(sh)

        self._update_label_visibility()

    def _resize_polygon_vertex(self, shape: PolygonShape, handle_index: int, scene_pos: QPointF) -> None:
        """Resize polygon by moving vertex."""
        if handle_index < 0 or handle_index >= len(shape.points):
            return

        pts = list(shape.points)
        pts[handle_index] = (scene_pos.x(), scene_pos.y())
        shape.points = pts

        sid = id(shape)
        item = self._shape_items.get(sid)
        if isinstance(item, QGraphicsPathItem):
            item.setPath(self._make_polygon_path(shape.points))

        self._refresh_handles_for_shape(shape)
        self._sync_label_chip_and_crosshair_for_shape(shape)
        self._update_label_visibility()

    def _sync_label_chip_and_crosshair_for_shape(self, shape: BaseShape) -> None:
        """Sync label chip and crosshair after shape change."""
        sid = id(shape)
        item = self._shape_items.get(sid)

        # Recreate label chip
        old_chip = self._label_items.pop(sid, None)
        if old_chip:
            for it in old_chip:
                self._scene.removeItem(it)

        if item is not None:
            br = item.mapToScene(item.boundingRect()).boundingRect()
            self._create_label_chip(shape, br.topLeft())

        # Recreate crosshair if selected
        self._remove_crosshair(shape)
        if sid in self._selected_shape_ids:
            self._create_crosshair(shape)

    # ==================== Mouse Events ====================

    def mousePressEvent(self, event) -> None:
        if self._image_item is None:
            return super().mousePressEvent(event)

        scene_pos = self.mapToScene(event.pos())

        if event.button() == Qt.RightButton:
            self._handle_right_click(event, scene_pos)
            return

        if event.button() == Qt.LeftButton:
            self._handle_left_click(event, scene_pos)
            return

        if event.button() == Qt.MiddleButton:
            self._handle_middle_click(event, scene_pos)
            return

        super().mousePressEvent(event)

    def _handle_right_click(self, event, scene_pos: QPointF) -> None:
        """Handle right click for selection."""
        ctrl = bool(event.modifiers() & Qt.ControlModifier)
        shape = self._find_shape_at(scene_pos)

        if ctrl:
            if shape is not None:
                self._set_selected_shape(shape, additive=True)
            self._apply_cursor(scene_pos)
            return

        if shape is None:
            if self._selected_shape_ids:
                self.clear_selection()
            self._apply_cursor(scene_pos)
            return

        sid = id(shape)
        if sid in self._selected_shape_ids:
            self.set_edit_mode(not self._edit_enabled)
        else:
            self._set_selected_shape(shape, additive=False)

        self._apply_cursor(scene_pos)

    def _handle_left_click(self, event, scene_pos: QPointF) -> None:
        """Handle left click for drawing/editing."""
        if self._draw_enabled:
            self._handle_draw_click(scene_pos)
            return

        if self._handle_resize_click(scene_pos):
            return

        if self._handle_move_click(scene_pos):
            return

        self._op = "pan"
        self._pan_last_view = QPointF(event.pos())
        self._apply_cursor(scene_pos)
        event.accept()

    def _handle_middle_click(self, event, scene_pos: QPointF) -> None:
        """Handle middle click for panning."""
        self._op = "pan"
        self._pan_last_view = QPointF(event.pos())
        self._apply_cursor(scene_pos)
        event.accept()

    def _handle_draw_click(self, scene_pos: QPointF) -> None:
        """Handle click in draw mode."""
        self._op = "draw"

        if self._shape_mode in ("rect", "circle"):
            if self._shape_mode == "rect":
                self._drag_start_scene = scene_pos
                self._circle_center = None
            else:
                self._circle_center = scene_pos
                self._drag_start_scene = None

            if self._temp_item is not None:
                self._scene.removeItem(self._temp_item)

            self._temp_item = (
                self._scene.addRect(QRectF(scene_pos, scene_pos))
                if self._shape_mode == "rect"
                else self._scene.addEllipse(QRectF(scene_pos, scene_pos))
            )
            self._temp_item.setPen(self._make_pen(self.DEFAULT_COLOR, 2, Qt.DashLine))
            self._temp_item.setBrush(Qt.NoBrush)
            self._temp_item.setZValue(10)

        elif self._shape_mode == "poly":
            if self._poly_points:
                first = self._poly_points[0]
                dx = scene_pos.x() - first.x()
                dy = scene_pos.y() - first.y()
                threshold = 10.0 / max(self._zoom, 0.001)

                if len(self._poly_points) >= 3 and dx * dx + dy * dy <= threshold * threshold:
                    self._finalize_polygon_from_points()
                    self._op = "idle"
                    self._apply_cursor(scene_pos)
                    return

            self._poly_points.append(scene_pos)
            self._poly_mouse_scene = scene_pos
            self._update_poly_preview()

        self._apply_cursor(scene_pos)

    def _handle_resize_click(self, scene_pos: QPointF) -> bool:
        """Handle click for resize. Returns True if handled."""
        if not self._can_resize():
            return False

        hit = self._hit_test_any_handle(scene_pos)
        if hit is None:
            hit = self._hit_test_circle_perimeter(scene_pos)

        if hit is None:
            return False

        sid, idx = hit

        self._pending_snapshot = self._snapshot_shapes()
        self._pending_changed = False

        self._op = "resize"
        self._resize_sid = sid
        self._resize_handle_index = idx
        self._drag_last_scene = scene_pos
        self._begin_group_resize(sid, idx, scene_pos)

        self._apply_cursor(scene_pos)
        return True

    def _handle_move_click(self, scene_pos: QPointF) -> bool:
        """Handle click for move. Returns True if handled."""
        if not self._can_mouse_move():
            return False

        shape = self._find_shape_at(scene_pos)
        if shape is None or id(shape) not in self._selected_shape_ids:
            return False

        self._pending_snapshot = self._snapshot_shapes()
        self._pending_changed = False

        self._op = "move"
        self._drag_last_scene = scene_pos

        self._apply_cursor(scene_pos)
        return True

    def mouseMoveEvent(self, event) -> None:
        if self._image_item is None:
            return super().mouseMoveEvent(event)

        scene_pos = self.mapToScene(event.pos())

        # Update hover
        self._set_hover_shape(self._find_shape_at(scene_pos))

        # Handle active operations
        if self._op == "move":
            self._handle_move_drag(scene_pos)
            return

        if self._op == "resize":
            self._handle_resize_drag(scene_pos)
            return

        if self._op == "pan":
            self._handle_pan_drag(event)
            return

        if self._draw_enabled:
            self._handle_draw_drag(scene_pos)
            return

        self._apply_cursor(scene_pos)
        super().mouseMoveEvent(event)

    def _handle_move_drag(self, scene_pos: QPointF) -> None:
        """Handle move drag operation."""
        if self._drag_last_scene is None or not self._can_mouse_move():
            self._reset_operation_state()
            self._apply_cursor(scene_pos)
            return

        dx = scene_pos.x() - self._drag_last_scene.x()
        dy = scene_pos.y() - self._drag_last_scene.y()
        self._drag_last_scene = scene_pos

        if dx != 0.0 or dy != 0.0:
            self._pending_changed = True

        for sid in list(self._selected_shape_ids):
            shape = self._shape_by_id.get(sid)
            if shape is not None:
                self._nudge_shape(shape, dx, dy)

        self._apply_cursor(scene_pos)

    def _handle_resize_drag(self, scene_pos: QPointF) -> None:
        """Handle resize drag operation."""
        if self._drag_last_scene is None or not self._can_resize() or self._resize_sid is None:
            self._reset_operation_state()
            self._apply_cursor(scene_pos)
            return

        self._pending_changed = True
        base = self._shape_by_id.get(self._resize_sid)

        if isinstance(base, RectShape):
            self._apply_group_resize_rect(scene_pos)
        elif isinstance(base, CircleShape):
            self._apply_group_resize_circle(scene_pos)
        elif isinstance(base, PolygonShape) and self._resize_handle_index is not None:
            self._resize_polygon_vertex(base, self._resize_handle_index, scene_pos)

    def _handle_pan_drag(self, event) -> None:
        """Handle pan drag operation."""
        if self._pan_last_view is None:
            return

        delta = QPointF(event.pos()) - self._pan_last_view
        self._pan_last_view = QPointF(event.pos())

        self.horizontalScrollBar().setValue(
            self.horizontalScrollBar().value() - int(delta.x())
        )
        self.verticalScrollBar().setValue(
            self.verticalScrollBar().value() - int(delta.y())
        )

        self._request_viewport_emit()
        self._apply_cursor(self.mapToScene(event.pos()))
    
    def _handle_draw_drag(self, scene_pos: QPointF) -> None:
        """Handle draw drag operation."""
        if self._shape_mode in ("rect", "circle") and self._temp_item is not None:
            if self._shape_mode == "rect" and self._drag_start_scene is not None:
                x1, y1 = self._drag_start_scene.x(), self._drag_start_scene.y()
                x2, y2 = scene_pos.x(), scene_pos.y()
                rect = QRectF(min(x1, x2), min(y1, y2), abs(x2 - x1), abs(y2 - y1))
                if isinstance(self._temp_item, QGraphicsRectItem):
                    self._temp_item.setRect(rect)

            elif self._shape_mode == "circle" and self._circle_center is not None:
                cx, cy = self._circle_center.x(), self._circle_center.y()
                dx2 = scene_pos.x() - cx
                dy2 = scene_pos.y() - cy
                r = (dx2 * dx2 + dy2 * dy2) ** 0.5
                rect = QRectF(cx - r, cy - r, 2 * r, 2 * r)
                if isinstance(self._temp_item, QGraphicsEllipseItem):
                    self._temp_item.setRect(rect)

        elif self._shape_mode == "poly" and self._poly_points:
            self._poly_mouse_scene = scene_pos
            self._update_poly_preview()

        self._apply_cursor(scene_pos)

    def mouseReleaseEvent(self, event) -> None:
        if self._image_item is None:
            return super().mouseReleaseEvent(event)

        scene_pos = self.mapToScene(event.pos())

        if event.button() in (Qt.LeftButton, Qt.MiddleButton) and self._op in ("move", "resize", "pan"):
            if self._op in ("move", "resize"):
                if self._pending_snapshot is not None and self._pending_changed:
                    self._push_undo_snapshot(self._pending_snapshot)
                    self._emit_shapes_changed()

                self._pending_snapshot = None
                self._pending_changed = False

            self._reset_operation_state()
            self._apply_cursor(scene_pos)
            return

        if self._draw_enabled and event.button() == Qt.LeftButton and self._temp_item is not None:
            self._finalize_draw(scene_pos)
            return

        super().mouseReleaseEvent(event)

    def _finalize_draw(self, scene_pos: QPointF) -> None:
        """Finalize drawing operation."""
        rect = self._temp_item.rect()

        # Too small → cancel
        if rect.width() < 3 or rect.height() < 3:
            self._scene.removeItem(self._temp_item)
            self._temp_item = None
            self._drag_start_scene = None
            self._circle_center = None
            self._op = "idle"
            self._apply_cursor(scene_pos)
            return

        if self._shape_manager is not None:
            self._push_undo_snapshot(self._snapshot_shapes())

            if self._shape_mode == "rect":
                shape = RectShape(
                    label=self.DEFAULT_LABEL,
                    color=self.DEFAULT_COLOR,
                    shape_type="rect",
                    x1=rect.left(),
                    y1=rect.top(),
                    x2=rect.right(),
                    y2=rect.bottom(),
                )
                self._shape_manager.add_shape(shape)
                self._finalize_rect_graphics(shape, rect)

            else:  # circle
                if self._circle_center is None:
                    cx = (rect.left() + rect.right()) / 2.0
                    cy = (rect.top() + rect.bottom()) / 2.0
                else:
                    cx, cy = self._circle_center.x(), self._circle_center.y()

                r = rect.width() / 2.0
                shape = CircleShape(
                    label=self.DEFAULT_LABEL,
                    color=self.DEFAULT_COLOR,
                    shape_type="circle",
                    cx=cx,
                    cy=cy,
                    r=r,
                )
                self._shape_manager.add_shape(shape)
                self._finalize_circle_graphics(shape, cx, cy, r)

        self._temp_item = None
        self._drag_start_scene = None
        self._circle_center = None
        self._op = "idle"
        self._apply_cursor(scene_pos)

    def mouseDoubleClickEvent(self, event) -> None:
        if self._image_item is not None and event.button() == Qt.RightButton:
            scene_pos = self.mapToScene(event.pos())
            if self._find_shape_at(scene_pos) is None:
                self.set_draw_enabled(not self._draw_enabled)
                self._apply_cursor(scene_pos)
                return

        if (
            self._draw_enabled
            and self._shape_mode == "poly"
            and event.button() == Qt.LeftButton
            and len(self._poly_points) >= 3
            and self._image_item is not None
        ):
            self._finalize_polygon_from_points()
            self._op = "idle"
            self._apply_cursor(self.mapToScene(event.pos()))
            return

        super().mouseDoubleClickEvent(event)

    def wheelEvent(self, event) -> None:
        if self._image_item is None:
            return super().wheelEvent(event)

        delta = event.angleDelta().y()
        if not delta:
            return

        self._mode = "free"
        step_factor = 1.25 if delta > 0 else 0.8
        new_zoom = self._clamp_zoom(self._zoom * step_factor)
        relative = new_zoom / self._zoom
        self._zoom = new_zoom

        self.scale(relative, relative)
        self._emit_zoom_changed()
        self._emit_viewport_changed()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if self._image_item is not None and self._mode == "fit":
            self.zoom_fit()
        elif self._image_item is not None:
            self._request_viewport_emit()


    # ==================== Keyboard Events ====================

    def _commit_keyboard_move(self) -> None:
        """Commit keyboard move to undo history (debounced)."""
        if self._kb_pending_snapshot is not None and self._kb_pending_changed:
            self._push_undo_snapshot(self._kb_pending_snapshot)
            self._emit_shapes_changed()

        self._kb_pending_snapshot = None
        self._kb_pending_changed = False

    def keyPressEvent(self, event: QKeyEvent) -> None:
        # Ctrl shortcuts
        if event.modifiers() & Qt.ControlModifier:
            if self._handle_ctrl_key(event):
                return

        if event.key() in (Qt.Key_Return, Qt.Key_Enter):
            self.applyRequested.emit()
            event.accept()
            return
    
        # Polygon drawing shortcuts (only when drafting poly)
        if self._draw_enabled and self._shape_mode == "poly" and self._poly_points:
            if event.key() == Qt.Key_Backspace:
                self._pop_polygon_last_point()
                return

            if event.key() == Qt.Key_Delete:
                self._cancel_polygon_drawing()
                return

        # Delete selection (normal)
        if event.key() == Qt.Key_Delete:
            self.delete_selection()
            return

        # Arrow move
        if self._selected_shape_ids and self._can_keyboard_move():
            if self._handle_arrow_key(event):
                return

        super().keyPressEvent(event)

    def _handle_ctrl_key(self, event: QKeyEvent) -> bool:
        """Handle Ctrl+key combinations. Returns True if handled."""
        # Ctrl+Shift+Z → Redo
        if (event.modifiers() & Qt.ShiftModifier) and event.key() == Qt.Key_Z:
            self.redo()
            return True

        if event.key() == Qt.Key_Z:
            self.undo()
            return True

        if event.key() == Qt.Key_Y:
            self.redo()
            return True

        if event.key() == Qt.Key_C:
            self.copy_selection()
            return True

        if event.key() == Qt.Key_V:
            self.paste_clipboard()
            return True
        
        if event.key() == Qt.Key_A:
            self.select_all()
            return True

        return False

    def _handle_arrow_key(self, event: QKeyEvent) -> bool:
        """Handle arrow key movement for selected shapes. Returns True if handled."""
        if not self._selected_shape_ids:
            return False

        step = 5 if (event.modifiers() & Qt.ShiftModifier) else 1

        dx = dy = 0
        if event.key() == Qt.Key_Left:
            dx = -step
        elif event.key() == Qt.Key_Right:
            dx = step
        elif event.key() == Qt.Key_Up:
            dy = -step
        elif event.key() == Qt.Key_Down:
            dy = step
        else:
            return False

        # start snapshot once per "burst"
        if self._kb_pending_snapshot is None:
            self._kb_pending_snapshot = self._snapshot_shapes()
            self._kb_pending_changed = False

        moved_any = False
        for sid in list(self._selected_shape_ids):
            shape = self._shape_by_id.get(sid)
            if shape is None:
                continue
            self._nudge_shape(shape, dx, dy)
            moved_any = True

        if moved_any:
            self._kb_pending_changed = True
            # restart debounce timer
            self._kb_move_timer.start()

        return True

    def _nudge_shape(self, shape: BaseShape, dx: float, dy: float) -> None:
        """Move shape by delta."""
        sid = id(shape)

        if isinstance(shape, RectShape):
            shape.x1 += dx
            shape.x2 += dx
            shape.y1 += dy
            shape.y2 += dy
            item = self._shape_items.get(sid)
            if isinstance(item, QGraphicsRectItem):
                r = item.rect()
                r.translate(dx, dy)
                item.setRect(r)

        elif isinstance(shape, CircleShape):
            shape.cx += dx
            shape.cy += dy
            item = self._shape_items.get(sid)
            if isinstance(item, QGraphicsEllipseItem):
                r = item.rect()
                r.translate(dx, dy)
                item.setRect(r)

        elif isinstance(shape, PolygonShape):
            shape.points = [(x + dx, y + dy) for x, y in shape.points]
            item = self._shape_items.get(sid)
            if isinstance(item, QGraphicsPathItem):
                item.setPath(self._make_polygon_path(shape.points))

        # Move associated items
        for it in self._label_items.get(sid, []):
            it.moveBy(dx, dy)
        for ln in self._cross_items.get(sid, []):
            ln.moveBy(dx, dy)

        self._refresh_handles_for_shape(shape)

    # ==================== Copy / Paste / Delete ====================

    def _clone_shape(self, shape: BaseShape, dx: float = 0.0, dy: float = 0.0) -> BaseShape:
        """Clone shape with optional offset."""
        if isinstance(shape, RectShape):
            return RectShape(
                label=shape.label,
                color=shape.color,
                shape_type=shape.shape_type,
                x1=shape.x1 + dx,
                y1=shape.y1 + dy,
                x2=shape.x2 + dx,
                y2=shape.y2 + dy,
            )

        if isinstance(shape, CircleShape):
            return CircleShape(
                label=shape.label,
                color=shape.color,
                shape_type=shape.shape_type,
                cx=shape.cx + dx,
                cy=shape.cy + dy,
                r=shape.r,
            )

        if isinstance(shape, PolygonShape):
            return PolygonShape(
                label=shape.label,
                color=shape.color,
                shape_type=shape.shape_type,
                points=[(x + dx, y + dy) for x, y in shape.points],
            )

        return shape

    def _add_shape_from_model(self, shape: BaseShape) -> None:
        """Add shape graphics from model."""
        if isinstance(shape, RectShape):
            rect = self._norm_rect(shape.x1, shape.y1, shape.x2, shape.y2)
            shape.x1, shape.y1 = rect.left(), rect.top()
            shape.x2, shape.y2 = rect.right(), rect.bottom()
            self._finalize_rect_graphics(shape, rect)

        elif isinstance(shape, CircleShape):
            self._finalize_circle_graphics(shape, shape.cx, shape.cy, shape.r)

        elif isinstance(shape, PolygonShape):
            pts = [QPointF(x, y) for x, y in shape.points]
            self._finalize_polygon_graphics(shape, pts)

    def _remove_shape_graphics(self, shape: BaseShape) -> None:
        """Remove all graphics for shape."""
        sid = id(shape)

        item = self._shape_items.pop(sid, None)
        if item is not None:
            self._scene.removeItem(item)

        for h in self._handle_items.pop(sid, []):
            try:
                self._scene.removeItem(h)
            except RuntimeError:
                pass

        for it in self._label_items.pop(sid, []):
            self._scene.removeItem(it)

        for ln in self._cross_items.pop(sid, []):
            self._scene.removeItem(ln)

        self._shape_by_id.pop(sid, None)

    def delete_selection(self) -> None:
        """Delete selected shapes."""
        if not self._selected_shape_ids or self._shape_manager is None:
            return

        self._push_undo_snapshot(self._snapshot_shapes())

        sids = list(self._selected_shape_ids)
        self.clear_selection()

        for sid in sids:
            shape = self._shape_by_id.get(sid)
            if shape is None:
                continue
            self._shape_manager.remove_shape(shape)
            self._remove_shape_graphics(shape)

        self._emit_shapes_changed()

    def copy_selection(self) -> None:
        """Copy selected shape to clipboard."""
        self._clipboard.clear()
        self._paste_count = 0

        if self._selected_shape:
            self._clipboard.append(self._clone_shape(self._selected_shape, 0.0, 0.0))

    def paste_clipboard(self) -> None:
        """Paste shapes from clipboard."""
        if not self._clipboard or self._shape_manager is None:
            return

        self._push_undo_snapshot(self._snapshot_shapes())

        self._paste_count += 1
        offs = self._paste_offset * float(self._paste_count)

        new_shapes: List[BaseShape] = []
        for shp in self._clipboard:
            new_shape = self._clone_shape(shp, offs, offs)
            self._shape_manager.add_shape(new_shape)
            self._add_shape_from_model(new_shape)
            new_shapes.append(new_shape)

        if new_shapes:
            self._set_selected_shape(new_shapes[-1])

        self._emit_shapes_changed()

    def select_all(self) -> None:
        """Select all shapes."""
        sids = list(self._shape_by_id.keys())
        for sid in sids:
            shape = self._shape_by_id.get(sid)
            if shape is not None:
                self._update_shape_highlight(shape, True)
                self._create_crosshair(shape)

        self._selected_shape_ids = set(sids)
        if sids:
            self._selected_shape = self._shape_by_id.get(sids[-1])

        self._update_label_visibility()
        
    # ==================== Public API ====================

    def all_shapes(self) -> List[BaseShape]:
        """Get all shapes."""
        return list(self._shape_by_id.values())

    def clear_shapes(self) -> None:
        """Clear all shapes."""
        self.clear_selection()

        for shape in list(self._shape_by_id.values()):
            if self._shape_manager is not None:
                try:
                    self._shape_manager.remove_shape(shape)
                except AttributeError:
                    pass
            self._remove_shape_graphics(shape)

        self._hover_shape = None
        self._clipboard.clear()
        self._paste_count = 0
        self._update_label_visibility()
        self.stop_unlabeled_blink()

    def load_shapes(self, shapes: List[BaseShape]) -> None:
        """Load shapes from list."""
        self.clear_shapes()

        for shape in shapes:
            if self._shape_manager is not None:
                try:
                    self._shape_manager.add_shape(shape)
                except AttributeError:
                    pass
            self._add_shape_from_model(shape)

        self._refresh_all_handles()
        if not self.has_unlabeled_shapes():
            self.stop_unlabeled_blink()

    def _emit_shapes_changed(self) -> None:
        """Emit shapes changed signal."""
        self.shapesChanged.emit()