from __future__ import annotations

from PySide6.QtCore import QRect, Signal, Qt
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from lzr_labeler.theme import (
    current_mode,
    get_palette,
    groupbox_with_border_style,
    button_outlined_style,
    frame_viewport_overlay_style,
)
from lzr_labeler.theme.palette import ThemeMode


class MonitoringBox(QGroupBox):
    """Grid navigator + viewport overlay (theme-aware)."""

    gridSizeChanged = Signal(int)        # e.g., 1, 4, 8, 16
    cellSelected = Signal(int, int)      # row, col

    def __init__(self, parent=None):
        super().__init__("Monitoring Box", parent)

        self._mode: ThemeMode = current_mode()

        self.GRID_SIZE = 220
        self.cell_buttons: dict[tuple[int, int], QPushButton] = {}
        self._current_size: int = 1
        self._selected_cell: tuple[int, int] | None = None

        # --- layout ---
        root = QVBoxLayout(self)
        root.setContentsMargins(2, 2, 2, 2)

        top = QHBoxLayout()
        top.setContentsMargins(2, 2, 2, 2)

        self.btn_1 = QPushButton("1")
        self.btn_4 = QPushButton("4×4")
        self.btn_8 = QPushButton("8×8")
        self.btn_16 = QPushButton("16×16")

        for b in (self.btn_1, self.btn_4, self.btn_8, self.btn_16):
            b.setCursor(Qt.PointingHandCursor)
            b.setCheckable(True)

        top.addWidget(self.btn_1)
        top.addWidget(self.btn_4)
        top.addWidget(self.btn_8)
        top.addWidget(self.btn_16)
        root.addLayout(top)

        self.grid_widget = QWidget(self)
        self.grid_widget.setFixedSize(self.GRID_SIZE, self.GRID_SIZE)

        self.grid_layout = QGridLayout(self.grid_widget)
        self.grid_layout.setContentsMargins(0, 0, 0, 0)
        self.grid_layout.setSpacing(0)

        root.addWidget(self.grid_widget, alignment=Qt.AlignCenter)

        # --- overlay (viewport rectangle) ---
        self._viewport_overlay = QFrame(self.grid_widget)
        self._viewport_overlay.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self._viewport_overlay.hide()

        # --- signals ---
        self.btn_1.clicked.connect(lambda: self._on_size_button_clicked(1))
        self.btn_4.clicked.connect(lambda: self._on_size_button_clicked(4))
        self.btn_8.clicked.connect(lambda: self._on_size_button_clicked(8))
        self.btn_16.clicked.connect(lambda: self._on_size_button_clicked(16))

        # Apply initial theme
        self.set_theme_mode(self._mode)

        # Build initial grid and default selection
        self._build_grid(self._current_size)
        self._select_cell(0, 0, emit=True)

    # ---------------------------
    # Theme API
    # ---------------------------

    def set_theme_mode(self, mode: ThemeMode) -> None:
        self._mode = mode
        self._apply_styles(mode)
        self._refresh_button_styles()
        self._viewport_overlay.update()
        self.update()

    def _apply_styles(self, mode: ThemeMode) -> None:
        p = get_palette(mode)

        # One stylesheet for this module
        self.setStyleSheet("\n".join([
            groupbox_with_border_style(p),
            button_outlined_style(p),
            frame_viewport_overlay_style(p),
            """
            QPushButton#gridCell {{
                border: none;
                padding: 0px;
                margin: 0px;
                background-color: transparent;
            }}

            QPushButton#gridCell:hover {{
                background-color: {p.background_hover};
            }}

            QPushButton#gridCell:checked {{
                background-color: {p.background_selected};
            }}
            """
        ]))

        # Overlay uses QFrame base selector from frame_viewport_overlay_style(p)
        # so we only need to ensure its class stays QFrame.
        self._viewport_overlay.setStyleSheet(frame_viewport_overlay_style(p))

    def _refresh_button_styles(self) -> None:
        # Re-apply checked states so QSS :checked visuals stay consistent
        mapping = {1: self.btn_1, 4: self.btn_4, 8: self.btn_8, 16: self.btn_16}
        for n, b in mapping.items():
            b.setChecked(n == self._current_size)

        # Force repaint for grid buttons as well
        for btn in self.cell_buttons.values():
            btn.update()

    # ---------------------------
    # Public API
    # ---------------------------

    def set_viewport_norm(self, nx: float, ny: float, nw: float, nh: float) -> None:
        """Update overlay from normalized viewport coords (0..1)."""
        if not self.cell_buttons or self._current_size <= 0:
            self._viewport_overlay.hide()
            return

        grid_rect = self._grid_rect()
        if grid_rect.isNull() or grid_rect.width() <= 0 or grid_rect.height() <= 0:
            self._viewport_overlay.hide()
            return

        nx = float(max(0.0, min(1.0, nx)))
        ny = float(max(0.0, min(1.0, ny)))
        nw = float(max(0.0, min(1.0, nw)))
        nh = float(max(0.0, min(1.0, nh)))

        x = grid_rect.left() + int(round(nx * grid_rect.width()))
        y = grid_rect.top() + int(round(ny * grid_rect.height()))
        w = max(1, int(round(nw * grid_rect.width())))
        h = max(1, int(round(nh * grid_rect.height())))

        if x < grid_rect.left():
            x = grid_rect.left()
        if y < grid_rect.top():
            y = grid_rect.top()

        max_right = grid_rect.right() + 1
        max_bottom = grid_rect.bottom() + 1

        if x + w > max_right:
            w = max(1, max_right - x)
        if y + h > max_bottom:
            h = max(1, max_bottom - y)

        self._viewport_overlay.setGeometry(x, y, w, h)
        self._viewport_overlay.show()
        self._viewport_overlay.raise_()

        self._sync_selected_cell_to_overlay()

    # ---------------------------
    # Internals
    # ---------------------------

    def _on_size_button_clicked(self, n: int) -> None:
        if n == self._current_size:
            return

        self._current_size = n
        self._build_grid(n)
        self.gridSizeChanged.emit(n)
        self._select_cell(0, 0, emit=True)
        self._refresh_button_styles()

    def _build_grid(self, n: int) -> None:
        # Clear previous
        for btn in self.cell_buttons.values():
            btn.setParent(None)
            btn.deleteLater()
        self.cell_buttons.clear()

        self._viewport_overlay.hide()

        # Compute cell size so the grid is centered
        spacing = self.grid_layout.spacing()
        total_spacing = spacing * (n - 1)
        cell_size = max(1, (self.GRID_SIZE - total_spacing) // max(1, n))

        actual_size = cell_size * n + total_spacing
        extra = max(0, self.GRID_SIZE - actual_size)

        left = top = extra // 2
        right = bottom = extra - left
        self.grid_layout.setContentsMargins(left, top, right, bottom)

        for r in range(n):
            for c in range(n):
                btn = QPushButton("", self.grid_widget)
                btn.setObjectName("gridCell")
                btn.setCheckable(True)
                btn.setFixedSize(cell_size, cell_size)
                btn.setCursor(Qt.PointingHandCursor)
                btn.clicked.connect(self._make_cell_handler(r, c))

                self.grid_layout.addWidget(btn, r, c)
                self.cell_buttons[(r, c)] = btn

        self._selected_cell = None

        # Ensure new buttons pick up current theme
        self._refresh_button_styles()

    def _select_cell(self, r: int, c: int, *, emit: bool = False) -> None:
        if (r, c) not in self.cell_buttons:
            return

        for (rr, cc), b in self.cell_buttons.items():
            b.setChecked((rr, cc) == (r, c))

        self._selected_cell = (r, c)
        if emit:
            self.cellSelected.emit(r, c)

    def _make_cell_handler(self, r: int, c: int):
        def handler():
            self._select_cell(r, c, emit=True)
        return handler

    def _grid_rect(self) -> QRect:
        """Return union rect of all cell button geometries (in grid_widget coords)."""
        rects = [b.geometry() for b in self.cell_buttons.values()]
        if not rects:
            return QRect()
        united = rects[0]
        for r in rects[1:]:
            united = united.united(r)
        return united

    def _sync_selected_cell_to_overlay(self) -> None:
        if self._viewport_overlay.isHidden():
            return

        overlay_rect = self._viewport_overlay.geometry()
        best_cell: tuple[int, int] | None = None
        best_area = -1

        for (rr, cc), btn in self.cell_buttons.items():
            inter = overlay_rect.intersected(btn.geometry())
            area = inter.width() * inter.height()
            if area > best_area:
                best_area = area
                best_cell = (rr, cc)

        if best_cell is None:
            return

        if best_cell != self._selected_cell:
            self._select_cell(best_cell[0], best_cell[1], emit=False)
