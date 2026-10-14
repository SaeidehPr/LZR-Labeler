from unittest.mock import patch

from PySide6.QtGui import QCloseEvent

from lzr_labeler.core.annotation_store import AnnotationStore
from lzr_labeler.core.shapes import RectShape
from lzr_labeler.ui.main_window import MainWindow


def make_window(tmp_path, monkeypatch):
    monkeypatch.setenv('LZR_LABELER_CONFIG_DIR', str(tmp_path/'config'))
    monkeypatch.setattr(MainWindow, '_init_ai_model', lambda self: None)
    return MainWindow()


def test_load_does_not_autosave_partial_canvas(app, tmp_path, monkeypatch):
    window = make_window(tmp_path, monkeypatch)
    image = tmp_path/'image.png'
    shape = RectShape('object', '#ffffff', 'rect', 1, 2, 20, 30)
    store = AnnotationStore()
    assert store.save(image, [shape])
    before = store.json_path_for(image).read_bytes()
    window._canvas_image_path = image
    with patch.object(window._annotation_store, 'save') as save:
        window._load_annotations(image)
        save.assert_not_called()
    assert len(window.canvas.all_shapes()) == 1
    assert store.json_path_for(image).read_bytes() == before
    window._canvas_image_path = None
    window.close()


def test_bad_file_is_protected_from_autosave(app, tmp_path, monkeypatch):
    window = make_window(tmp_path, monkeypatch)
    image = tmp_path/'image.png'
    target = AnnotationStore().json_path_for(image)
    target.parent.mkdir()
    target.write_text('{broken')
    window._canvas_image_path = image
    with patch('lzr_labeler.ui.main_window.QMessageBox.warning'):
        window._load_annotations(image)
    assert not window.canvas.isEnabled()
    window._save_annotations()
    assert target.read_text() == '{broken'
    window.close()


def test_failed_save_blocks_navigation_and_close(app, tmp_path, monkeypatch):
    window = make_window(tmp_path, monkeypatch)
    window._image_paths = [tmp_path/'a.png', tmp_path/'b.png']
    window._current_index = 0
    window._canvas_image_path = window._image_paths[0]
    with patch.object(window._annotation_store, 'save', return_value=False), \
         patch('lzr_labeler.ui.main_window.QMessageBox.warning'), \
         patch.object(window, '_load_image_async') as load:
        window._on_next()
        assert window._current_index == 0
        load.assert_not_called()
        event = QCloseEvent()
        window.closeEvent(event)
        assert not event.isAccepted()
    window._canvas_image_path = None
    window.close()


def test_stale_ai_results_are_discarded(app, tmp_path, monkeypatch):
    window = make_window(tmp_path, monkeypatch)
    window._canvas_image_path = tmp_path/'new.png'
    window._ai_image_path = tmp_path/'old.png'
    window._ai_busy = True
    window._on_ai_detection_finished([object()])
    assert not window._ai_busy
    assert window.canvas.all_shapes() == []
    window._canvas_image_path = None
    window.close()

