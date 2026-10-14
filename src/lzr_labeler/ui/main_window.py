from __future__ import annotations

from pathlib import Path
from typing import Optional

import numpy as np

from PySide6.QtCore import QThread, Qt, Signal
from PySide6.QtGui import (
    QIcon, 
    QImage, 
    QCloseEvent,
    QKeySequence, 
    QShortcut,
)
from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QStatusBar,
    QWidget,
    QHBoxLayout,
    QVBoxLayout,
    QFileDialog,
    QMessageBox,
)

from lzr_labeler.core.image_loader import ImageLoaderWorker
from lzr_labeler.core.label_manager import LabelManager
from lzr_labeler.core.shapes import RectShape, ShapeModel
from lzr_labeler.core.annotation_store import AnnotationStore, AnnotationError
from lzr_labeler.core.ai_worker import AIManager
from lzr_labeler.core.paths import resource_path

from lzr_labeler.ui.widgets.selection_panel import SelectionPanel
from lzr_labeler.ui.widgets.canvas import Canvas
from lzr_labeler.ui.widgets.shape_panel import ShapeBox
from lzr_labeler.ui.widgets.log_panel import MonitoringBox
from lzr_labeler.ui.widgets.current_label_panel import CurrentLabelBox
from lzr_labeler.ui.widgets.setting_panel import SettingBox
from lzr_labeler.ui.widgets.defect_types_panel import DefectTypesPanel
from lzr_labeler.ui.widgets.info_dialog import show_info_dialog

from lzr_labeler.theme import apply_theme

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff"}
from lzr_labeler.core.paths import base_dir

class MainWindow(QMainWindow):
    """Main application window."""

    def find_single_pth_in_models() -> str:
        models_dir = Path(base_dir()) / "models"
        pths = list(models_dir.glob("*.pth"))
        return str(pths[0]) if pths else ""  

    DEFAULT_MODEL_PATH = find_single_pth_in_models()
    DEFAULT_META_PATH = resource_path("models/meta_info.json")

    requestModelLoad = Signal()
    requestDetection = Signal(object)

    def __init__(self, preset="general", models_dir=None) -> None:
        super().__init__()

        # Window setup
        self._setup_window()

        # Core managers
        self._label_manager = LabelManager(preset=preset)
        self._shape_manager = ShapeModel()
        self._annotation_store = AnnotationStore()
        self._loading_annotations = False
        self._annotation_read_error = False

        # AI manager
        self._ai_manager = AIManager()
        self._ai_thread = QThread(self)
        self._ai_manager.moveToThread(self._ai_thread)
        self.requestModelLoad.connect(self._ai_manager.load_model)
        self.requestDetection.connect(self._ai_manager.detect)
        self._ai_thread.finished.connect(self._ai_manager.cleanup)
        self._ai_thread.finished.connect(self._ai_manager.deleteLater)
        self._ai_thread.start()
        self._ai_busy = False
        self._ai_image_path = None
        if models_dir is not None:
            candidates = sorted(Path(models_dir).glob("*.pth"))
            self.DEFAULT_MODEL_PATH = str(candidates[0]) if len(candidates) == 1 else ""
            self.DEFAULT_META_PATH = str(Path(models_dir) / "meta_info.json")
        self._ai_model_loaded = False
        self._current_qimage: Optional[QImage] = None

        # Image state
        self._image_paths: list[Path] = []
        self._current_index: int = -1
        self._current_image_path: Optional[Path] = None

        # Async loader
        self._loader_thread: Optional[QThread] = None
        self._loader_worker: Optional[ImageLoaderWorker] = None
        
        # ============ FIX: Track which image the canvas actually shows ============
        # _current_image_path = what we WANT to show (set immediately on navigation)
        # _canvas_image_path = what canvas ACTUALLY shows (set after load completes)
        self._canvas_image_path: Optional[Path] = None
        # =========================================================================

        # Build UI
        self._setup_ui()
        self._connect_signals()

        self._setup_global_shortcuts()

        # Try to load AI model
        self._init_ai_model()

    # ==================== Setup ====================

    def _setup_window(self) -> None:
        """Configure main window properties."""
        self.setWindowTitle("LZR Labelr (PySide6 Edition)")
        self.setWindowIcon(QIcon(resource_path("assets/icons/LZR icon.png")))
        self.resize(1200, 700)

    def _setup_ui(self) -> None:
        """Build the UI layout."""
        central = QWidget(self)
        self.setCentralWidget(central)

        root_layout = QVBoxLayout(central)
        root_layout.setContentsMargins(2, 2, 2, 2)

        top_layout = QHBoxLayout()
        top_layout.setSpacing(4)
        root_layout.addLayout(top_layout, stretch=1)

        # Left: Selection panel
        self._selection_panel = self._create_selection_panel()
        top_layout.addWidget(self._selection_panel)

        # Middle-left: Controls column
        controls_column = self._create_controls_column()
        top_layout.addWidget(controls_column)

        # Center: Canvas
        self._canvas = Canvas(shape_manager=self._shape_manager)
        top_layout.addWidget(self._canvas, stretch=1)

        # Right: Defect types panel
        self._defect_panel = self._create_defect_panel()
        top_layout.addWidget(self._defect_panel)

        # Status bar
        status = QStatusBar(self)
        self.setStatusBar(status)
        status.showMessage("Ready")

    def _create_selection_panel(self) -> SelectionPanel:
        """Create and configure selection panel."""
        panel = SelectionPanel()
        panel.setFixedWidth(105)
        return panel

    def _create_controls_column(self) -> QWidget:
        """Create controls column with shape, monitor, label, and settings boxes."""
        column = QWidget()
        column.setFixedWidth(250)

        layout = QVBoxLayout(column)
        layout.setContentsMargins(2, 2, 2, 2)
        layout.setSpacing(4)

        self._shape_box = ShapeBox()
        self._monitor_box = MonitoringBox()
        self._current_label_box = CurrentLabelBox()
        self._setting_box = SettingBox()

        layout.addWidget(self._shape_box)
        layout.addWidget(self._monitor_box)
        layout.addWidget(self._current_label_box, 1)
        layout.addWidget(self._setting_box)

        return column

    def _create_defect_panel(self) -> DefectTypesPanel:
        """Create and configure defect types panel."""
        panel = DefectTypesPanel(self._label_manager, self)
        panel.setFixedWidth(250)
        return panel

    def _connect_signals(self) -> None:
        """Connect all signals between components."""
        # Selection panel -> MainWindow
        self._selection_panel.fileRequested.connect(self._on_file_requested)
        self._selection_panel.folderRequested.connect(self._on_folder_requested)
        self._selection_panel.prevRequested.connect(self._on_prev)
        self._selection_panel.nextRequested.connect(self._on_next)
        self._selection_panel.indexRequested.connect(self._on_index_requested)
        self._selection_panel.deleteRequested.connect(self._on_delete_requested)
        self._selection_panel.undoRequested.connect(self._canvas.undo)
        self._selection_panel.redoRequested.connect(self._canvas.redo)

        # AI button
        self._selection_panel.aiRequested.connect(self._on_ai_requested)

        # Selection panel <-> Canvas
        self._selection_panel.zoomFitRequested.connect(self._canvas.zoom_fit)
        self._selection_panel.zoomActualRequested.connect(self._canvas.zoom_actual)
        self._selection_panel.annotationToggled.connect(self._canvas.set_draw_enabled)
        self._selection_panel.editToggled.connect(self._canvas.set_edit_mode)
        self._canvas.annotationModeChanged.connect(self._selection_panel.set_annotation_checked)
        self._canvas.editModeChanged.connect(self._selection_panel.set_edit_checked)

        # Control boxes -> Canvas
        self._monitor_box.gridSizeChanged.connect(self._canvas.set_grid_divisions)
        self._monitor_box.cellSelected.connect(self._canvas.focus_on_grid_cell)
        self._shape_box.shapeChanged.connect(self._canvas.set_shape_mode)

        self._canvas.viewportChanged.connect(self._monitor_box.set_viewport_norm)

        # Settings -> AI Manager
        self._setting_box.confidenceChanged.connect(self._ai_manager.set_confidence_threshold)

        # Settings -> Theme
        self._setting_box.themeModeChanged.connect(self._on_theme_mode_changed)

        # Canvas -> MainWindow
        self._canvas.shapesChanged.connect(self._on_shapes_changed)

        # Current label box
        self._current_label_box.labelClicked.connect(self._on_label_row_clicked)

        # Defect panel -> MainWindow
        self._defect_panel.defectSelected.connect(self._on_defect_selected)
        self._defect_panel.defectAdded.connect(self._on_defect_added)

        # Canvas -> Defect panel
        self._canvas.applyRequested.connect(self._defect_panel.apply_pending)

        # AI manager signals
        self._ai_manager.modelLoaded.connect(self._on_ai_model_loaded)
        self._ai_manager.detectionFinished.connect(self._on_ai_detection_finished)
        self._ai_manager.detectionError.connect(self._on_ai_detection_error)
        self._ai_manager.progressUpdate.connect(self._on_ai_progress)

        # Initial refresh
        self._refresh_current_label_box()

        self._selection_panel.infoRequested.connect(self._on_info_requested)

    # ==================== Properties (for backward compatibility) ====================

    @property
    def canvas(self) -> Canvas:
        return self._canvas

    @property
    def selection_panel(self) -> SelectionPanel:
        return self._selection_panel

    @property
    def shape_box(self) -> ShapeBox:
        return self._shape_box

    @property
    def monitor_box(self) -> MonitoringBox:
        return self._monitor_box

    @property
    def current_label_box(self) -> CurrentLabelBox:
        return self._current_label_box

    @property
    def setting_box(self) -> SettingBox:
        return self._setting_box

    @property
    def defect_types_panel(self) -> DefectTypesPanel:
        return self._defect_panel

    @property
    def shape_manager(self) -> ShapeModel:
        return self._shape_manager

    # ==================== Shortcuts ====================
    def _setup_global_shortcuts(self) -> None:
        """Register global shape shortcuts."""
        self._sc_rect = QShortcut(QKeySequence("1"), self)
        self._sc_circle = QShortcut(QKeySequence("2"), self)
        self._sc_poly = QShortcut(QKeySequence("3"), self)

        for sc in (self._sc_rect, self._sc_circle, self._sc_poly):
            sc.setContext(Qt.ApplicationShortcut)

        self._sc_rect.activated.connect(lambda: self._select_shape_mode("rect"))
        self._sc_circle.activated.connect(lambda: self._select_shape_mode("circle"))
        self._sc_poly.activated.connect(lambda: self._select_shape_mode("poly"))


    def _select_shape_mode(self, mode: str) -> None:
        """Sync shape selection between ShapeBox UI and Canvas."""
        self._shape_box.set_mode(mode)
        self._canvas.set_shape_mode(mode)
        self.statusBar().showMessage(f"Shape mode: {mode}", 1500)

    # ==================== AI Integration ====================

    def _init_ai_model(self) -> None:
        """Initialize AI model on startup."""
        model_path = Path(self.DEFAULT_MODEL_PATH)
        meta_path = Path(self.DEFAULT_META_PATH)

        if not model_path.is_file():
            print(f"AI model not found at {model_path}")
            self._selection_panel.set_ai_enabled(False)
            return

        if not meta_path.exists():
            print(f"AI meta not found at {meta_path}")
            self._selection_panel.set_ai_enabled(False)
            return

        self._selection_panel.set_ai_loading(True)
        self._ai_manager.set_model_config(
            model_path=model_path,
            meta_path=meta_path,
            confidence_threshold=self._setting_box.confidence(),
        )
        self._ai_busy = True
        self._ai_thread.start()
        self.requestModelLoad.emit()

    def _on_ai_model_loaded(self, success: bool, message: str) -> None:
        """Handle AI model loaded signal."""
        self._ai_busy = False
        self._ai_model_loaded = success
        self._selection_panel.set_ai_loading(False)
        self._selection_panel.set_ai_enabled(success)

        if success:
            self.statusBar().showMessage(f"AI: {message}", 5000)
        else:
            self.statusBar().showMessage(f"AI Error: {message}", 5000)

    def _on_ai_requested(self) -> None:
        """Handle AI detection request."""
        if self._annotation_read_error or self._ai_busy:
            return
        if not self._ai_model_loaded:
            QMessageBox.warning(
                self,
                "AI Not Ready",
                "AI model is not loaded. Please check if the model file exists.",
            )
            return

        if self._current_qimage is None:
            QMessageBox.warning(
                self,
                "No Image",
                "Please load an image first.",
            )
            return

        # Convert QImage to numpy array
        image_array = self._qimage_to_numpy(self._current_qimage)
        if image_array is None:
            QMessageBox.warning(
                self,
                "Image Error",
                "Could not process the current image.",
            )
            return

        # Disable AI button during detection
        self._selection_panel.set_ai_enabled(False)
        self.statusBar().showMessage("Running AI detection...", 0)

        # Run detection
        self._ai_busy = True
        self._ai_image_path = self._canvas_image_path
        self.requestDetection.emit(image_array)

    def _on_ai_detection_finished(self, detections: list) -> None:
        """Apply results only to the image that initiated detection."""
        self._ai_busy = False
        if self._canvas_image_path != self._ai_image_path or self._annotation_read_error:
            self._selection_panel.set_ai_enabled(True)
            self.statusBar().showMessage("AI results discarded: the image changed.", 5000)
            return
        self._selection_panel.set_ai_enabled(True)

        if not detections:
            self.statusBar().showMessage("AI: No defects detected", 3000)
            return

        existing_shapes = self._canvas.all_shapes()
        
        new_shapes = []
        for det in detections:
            self._defect_panel.ensure_defect_type(det.label)
            color = self._label_manager.get_color(det.label)

            x1, y1, x2, y2 = det.bbox
            shape = RectShape(
                label=det.label,
                color=color,
                shape_type="rect",
                x1=x1,
                y1=y1,
                x2=x2,
                y2=y2,
            )
            new_shapes.append(shape)

        all_shapes = existing_shapes + new_shapes
        
        self._canvas.load_shapes(all_shapes)

        self.statusBar().showMessage(f"AI: Added {len(new_shapes)} detections", 5000)
        self._save_annotations()

    def _on_ai_detection_error(self, error: str) -> None:
        """Handle AI detection error."""
        self._ai_busy = False
        self._selection_panel.set_ai_enabled(True)
        self.statusBar().showMessage(f"AI Error: {error}", 5000)
        QMessageBox.warning(self, "AI Detection Error", error)

    def _on_ai_progress(self, message: str) -> None:
        """Handle AI progress updates."""
        self.statusBar().showMessage(f"AI: {message}", 0)

    def _qimage_to_numpy(self, qimage: QImage) -> Optional[np.ndarray]:
        """Convert QImage to numpy array (RGB)."""
        try:
            # Convert to RGB format if needed
            if qimage.format() != QImage.Format_RGB888:
                qimage = qimage.convertToFormat(QImage.Format_RGB888)

            width = qimage.width()
            height = qimage.height()
            bytes_per_line = qimage.bytesPerLine()

            # Get pointer to image data
            ptr = qimage.bits()
            
            # Convert to numpy array
            arr = np.array(ptr).reshape(height, bytes_per_line)
            
            # Remove padding if any
            arr = arr[:, :width * 3]
            arr = arr.reshape(height, width, 3)

            return arr.copy()

        except Exception as e:
            print(f"Error converting QImage to numpy: {e}")
            return None

    # ==================== Save/Load Annotations ====================

    def _save_annotations(self) -> bool:
        """Save before navigation; never overwrite a file that failed to load."""
        if self._loading_annotations or self._canvas_image_path is None:
            return True
        if self._annotation_read_error:
            return True  # Failed loads are read-only until another image is opened.
        if self._annotation_store.save(self._canvas_image_path, self._canvas.all_shapes()):
            return True
        QMessageBox.warning(self, "Annotations not saved", self._annotation_store.last_error)
        return False

    def _load_annotations(self, image_path: Path) -> None:
        self._loading_annotations = True
        self._annotation_read_error = False
        self._canvas.setEnabled(True)
        try:
            # Parse completely before changing the current canvas.
            shapes = self._annotation_store.load(
                image_path, self._label_manager.get_color,
                self._label_manager.canonicalize,
            )
            for shape in shapes:
                if shape.label != self._canvas.DEFAULT_LABEL:
                    self._defect_panel.ensure_defect_type(shape.label)
            self._canvas.load_shapes(shapes)
        except AnnotationError as exc:
            self._annotation_read_error = True
            self._canvas.clear_shapes()
            self._canvas.setEnabled(False)
            QMessageBox.warning(
                self, "Cannot load annotations",
                f"{exc}\n\nThis image is read-only. The annotation file has not been changed.",
            )
        finally:
            self._loading_annotations = False

    # ==================== File/Folder Navigation ====================

    def _on_file_requested(self) -> None:
        """Handle file selection request."""
        if not self._save_annotations():
            return

        path_str, _ = QFileDialog.getOpenFileName(
            self,
            "Select image file",
            "",
            "Images (*.png *.jpg *.jpeg *.bmp *.tif *.tiff)",
        )

        if not path_str:
            return

        self._image_paths = [Path(path_str)]
        self._current_index = 0

        # Single-file mode -> hide folder jump box
        self._selection_panel.reset_navigation()

        self._load_image_async(self._image_paths[0])

    def _on_folder_requested(self) -> None:
        """Handle folder selection request."""
        if not self._save_annotations():
            return

        folder_str = QFileDialog.getExistingDirectory(self, "Select folder with images", "")
        if not folder_str:
            return

        root = Path(folder_str)
        files = sorted(
            p for p in root.iterdir()
            if p.is_file() and p.suffix.lower() in IMAGE_EXTENSIONS
        )

        if not files:
            QMessageBox.information(self, "No images", "No image files in this folder.")
            self._selection_panel.reset_navigation()
            return

        self._image_paths = files
        self._current_index = 0

        # Folder mode -> show jump box
        self._selection_panel.set_navigation_range(len(self._image_paths))
        self._selection_panel.set_navigation_value(self._current_index + 1)
        self._selection_panel.set_navigation_visible(True)

        self._load_image_async(self._image_paths[0])

    def _on_index_requested(self, value: int) -> None:
        """Jump directly to a specific image number (1-based)."""
        if not self._image_paths:
            return

        if not self._guard_unlabeled():
            # restore visible value if navigation was blocked
            self._selection_panel.set_navigation_value(self._current_index + 1)
            return

        target_index = max(0, min(int(value) - 1, len(self._image_paths) - 1))

        if target_index == self._current_index:
            self._selection_panel.set_navigation_value(self._current_index + 1)
            return

        if not self._save_annotations():
            return
        self._current_index = target_index
        self._selection_panel.set_navigation_value(self._current_index + 1)
        self._load_image_async(self._image_paths[self._current_index])

    def _on_prev(self) -> None:
        """Navigate to previous image."""
        if not self._image_paths:
            return

        if not self._guard_unlabeled():
            return

        if not self._save_annotations():
            return
        self._current_index = (self._current_index - 1) % len(self._image_paths)
        self._selection_panel.set_navigation_value(self._current_index + 1)
        self._load_image_async(self._image_paths[self._current_index])

    def _on_next(self) -> None:
        """Navigate to next image."""
        if not self._image_paths:
            return

        if not self._guard_unlabeled():
            return

        if not self._save_annotations():
            return
        self._current_index = (self._current_index + 1) % len(self._image_paths)
        self._selection_panel.set_navigation_value(self._current_index + 1)
        self._load_image_async(self._image_paths[self._current_index])

    def _on_delete_requested(self) -> None:
        """Handle delete selection request."""
        self._canvas.delete_selection()
        self._save_annotations()

    def _guard_unlabeled(self) -> bool:
        """Check for unlabeled shapes and warn user."""
        if self._canvas.has_unlabeled_shapes():
            self._canvas.start_unlabeled_blink()
            QMessageBox.warning(
                self,
                "Unlabeled boxes",
                "Some boxes are still 'No labeled'.\n"
                "Please assign a label before switching images.",
            )
            return False
        return True

    # ==================== Async Image Loading ====================

    def _cancel_pending_load(self) -> None:
        """Cancel any pending image load operation by disconnecting signals."""
        if self._loader_worker is not None:
            # Disconnect signals to prevent callbacks from old requests
            try:
                self._loader_worker.finished.disconnect(self._on_image_loaded)
            except (RuntimeError, TypeError):
                pass  # Already disconnected or never connected
            
            try:
                self._loader_worker.error.disconnect(self._on_image_error)
            except (RuntimeError, TypeError):
                pass  # Already disconnected or never connected

    def _load_image_async(self, path: Path) -> None:
        """Load image asynchronously."""
        # ============ FIX: Cancel previous load to prevent race condition ============
        self._cancel_pending_load()
        # Retain ownership until the previous worker exits. Its queued completion
        # must not clear the references belonging to the next request.
        self._cleanup_loader_thread()
        # =============================================================================
        
        self._current_image_path = path
        self.statusBar().showMessage(f"Loading: {path}", 0)

        self._loader_thread = QThread(self)
        self._loader_worker = ImageLoaderWorker(str(path))
        self._loader_worker.moveToThread(self._loader_thread)

        self._loader_thread.started.connect(self._loader_worker.run)
        
        # Connect signals - race condition check happens in callbacks
        self._loader_worker.finished.connect(self._on_image_loaded)
        self._loader_worker.error.connect(self._on_image_error)

        self._loader_worker.finished.connect(self._loader_thread.quit)
        self._loader_worker.error.connect(self._loader_thread.quit)
        self._loader_thread.finished.connect(self._on_loader_finished)
        self._loader_thread.finished.connect(self._loader_worker.deleteLater)
        self._loader_thread.finished.connect(self._loader_thread.deleteLater)

        self._loader_thread.start()

    def _on_image_loaded(self, image: QImage, path: str) -> None:
        """Handle successful image load."""
        # ============ FIX: Check if this path is still the current one ============
        # This handles race condition when user navigates quickly
        if self._current_image_path is None or str(self._current_image_path) != path:
            # This is an old request for a different image - ignore it
            return
        # =========================================================================

        # Store QImage for AI detection
        self._current_qimage = image

        self._canvas.set_image(image)
        self._canvas.setFocus()
        self.statusBar().showMessage(f"Loaded: {path}", 3000)

        # ============ FIX: Mark canvas as showing THIS image BEFORE loading annotations ============
        self._canvas_image_path = self._current_image_path
        # =========================================================================================
        
        # Update window title with current image info
        self._update_window_title()
        
        self._load_annotations(self._current_image_path)
        self._refresh_current_label_box()
    
    def _update_window_title(self) -> None:
        """Update window title with current image name and index."""
        base_title = "LZR Labelr"
        
        if self._canvas_image_path is None:
            self.setWindowTitle(base_title)
            return
        
        filename = self._canvas_image_path.name
        
        if self._image_paths:
            # Show index: "image.png (3/25)"
            index = self._current_index + 1
            total = len(self._image_paths)
            self.setWindowTitle(f"{base_title} - {filename} ({index}/{total})")
        else:
            # Single file: just show name
            self.setWindowTitle(f"{base_title} - {filename}")

    def _on_image_error(self, path: str, message: str) -> None:
        """Handle image load error."""
        # ============ FIX: Check if this path is still the current one ============
        if self._current_image_path is None or str(self._current_image_path) != path:
            # This is an old request for a different image - ignore it
            return
        # =========================================================================

        QMessageBox.warning(self, "Image load error", f"{path}\n\n{message}")
        self.statusBar().showMessage("Error loading image", 3000)

    def _on_loader_finished(self) -> None:
        """Cleanup after loader thread finishes."""
        if self.sender() is not self._loader_thread:
            return
        self._loader_thread = None
        self._loader_worker = None

    # ==================== Defect/Label Handling ====================

    def _on_defect_selected(self, name: str) -> None:
        """Handle defect type selection from panel."""
        color = self._label_manager.get_color(name)

        self._canvas.set_current_label(name, color)
        self._canvas.apply_label_to_selection(name, color)
        self._save_annotations()

    def _on_defect_added(self, name: str, color: str) -> None:
        """Handle new defect type added."""
        self.statusBar().showMessage(f"Added defect type: {name}", 3000)

    def _on_shapes_changed(self) -> None:
        """Handle shapes changed on canvas."""
        self._save_annotations()
        self._refresh_current_label_box()

    def _refresh_current_label_box(self) -> None:
        """Refresh the current label box with shape counts."""
        counts: dict[str, tuple[str, int]] = {}

        for shape in self._canvas.all_shapes():
            name = getattr(shape, "label", "") or self._canvas.DEFAULT_LABEL
            color = getattr(shape, "color", self._canvas.DEFAULT_COLOR)

            if name not in counts:
                counts[name] = (color, 0)

            current_color, current_count = counts[name]
            counts[name] = (current_color, current_count + 1)

        self._current_label_box.set_counts(counts)

    def _on_label_row_clicked(self, label_name: str) -> None:
        """Handle click on label row in current label box."""
        self._canvas.blink_by_label(label_name, cycles=8, interval_ms=140)

    # ==================== Window Events ====================

    def closeEvent(self, event: QCloseEvent) -> None:
        """Handle window close event."""
        if self._ai_busy:
            QMessageBox.information(self, "AI is running", "Wait for the current AI operation before closing.")
            event.ignore()
            return
        if self._canvas.has_unlabeled_shapes():
            self._canvas.start_unlabeled_blink()
            QMessageBox.warning(
                self,
                "Unlabeled boxes",
                "Some boxes are still 'No labeled'.\n"
                "Please assign a label before closing the application.",
            )
            event.ignore()
            return

        if not self._save_annotations():
            event.ignore()
            return
        self._cleanup_loader_thread()
        
        # Cleanup AI
        self._ai_thread.quit()
        self._ai_thread.wait()

        super().closeEvent(event)

    def _cleanup_loader_thread(self) -> None:
        """Clean up loader thread on close."""
        try:
            if self._loader_thread is not None and self._loader_thread.isRunning():
                self._loader_thread.quit()
                self._loader_thread.wait()
        except RuntimeError:
            pass

    # ==================== Info Dialog ====================

    def _on_info_requested(self) -> None:
        """Handle info button click."""
        show_info_dialog(self)

     #==================== Theme Handling ====================
    def _on_theme_mode_changed(self, mode: str) -> None:
        """Handle theme change from settings panel."""
        app = QApplication.instance()
        apply_theme(app, mode, assets_dir=Path(resource_path("")))

        self._setting_box.set_theme_mode(mode)
        self._selection_panel._apply_styles(mode)
        self._shape_box._apply_styles(mode)
        self._monitor_box._apply_styles(mode)
        self._current_label_box._apply_styles(mode)
        self._defect_panel._apply_styles(mode)
        
        
        #     self._canvas._apply_styles(mode)
