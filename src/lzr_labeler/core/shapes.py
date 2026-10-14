from __future__ import annotations

from dataclasses import dataclass
from typing import List, Literal, Tuple, Iterator

from PySide6.QtCore import QObject, Signal

# Type definitions
ShapeType = Literal["rect", "circle", "poly"]
Point = Tuple[float, float]


# ==================== Shape Dataclasses ====================

@dataclass
class BaseShape:
    """Base class for all shapes."""
    label: str
    color: str
    shape_type: ShapeType


@dataclass
class RectShape(BaseShape):
    """Rectangle shape with corner coordinates."""
    x1: float
    y1: float
    x2: float
    y2: float


@dataclass
class CircleShape(BaseShape):
    """Circle shape with center and radius."""
    cx: float
    cy: float
    r: float


@dataclass
class PolygonShape(BaseShape):
    """Polygon shape with list of points."""
    points: List[Point]


# ==================== Shape Model (Reactive Container) ====================

class ShapeModel(QObject):
    """
    Reactive shape container with Qt signals.
    
    Emits signals automatically when shapes are added, removed, or cleared.
    This replaces the old ShapeManager class.
    
    Signals:
        shapesChanged: Emitted whenever the shape list changes
        shapeAdded: Emitted when a shape is added (passes the shape)
        shapeRemoved: Emitted when a shape is removed (passes the shape)
    """
    
    # Signals
    shapesChanged = Signal()
    shapeAdded = Signal(object)
    shapeRemoved = Signal(object)

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self._shapes: List[BaseShape] = []

    # ==================== Public Methods ====================

    @property
    def shapes(self) -> List[BaseShape]:
        """Get list of all shapes (for backward compatibility)."""
        return self._shapes

    def all(self) -> List[BaseShape]:
        """Get a copy of all shapes."""
        return list(self._shapes)

    def add_shape(self, shape: BaseShape) -> None:
        """
        Add a shape to the model.
        
        Emits shapeAdded and shapesChanged signals.
        """
        self._shapes.append(shape)
        self.shapeAdded.emit(shape)
        self.shapesChanged.emit()

    def remove_shape(self, shape: BaseShape) -> bool:
        """
        Remove a shape from the model.
        
        Returns:
            True if shape was removed, False if not found.
            
        Emits shapeRemoved and shapesChanged signals if successful.
        """
        if shape in self._shapes:
            self._shapes.remove(shape)
            self.shapeRemoved.emit(shape)
            self.shapesChanged.emit()
            return True
        return False

    def clear(self) -> None:
        """
        Remove all shapes.
        
        Emits shapesChanged signal if there were shapes to clear.
        """
        if not self._shapes:
            return
        self._shapes.clear()
        self.shapesChanged.emit()

    def serialize(self) -> List[dict]:
        """
        Serialize all shapes to a list of dictionaries.
        
        For backward compatibility with old ShapeManager.
        """
        out = []
        for s in self._shapes:
            d = s.__dict__.copy()
            d["shape_type"] = s.shape_type
            out.append(d)
        return out

    # ==================== Dunder Methods ====================

    def __len__(self) -> int:
        """Return number of shapes."""
        return len(self._shapes)

    def __iter__(self) -> Iterator[BaseShape]:
        """Iterate over shapes."""
        return iter(self._shapes)

    def __contains__(self, shape: BaseShape) -> bool:
        """Check if shape is in model."""
        return shape in self._shapes

