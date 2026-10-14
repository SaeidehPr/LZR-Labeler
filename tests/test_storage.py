import json
from unittest.mock import patch

import pytest

from lzr_labeler.core.annotation_store import AnnotationError, AnnotationStore
from lzr_labeler.core.shapes import CircleShape, PolygonShape, RectShape


def rectangle():
    return RectShape('object', '#ffffff', 'rect', 1, 2, 30, 40)


@pytest.mark.parametrize('shape', [
    rectangle(), CircleShape('circle', '#ffffff', 'circle', 5, 6, 3),
    PolygonShape('polygon', '#ffffff', 'poly', [(0, 0), (5, 0), (5, 5)]),
])
def test_round_trip(tmp_path, shape):
    store = AnnotationStore()
    image = tmp_path / 'sample.png'
    assert store.save(image, [shape])
    assert store.load(image, lambda _: '#ffffff') == [shape]


def test_same_stem_images_are_independent(tmp_path):
    store = AnnotationStore()
    a, b = tmp_path/'board.png', tmp_path/'board.jpg'
    assert store.save(a, [rectangle()])
    assert store.save(b, [])
    assert len(store.load(a, lambda _: '#ffffff')) == 1
    assert store.load(b, lambda _: '#ffffff') == []


def test_failed_replace_preserves_previous_file(tmp_path):
    store = AnnotationStore()
    image = tmp_path/'board.png'
    assert store.save(image, [rectangle()])
    before = store.json_path_for(image).read_bytes()
    with patch('lzr_labeler.core.annotation_store.os.replace', side_effect=OSError('disk error')):
        assert not store.save(image, [])
    assert store.json_path_for(image).read_bytes() == before
    assert not list((tmp_path/'Labels').glob('*.tmp'))


def test_legacy_import_and_empty_save(tmp_path):
    store = AnnotationStore()
    image = tmp_path/'board.png'
    folder = tmp_path/'Labels'
    folder.mkdir()
    legacy = folder/'board.json'
    legacy.write_text(json.dumps({'image': 'board', 'annotations': [store._shape_to_dict(rectangle())]}))
    assert len(store.load(image, lambda _: '#ffffff')) == 1
    assert store.save(image, [])
    assert store.load(image, lambda _: '#ffffff') == []
    assert legacy.exists()


def test_ambiguous_legacy_file_is_rejected(tmp_path):
    for name in ['board.png', 'board.jpg']:
        (tmp_path/name).touch()
    (tmp_path/'Labels').mkdir()
    (tmp_path/'Labels/board.json').write_text('{"annotations": []}')
    with pytest.raises(AnnotationError, match='Ambiguous'):
        AnnotationStore().load(tmp_path/'board.png', lambda _: '#ffffff')


@pytest.mark.parametrize('payload', [[], {'annotations': {}},
    {'annotations': [{'label': 'a', 'shape': 'circle', 'center': [1], 'diameter': 2}]},
    {'annotations': [{'label': 'a', 'shape': 'rect', 'points': [[0, 0], [float('nan'), 2]]}]},
    {'annotations': [{'label': 'a', 'shape': 'unknown'}]},
    {'schema_version': 99, 'annotations': []},
])
def test_invalid_payload_is_rejected_without_writes(tmp_path, payload):
    store = AnnotationStore()
    image = tmp_path/'board.png'
    (tmp_path/'Labels').mkdir()
    target = store.json_path_for(image)
    target.write_text(json.dumps(payload))
    before = target.read_bytes()
    with pytest.raises(AnnotationError):
        store.load(image, lambda _: '#ffffff')
    assert target.read_bytes() == before


def test_failed_directory_creation_is_reported(tmp_path):
    (tmp_path/'Labels').write_text('not a directory')
    store = AnnotationStore()
    assert not store.save(tmp_path/'board.png', [rectangle()])
    assert store.last_error
