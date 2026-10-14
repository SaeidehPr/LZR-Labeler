"""Versioned JSON annotation storage with atomic saves and legacy import."""
from __future__ import annotations

import json
import logging
import math
import os
import tempfile
from pathlib import Path
from typing import Callable

from lzr_labeler.core.shapes import BaseShape, CircleShape, PolygonShape, RectShape

logger = logging.getLogger(__name__)
IMAGE_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.bmp', '.tif', '.tiff'}


class AnnotationError(ValueError):
    """An annotation file cannot be safely interpreted."""


class AnnotationStore:
    def __init__(self):
        self.last_error = ''

    def labels_dir_for(self, image_path: Path) -> Path:
        return image_path.parent / 'Labels'

    def json_path_for(self, image_path: Path) -> Path:
        return self.labels_dir_for(image_path) / f'{image_path.name}.json'

    def _read_path(self, image_path: Path) -> Path:
        current = self.json_path_for(image_path)
        if current.exists():
            return current
        legacy = self.labels_dir_for(image_path) / f'{image_path.stem}.json'
        if legacy.exists():
            matches = [p for p in image_path.parent.iterdir()
                       if p.is_file() and p.stem == image_path.stem
                       and p.suffix.lower() in IMAGE_EXTENSIONS]
            if len(matches) > 1:
                raise AnnotationError(f'Ambiguous legacy annotation file: {legacy}. '
                                      'Multiple images have the same stem; assign the file manually.')
            return legacy
        return current

    def save(self, image_path: Path, shapes: list[BaseShape]) -> bool:
        temporary = None
        self.last_error = ''
        try:
            records = [self._shape_to_dict(shape) for shape in shapes]
            for record in records:
                self._dict_to_shape(record, lambda _: '#ffffff')
            payload = {'schema_version': 2, 'image': image_path.name, 'annotations': records}
            encoded = json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False)
            target = self.json_path_for(image_path)
            target.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=target.parent,
                                             prefix=target.name + '.', suffix='.tmp',
                                             delete=False) as stream:
                temporary = Path(stream.name)
                stream.write(encoded)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, target)
            # Empty lists are persisted so legacy files cannot resurrect deleted shapes.
            return True
        except (OSError, ValueError, TypeError, AttributeError) as exc:
            self.last_error = f'Could not save {image_path.name}: {exc}'
            logger.warning(self.last_error)
            return False
        finally:
            if temporary is not None:
                try:
                    temporary.unlink(missing_ok=True)
                except OSError:
                    logger.warning('Could not remove temporary annotation file: %s', temporary)

    def load(self, image_path: Path, color_resolver: Callable,
             label_resolver: Callable | None = None) -> list[BaseShape]:
        try:
            path = self._read_path(image_path)
            if not path.exists():
                return []
            payload = json.loads(path.read_text(encoding='utf-8'))
            if not isinstance(payload, dict):
                raise AnnotationError('Expected a JSON object.')
            version = payload.get('schema_version', 1)
            if type(version) is not int or version not in (1, 2):
                raise AnnotationError(f'Unsupported schema version: {version}')
            if version == 2 and payload.get('image') != image_path.name:
                raise AnnotationError('Annotation image name does not match the selected image.')
            records = payload.get('annotations')
            if not isinstance(records, list):
                raise AnnotationError('annotations must be a list.')
            return [self._dict_to_shape(r, color_resolver, label_resolver) for r in records]
        except (OSError, ValueError, TypeError, KeyError, IndexError) as exc:
            raise AnnotationError(f'Cannot read annotations for {image_path.name}: {exc}') from exc

    def get_labels_from_file(self, image_path: Path, label_resolver=None) -> list[str]:
        return list(dict.fromkeys(s.label for s in self.load(
            image_path, lambda _: '#ffffff', label_resolver)))

    @staticmethod
    def _number(value) -> float:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise AnnotationError('Coordinates must be numbers.')
        if not math.isfinite(value):
            raise AnnotationError('Coordinates must be finite.')
        return float(value)

    def _point(self, value):
        if not isinstance(value, (list, tuple)) or len(value) != 2:
            raise AnnotationError('Each point must contain two coordinates.')
        return tuple(self._number(v) for v in value)

    def _dict_to_shape(self, data, color_resolver, label_resolver=None):
        if not isinstance(data, dict) or not isinstance(data.get('label'), str):
            raise AnnotationError('Each shape requires a text label.')
        label = data['label'].strip()
        if not label:
            raise AnnotationError('Shape labels must not be empty.')
        label = label_resolver(label) if label_resolver else label
        common = dict(label=label, color=color_resolver(label), shape_type=data.get('shape'))
        if data.get('shape') == 'circle':
            cx, cy = self._point(data['center'])
            diameter = self._number(data['diameter'])
            if diameter <= 0:
                raise AnnotationError('Circle diameter must be positive.')
            return CircleShape(**common, cx=cx, cy=cy, r=diameter / 2)
        if data.get('shape') in ('rect', 'poly'):
            if not isinstance(data.get('points'), list):
                raise AnnotationError('points must be a list.')
            points = [self._point(p) for p in data['points']]
            if data['shape'] == 'rect':
                if len(points) != 2:
                    raise AnnotationError('A rectangle requires two corners.')
                (x1, y1), (x2, y2) = points
                if x1 == x2 or y1 == y2:
                    raise AnnotationError('A rectangle must have nonzero area.')
                return RectShape(**common, x1=x1, y1=y1, x2=x2, y2=y2)
            if len(points) < 3:
                raise AnnotationError('A polygon requires at least three points.')
            return PolygonShape(**common, points=points)
        raise AnnotationError(f"Unsupported shape: {data.get('shape')}")

    def _shape_to_dict(self, shape):
        data = {'label': shape.label}
        if isinstance(shape, RectShape):
            return dict(data, shape='rect', points=[[shape.x1, shape.y1], [shape.x2, shape.y2]])
        if isinstance(shape, CircleShape):
            return dict(data, shape='circle', center=[shape.cx, shape.cy], diameter=shape.r * 2)
        if isinstance(shape, PolygonShape):
            return dict(data, shape='poly', points=shape.points)
        raise AnnotationError(f'Unsupported shape class: {type(shape).__name__}')
