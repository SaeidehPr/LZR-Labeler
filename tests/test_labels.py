from lzr_labeler.core.label_manager import LabelManager


def test_general_preset_has_no_pcb_labels(tmp_path):
    manager = LabelManager(tmp_path, preset='general')
    assert manager.all_defects == []
    manager.add_defect('Person', '#ff0000')
    restored = LabelManager(tmp_path, preset='general')
    assert restored.exists('Person')


def test_pcb_preset_is_available(tmp_path):
    assert len(LabelManager(tmp_path, preset='pcb').default_defects) > 0
