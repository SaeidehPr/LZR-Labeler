from PySide6.QtCore import QEventLoop, QObject, QThread, QTimer, Slot
from lzr_labeler.ui.main_window import MainWindow


def test_detection_runs_on_worker_thread(app, tmp_path, monkeypatch):
    monkeypatch.setenv('LZR_LABELER_CONFIG_DIR', str(tmp_path/'config'))
    monkeypatch.setattr(MainWindow, '_init_ai_model', lambda self: None)
    window = MainWindow()
    seen = []
    loop = QEventLoop()

    class Probe(QObject):
        @Slot(object)
        def receive(self, image):
            seen.append(QThread.currentThread() is window._ai_thread)
            loop.quit()

    probe = Probe()
    probe.moveToThread(window._ai_thread)
    window._ai_thread.finished.connect(probe.deleteLater)
    window.requestDetection.disconnect(window._ai_manager.detect)
    window.requestDetection.connect(probe.receive)
    timer = QTimer()
    timer.setSingleShot(True)
    timer.timeout.connect(loop.quit)
    timer.start(3000)
    window.requestDetection.emit(None)
    loop.exec()
    timer.stop()
    window.close()
    assert seen == [True]
