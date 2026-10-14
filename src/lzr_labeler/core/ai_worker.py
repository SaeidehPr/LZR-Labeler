from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from enum import Enum, auto
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, TYPE_CHECKING

import numpy as np
from PySide6.QtCore import QObject, Signal, Slot

from lzr_labeler.core.label_normalizer import clean_label_text, normalize_label_key

if TYPE_CHECKING:
    import torch
    from lzr_labeler.core.label_manager import LabelManager


# ==================== Constants ====================

TILE_SIZE = 1000
DEFAULT_CONFIDENCE = 0.90


# ==================== Logging ====================

logger = logging.getLogger("ai.worker")
logger.addHandler(logging.NullHandler())


# ==================== Lazy Torch Import ====================

_torch = None
_torchvision = None


def _ensure_torch() -> None:
    """Lazy import torch/torchvision for faster startup."""
    global _torch, _torchvision
    if _torch is None:
        import torch
        import torchvision
        _torch = torch
        _torchvision = torchvision


def _get_torch():
    _ensure_torch()
    return _torch


# ==================== Data Classes ====================

@dataclass
class Detection:
    """Single detection result (MaskRCNN may include mask)."""
    label: str
    confidence: float
    bbox: Tuple[float, float, float, float]  # (x1, y1, x2, y2)
    mask: Optional[np.ndarray] = None        # (H, W) float/uint8 mask if available


class ModelType(Enum):
    """Supported torchvision detection architectures."""
    FASTER_RCNN = auto()
    MASK_RCNN = auto()
    RETINANET = auto()
    FCOS = auto()
    SSD = auto()
    UNKNOWN = auto()


@dataclass
class ModelInfo:
    """Resolved model properties from meta file."""
    model_type: ModelType
    has_mask: bool
    num_classes: int                  # torchvision-style num_classes
    arch_hint: str                    # exact builder name from meta


@dataclass
class MetaInfo:
    """Metadata loaded from meta_info.json."""
    arch: str
    num_classes: int
    label_map: Dict[str, Any]
    trained_on_img_size: Optional[Tuple[int, int]] = None
    raw: Optional[Dict[str, Any]] = None


# ==================== Label Mapper ====================

class LabelMapper:
    """
    Maps model output class IDs to human-readable labels.

    Supports flexible label_map formats:
      - { "ClassName": 1, ... }   →  name→id
      - { "1": "ClassName", ... } →  id→name

    Label resolution pipeline (in order):
      1. Raw name from label_map  (e.g. "Kratzer_Funktional")
      2. normalize_label_key()    →  strips underscore/spaces/case differences
      3. LabelManager.canonicalize() → returns the official display name

    This means the model can use any casing or underscore style and the app
    will always display the canonical label name (e.g. "Kratzer funktional").

    IMPORTANT:
    - In torchvision detectors, num_classes includes background class 0.
    - Therefore if your foreground labels are 1..7, num_classes should be 8.
    """

    def __init__(self, label_manager: "Optional[LabelManager]" = None) -> None:
        self._id_to_name: Dict[int, str] = {}
        self._loaded = False
        # Optional LabelManager for canonical name + color resolution.
        # If None, falls back to clean_label_text() only.
        self._label_manager = label_manager

    @property
    def is_loaded(self) -> bool:
        return self._loaded

    @property
    def num_classes(self) -> int:
        """Return torchvision-style num_classes including background class 0."""
        if not self._id_to_name:
            return 0
        return max(self._id_to_name.keys(), default=0) + 1

    def load_from_dict(self, data: Dict[str, Any]) -> bool:
        """Load label map from a dictionary."""
        try:
            self._id_to_name = {}

            for key, value in data.items():
                if isinstance(value, int):
                    # {name: id}
                    self._id_to_name[value] = str(key)
                else:
                    # {id: name}
                    try:
                        self._id_to_name[int(key)] = str(value)
                    except (ValueError, TypeError):
                        continue

            self._loaded = bool(self._id_to_name)
            return self._loaded
        except Exception:
            logger.exception("Failed to load label map from dict")
            self._loaded = False
            return False

    def get_label(self, class_id: int) -> str:
        """
        Resolve a model class ID to a canonical display label.

        Uses normalize_label_key() to tolerate underscore/space/case
        differences between the model's label_map and the app's LabelManager.
        Falls back to clean_label_text() if no LabelManager is set.
        """
        raw = self._id_to_name.get(class_id, f"Class_{class_id}")

        if self._label_manager is not None:
            # canonicalize() uses normalize_label_key() internally:
            # strips underscores → spaces, lowercases, NFKC-normalizes,
            # then looks up the official DefectType name.
            return self._label_manager.canonicalize(raw)

        # No LabelManager: at least clean up underscores and whitespace.
        return clean_label_text(raw)


# ==================== Meta Loader ====================

class MetaLoader:
    """
    Load model metadata from sidecar JSON.

    Expected keys:
      - arch or Model
      - num_classes
      - label_map
      - optional trained_on_img_size
    """

    @staticmethod
    def load(path: Path) -> MetaInfo:
        if not path.exists():
            raise FileNotFoundError(f"Meta file not found: {path}")

        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError("Meta file must contain a JSON object")

        arch = data.get("arch") or data.get("Model") or ""
        arch = str(arch).strip()

        # Common typo guard
        if arch == "fastrcnn_resnet50_fpn":
            arch = "fasterrcnn_resnet50_fpn"

        if not arch:
            raise ValueError("Meta file is missing 'arch' or 'Model'")

        num_classes = data.get("num_classes")
        if not isinstance(num_classes, int) or num_classes < 2:
            raise ValueError("Meta file has invalid 'num_classes'")

        label_map = data.get("label_map")
        if not isinstance(label_map, dict) or not label_map:
            raise ValueError("Meta file is missing a valid 'label_map'")

        img_size = data.get("trained_on_img_size")
        parsed_img_size: Optional[Tuple[int, int]] = None
        if isinstance(img_size, list) and len(img_size) == 2:
            try:
                parsed_img_size = (int(img_size[0]), int(img_size[1]))
            except Exception:
                parsed_img_size = None

        return MetaInfo(
            arch=arch,
            num_classes=num_classes,
            label_map=label_map,
            trained_on_img_size=parsed_img_size,
            raw=data,
        )


# ==================== Checkpoint Loader ====================

class CheckpointLoader:
    """
    Loads checkpoint (.pth) and extracts the BEST possible state_dict.

    Supports:
    - DataParallel prefix "module."
    - Lightning prefix "model."
    - checkpoints containing nested state_dicts
    """

    @classmethod
    def load(cls, path: Path) -> Dict[str, Any]:
        _ensure_torch()
        torch = _get_torch()

        ckpt = torch.load(path, map_location="cpu")
        state = cls._extract_best_state_dict(ckpt)
        state = cls._strip_prefixes(state)
        return state

    @staticmethod
    def _strip_prefixes(sd: Dict[str, Any]) -> Dict[str, Any]:
        """Remove common prefixes introduced by wrappers."""
        prefixes = ("module.", "model.")
        for pref in prefixes:
            if any(k.startswith(pref) for k in sd.keys()):
                sd = {(k[len(pref):] if k.startswith(pref) else k): v for k, v in sd.items()}
        return sd

    @classmethod
    def _extract_best_state_dict(cls, ckpt: Any) -> Dict[str, Any]:
        """Extract the most plausible full detector state_dict from checkpoint."""
        if not isinstance(ckpt, dict):
            if hasattr(ckpt, "state_dict"):
                return ckpt.state_dict()
            raise ValueError("Checkpoint is not a dict and has no state_dict()")

        candidates: List[Tuple[str, Dict[str, Any]]] = []

        for k in ("state_dict", "model_state_dict", "model", "net", "weights"):
            v = ckpt.get(k)
            if isinstance(v, dict) and cls._looks_like_state_dict(v):
                candidates.append((k, v))

        for k, v in ckpt.items():
            if isinstance(v, dict) and cls._looks_like_state_dict(v):
                candidates.append((k, v))

        if cls._looks_like_state_dict(ckpt):
            candidates.append(("__root__", ckpt))

        if not candidates:
            raise ValueError("Could not find a valid state_dict inside the checkpoint")

        best_key, best_sd = max(candidates, key=lambda kv: cls._score_state_dict(kv[1]))
        logger.info("Selected state_dict candidate: %s (keys=%d)", best_key, len(best_sd))
        return best_sd

    @staticmethod
    def _looks_like_state_dict(d: Dict[str, Any]) -> bool:
        """Heuristic: keys are string parameter names, values look like tensors."""
        if not d:
            return False

        keys = list(d.keys())
        if not all(isinstance(k, str) for k in keys[:50]):
            return False

        if not any("." in k for k in keys[:200]):
            return False

        vals = list(d.values())[:10]
        if not vals:
            return False
        if not all(hasattr(v, "shape") for v in vals):
            return False

        return True

    @staticmethod
    def _score_state_dict(sd: Dict[str, Any]) -> int:
        """
        Score candidate state_dicts:
        - More keys is generally better.
        - Presence of critical detector parts is heavily rewarded.
        """
        keys = list(sd.keys())
        s = len(keys)

        def has_prefix(p: str) -> bool:
            return any(k.startswith(p) for k in keys)

        if has_prefix("backbone."):
            s += 1000
        if has_prefix("rpn."):
            s += 5000
        if has_prefix("roi_heads.box_head."):
            s += 5000
        if has_prefix("roi_heads.box_predictor."):
            s += 5000
        if has_prefix("roi_heads.mask_head."):
            s += 3000
        if has_prefix("roi_heads.mask_predictor."):
            s += 3000
        if has_prefix("head."):
            s += 2000
        if "anchor_generator" in " ".join(keys):
            s += 1500

        return s


# ==================== Model Resolver ====================

class ModelResolver:
    """Resolve architecture info from meta."""

    @staticmethod
    def model_type_from_arch(arch: str) -> ModelType:
        a = arch.strip().lower()

        if a.startswith("maskrcnn_"):
            return ModelType.MASK_RCNN
        if a.startswith("fasterrcnn_"):
            return ModelType.FASTER_RCNN
        if a.startswith("retinanet_"):
            return ModelType.RETINANET
        if a.startswith("fcos_"):
            return ModelType.FCOS
        if a.startswith("ssd"):
            return ModelType.SSD

        return ModelType.UNKNOWN

    @staticmethod
    def resolve(meta: MetaInfo) -> ModelInfo:
        mtype = ModelResolver.model_type_from_arch(meta.arch)
        if mtype == ModelType.UNKNOWN:
            raise ValueError(f"Unsupported model architecture in meta: {meta.arch}")

        return ModelInfo(
            model_type=mtype,
            has_mask=(mtype == ModelType.MASK_RCNN),
            num_classes=meta.num_classes,
            arch_hint=meta.arch,
        )

    @staticmethod
    def validate_label_map(meta: MetaInfo) -> Optional[str]:
        """
        Validate that label_map is compatible with num_classes.

        For torchvision detectors:
          num_classes = max_foreground_class_id + 1  (background = 0)

        Gaps in foreground class IDs are allowed and produce a warning only —
        predictions for missing IDs will show as "Class_N" but the model loads.
        """
        ids: List[int] = []
        for key, value in meta.label_map.items():
            if isinstance(value, int):
                ids.append(value)
            else:
                try:
                    ids.append(int(key))
                except (ValueError, TypeError):
                    continue

        if not ids:
            return "Meta label_map does not contain any valid class ids."

        max_id = max(ids)
        expected_num_classes = max_id + 1

        if meta.num_classes != expected_num_classes:
            return (
                "Meta class count mismatch:\n"
                f"- meta num_classes = {meta.num_classes}\n"
                f"- label_map implies num_classes = {expected_num_classes}\n"
                "For torchvision detectors, num_classes should include background class 0."
            )

        # Gaps in foreground ids are common (e.g. a class was removed after training).
        # The model still loads correctly — unknown ids just show as "Class_N".
        missing = sorted(set(range(1, max_id + 1)) - set(ids))
        if missing:
            logger.warning(
                "label_map has gaps in foreground class ids (missing: %s). "
                "Detections for those ids will display as 'Class_N'.",
                missing,
            )

        return None


# ==================== Model Builder ====================

class ModelBuilder:
    """
    Build a torchvision detection model from exact builder name.
    """

    @classmethod
    def build(cls, info: ModelInfo):
        _ensure_torch()
        model = cls._build_from_arch_name(info.arch_hint, info.num_classes)
        if model is None:
            raise ValueError(f"Unsupported architecture builder: {info.arch_hint}")
        return model

    @staticmethod
    def _build_from_arch_name(arch: str, num_classes: int):
        arch = arch.strip()

        # Two-stage
        if arch == "fasterrcnn_resnet50_fpn":
            from torchvision.models.detection import fasterrcnn_resnet50_fpn
            return fasterrcnn_resnet50_fpn(weights=None, num_classes=num_classes)

        if arch == "fasterrcnn_resnet50_fpn_v2":
            from torchvision.models.detection import fasterrcnn_resnet50_fpn_v2
            return fasterrcnn_resnet50_fpn_v2(weights=None, num_classes=num_classes)

        if arch == "maskrcnn_resnet50_fpn":
            from torchvision.models.detection import maskrcnn_resnet50_fpn
            return maskrcnn_resnet50_fpn(weights=None, num_classes=num_classes)

        if arch == "maskrcnn_resnet50_fpn_v2":
            from torchvision.models.detection import maskrcnn_resnet50_fpn_v2
            return maskrcnn_resnet50_fpn_v2(weights=None, num_classes=num_classes)

        # One-stage
        if arch == "retinanet_resnet50_fpn":
            from torchvision.models.detection import retinanet_resnet50_fpn
            return retinanet_resnet50_fpn(weights=None, num_classes=num_classes)

        if arch == "retinanet_resnet50_fpn_v2":
            from torchvision.models.detection import retinanet_resnet50_fpn_v2
            return retinanet_resnet50_fpn_v2(weights=None, num_classes=num_classes)

        if arch == "fcos_resnet50_fpn":
            from torchvision.models.detection import fcos_resnet50_fpn
            return fcos_resnet50_fpn(weights=None, num_classes=num_classes)

        if arch == "ssd300_vgg16":
            from torchvision.models.detection import ssd300_vgg16
            return ssd300_vgg16(weights=None, num_classes=num_classes)

        return None


# ==================== Checkpoint Validation ====================

class CheckpointValidator:
    """Validate checkpoint completeness against resolved architecture."""

    @staticmethod
    def validate_completeness(state_dict: Dict[str, Any], info: ModelInfo) -> Optional[str]:
        keys = list(state_dict.keys())

        def has_prefix(p: str) -> bool:
            return any(k.startswith(p) for k in keys)

        if info.model_type in (ModelType.FASTER_RCNN, ModelType.MASK_RCNN):
            required = {
                "backbone": has_prefix("backbone."),
                "rpn": has_prefix("rpn."),
                "roi_heads.box_head": has_prefix("roi_heads.box_head."),
                "roi_heads.box_predictor": has_prefix("roi_heads.box_predictor."),
            }

            if info.model_type == ModelType.MASK_RCNN:
                required.update({
                    "roi_heads.mask_head": has_prefix("roi_heads.mask_head."),
                    "roi_heads.mask_predictor": has_prefix("roi_heads.mask_predictor."),
                })

            missing = [k for k, ok in required.items() if not ok]
            if missing:
                return (
                    "Checkpoint seems incomplete or does not match the declared architecture.\n"
                    f"Missing essential parts: {missing}\n"
                    "Please export and provide a FULL detector state_dict (model.state_dict())."
                )

        if info.model_type in (ModelType.RETINANET, ModelType.FCOS, ModelType.SSD):
            required = {
                "head": has_prefix("head.") or any("classification_head" in k for k in keys),
            }
            missing = [k for k, ok in required.items() if not ok]
            if missing:
                return (
                    "Checkpoint seems incomplete for a one-stage detector.\n"
                    f"Missing essential parts: {missing}\n"
                    "Please provide a FULL model.state_dict() export."
                )

        return None

    @staticmethod
    def validate_num_classes(state_dict: Dict[str, Any], info: ModelInfo) -> Optional[str]:
        """
        Validate classifier/mask head output dimensions against meta num_classes.
        """
        candidates: List[str] = []

        if info.model_type in (ModelType.FASTER_RCNN, ModelType.MASK_RCNN):
            candidates += ["roi_heads.box_predictor.cls_score.weight"]

        if info.model_type == ModelType.MASK_RCNN:
            candidates += ["roi_heads.mask_predictor.mask_fcn_logits.weight"]

        if info.model_type == ModelType.RETINANET:
            candidates += ["head.classification_head.cls_logits.weight"]

        if info.model_type == ModelType.FCOS:
            candidates += ["head.classification_head.cls_logits.weight", "head.cls_logits.weight"]

        if info.model_type == ModelType.SSD:
            candidates += [
                "head.classification_head.module_list.0.weight",
                "head.classification_head.cls_logits.weight",
            ]

        for k in candidates:
            if k in state_dict:
                w = state_dict[k]
                if hasattr(w, "shape") and len(w.shape) >= 1:
                    out_dim = int(w.shape[0])
                    if out_dim != info.num_classes:
                        return (
                            "Checkpoint/meta class count mismatch:\n"
                            f"- meta num_classes = {info.num_classes}\n"
                            f"- checkpoint head output = {out_dim}\n"
                            f"- offending tensor = {k}"
                        )

        return None


# ==================== AI Manager ====================

class AIManager(QObject):
    """
    Qt-friendly AI manager:
    - load_model() loads meta, builds exact model, loads weights.
    - detect() runs inference on numpy image (H,W,C), supports tiling for large images.

    Args:
        label_manager: Optional LabelManager instance for canonical label resolution.
                       When provided, model output labels are matched via
                       normalize_label_key() and resolved to their official display
                       names regardless of underscore/space/case differences.
                       When None, clean_label_text() is used as a simple fallback.

    Signals:
      modelLoaded(success: bool, message: str)
      detectionFinished(detections: list[Detection])
      detectionError(error: str)
      progressUpdate(message: str)
    """

    modelLoaded = Signal(bool, str)
    detectionFinished = Signal(list)
    detectionError = Signal(str)
    progressUpdate = Signal(str)

    def __init__(
        self,
        label_manager: "Optional[LabelManager]" = None,
        parent=None,
    ) -> None:
        super().__init__(parent)

        self._model = None
        self._model_info: Optional[ModelInfo] = None
        self._meta_info: Optional[MetaInfo] = None
        self._device = None

        self._label_mapper = LabelMapper(label_manager=label_manager)
        self._model_loaded = False

        self._model_path: Optional[Path] = None
        self._meta_path: Optional[Path] = None

        self._confidence_threshold: float = DEFAULT_CONFIDENCE
        self._last_error: Optional[str] = None

    # -------- properties --------

    @property
    def is_loaded(self) -> bool:
        return self._model_loaded

    @property
    def device(self) -> str:
        return "cpu" if self._device is None else str(self._device)

    @property
    def model_info(self) -> Optional[ModelInfo]:
        return self._model_info

    @property
    def meta_info(self) -> Optional[MetaInfo]:
        return self._meta_info

    @property
    def last_error(self) -> Optional[str]:
        return self._last_error

    # -------- configuration --------

    def set_model_config(
        self,
        model_path: str | Path,
        meta_path: Optional[str | Path] = None,
        confidence_threshold: float = DEFAULT_CONFIDENCE,
    ) -> None:
        self._model_path = Path(model_path)
        self._meta_path = Path(meta_path) if meta_path else None
        self._confidence_threshold = confidence_threshold

    @Slot(float)
    def set_confidence_threshold(self, threshold: float) -> None:
        self._confidence_threshold = max(0.0, min(1.0, threshold))

    # -------- internals --------

    def _emit_error(self, msg: str) -> None:
        self._last_error = msg
        self._model_loaded = False
        logger.error(msg)
        self.modelLoaded.emit(False, msg)

    # -------- model loading --------

    @Slot()
    def load_model(
        self,
        model_path: Optional[str | Path] = None,
        meta_path: Optional[str | Path] = None,
    ) -> None:
        """
        Load AI model from:
        - checkpoint (.pth)
        - metadata sidecar (.json)

        Meta is the source of truth for:
        - architecture builder name
        - num_classes
        - label_map
        """
        if model_path:
            self._model_path = Path(model_path)
        if meta_path:
            self._meta_path = Path(meta_path)

        self._last_error = None

        if self._model_path is None:
            self._emit_error("Model path not configured.")
            return
        if not self._model_path.exists():
            self._emit_error(f"Model file not found: {self._model_path}")
            return

        if self._meta_path is None:
            self._emit_error("Meta path not configured.")
            return
        if not self._meta_path.exists():
            self._emit_error(f"Meta file not found: {self._meta_path}")
            return

        try:
            _ensure_torch()
            torch = _get_torch()

            # Select device (CPU or CUDA)
            self._device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

            self.progressUpdate.emit("Loading meta info...")

            meta = MetaLoader.load(self._meta_path)
            self._meta_info = meta

            label_map_error = ModelResolver.validate_label_map(meta)
            if label_map_error:
                self._emit_error(label_map_error)
                return

            if not self._label_mapper.load_from_dict(meta.label_map):
                self._emit_error("Failed to load label_map from meta file.")
                return

            info = ModelResolver.resolve(meta)
            self._model_info = info

            self.progressUpdate.emit("Loading checkpoint...")

            state_dict = CheckpointLoader.load(self._model_path)

            incomplete = CheckpointValidator.validate_completeness(state_dict, info)
            if incomplete:
                self._emit_error(incomplete)
                return

            nc_error = CheckpointValidator.validate_num_classes(state_dict, info)
            if nc_error:
                self._emit_error(nc_error)
                return

            self.progressUpdate.emit(f"Building model: {info.arch_hint} ...")

            self._model = ModelBuilder.build(info)

            self.progressUpdate.emit("Loading weights...")

            try:
                self._model.load_state_dict(state_dict, strict=True)
            except Exception as e:
                raise RuntimeError(
                    "load_state_dict(strict=True) failed.\n"
                    "Possible reasons:\n"
                    "- Meta architecture does not match the checkpoint.\n"
                    "- Meta num_classes does not match the trained model.\n"
                    "- Checkpoint is partial or from a different codebase.\n"
                    f"Original error: {e}"
                ) from e

            self._model.to(self._device)
            self._model.eval()

            self._model_loaded = True
            msg = f"Loaded {info.arch_hint} ({info.num_classes} classes) on {self._device}"
            self.modelLoaded.emit(True, msg)

        except Exception as e:
            logger.exception("Error loading model")
            self._emit_error(str(e))

    # -------- detection --------

    @Slot(object)
    def detect(self, image: np.ndarray) -> None:
        """Run detection on image (numpy H,W,C)."""
        if not self._model_loaded:
            self._last_error = "Model not loaded"
            self.detectionError.emit(self._last_error)
            return

        self._last_error = None

        try:
            h, w = image.shape[:2]
            if w <= TILE_SIZE * 1.5 and h <= TILE_SIZE * 1.5:
                detections = self._detect_single(image)
            else:
                detections = self._detect_tiled(image)

            self.detectionFinished.emit(detections)

        except Exception as e:
            self._last_error = str(e)
            logger.exception("Detection error")
            self.detectionError.emit(self._last_error)

    def _detect_single(self, image: np.ndarray) -> List[Detection]:
        torch = _get_torch()

        tensor = self._preprocess(image).to(self._device)
        self._model.eval()
        with torch.no_grad():
            outputs = self._model([tensor])[0]
        return self._process_outputs(outputs)

    def _detect_tiled(self, image: np.ndarray) -> List[Detection]:
        """
        Detect on large images using tiled approach with batch processing.
        """
        torch = _get_torch()

        h, w = image.shape[:2]
        all_dets: List[Detection] = []

        n_tiles_x = (w + TILE_SIZE - 1) // TILE_SIZE
        n_tiles_y = (h + TILE_SIZE - 1) // TILE_SIZE
        total_tiles = n_tiles_x * n_tiles_y

        if str(self._device) == "cuda":
            batch_size = min(4, total_tiles)
        else:
            batch_size = min(2, total_tiles)

        self._model.eval()

        tiles_data: List[Tuple[np.ndarray, int, int]] = []

        for y0 in range(0, h, TILE_SIZE):
            for x0 in range(0, w, TILE_SIZE):
                x1 = min(x0 + TILE_SIZE, w)
                y1 = min(y0 + TILE_SIZE, h)
                tile = image[y0:y1, x0:x1].copy()

                th, tw = tile.shape[:2]
                if tw < TILE_SIZE or th < TILE_SIZE:
                    padded = np.zeros((TILE_SIZE, TILE_SIZE, 3), dtype=np.uint8)
                    padded[:th, :tw] = tile
                    tile = padded

                tiles_data.append((tile, x0, y0))

        for batch_start in range(0, len(tiles_data), batch_size):
            batch_end = min(batch_start + batch_size, len(tiles_data))
            batch_tiles = tiles_data[batch_start:batch_end]

            self.progressUpdate.emit(
                f"Processing tiles {batch_start + 1}-{batch_end}/{total_tiles} ..."
            )

            tensors = [self._preprocess(tile).to(self._device) for tile, _, _ in batch_tiles]

            with torch.no_grad():
                outputs_list = self._model(tensors)

            for (tile, x0, y0), outputs in zip(batch_tiles, outputs_list):
                all_dets.extend(self._process_outputs(outputs, offset_x=x0, offset_y=y0))

        self.progressUpdate.emit(f"Found {len(all_dets)} detections")
        return all_dets

    def _preprocess(self, image: np.ndarray):
        """
        Convert numpy image to torch tensor:
        - Ensure uint8
        - (H, W, C) -> (C, H, W)
        - normalize to [0, 1]
        """
        torch = _get_torch()

        if image.dtype != np.uint8:
            image = (image * 255).astype(np.uint8)

        return torch.from_numpy(image).permute(2, 0, 1).float() / 255.0

    def _process_outputs(
        self,
        outputs: Dict[str, Any],
        offset_x: float = 0.0,
        offset_y: float = 0.0,
    ) -> List[Detection]:
        """Convert model outputs dict to a list[Detection]."""
        dets: List[Detection] = []

        boxes = outputs["boxes"].detach().cpu().numpy()
        labels = outputs["labels"].detach().cpu().numpy()
        scores = outputs["scores"].detach().cpu().numpy()

        masks = None
        if self._model_info and self._model_info.has_mask and "masks" in outputs:
            masks = outputs["masks"].detach().cpu().numpy()  # (N,1,H,W)

        for i, (box, lid, score) in enumerate(zip(boxes, labels, scores)):
            if float(score) < self._confidence_threshold:
                continue

            if self._label_mapper.is_loaded:
                label_name = self._label_mapper.get_label(int(lid))
            else:
                label_name = str(int(lid))

            x1, y1, x2, y2 = box.tolist()
            x1 += offset_x
            y1 += offset_y
            x2 += offset_x
            y2 += offset_y

            mask = None
            if masks is not None and i < len(masks):
                mask = masks[i, 0]

            dets.append(
                Detection(
                    label=label_name,
                    confidence=float(score),
                    bbox=(x1, y1, x2, y2),
                    mask=mask,
                )
            )

        return dets

    # -------- cleanup --------

    @Slot()
    def cleanup(self) -> None:
        """Release model and free GPU memory."""
        if self._model is not None:
            del self._model
            self._model = None

        self._model_loaded = False
        self._model_info = None
        self._meta_info = None

        try:
            torch = _torch
            if torch is not None and torch.cuda.is_available():
                torch.cuda.empty_cache()
        except Exception:
            logger.exception("Cleanup error")

    # Backward-compat alias
    def is_model_loaded(self) -> bool:
        return self._model_loaded