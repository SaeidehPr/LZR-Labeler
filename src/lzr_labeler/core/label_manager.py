from __future__ import annotations

import json
from pathlib import Path
import os
from PySide6.QtCore import QStandardPaths
from typing import Optional

from lzr_labeler.core.defects import DefectType, DEFAULT_DEFECTS
from lzr_labeler.core.label_normalizer import normalize_label_key, clean_label_text
from lzr_labeler.core.palette import CATEGORICAL_20


class LabelManager:
    def __init__(self, config_dir: Optional[str | Path] = None, preset: str = "general"):
        if preset not in ("general", "pcb"):
            raise ValueError(f"Unknown label preset: {preset}")
        # Determine config directory
        if config_dir is None:
            # Default: config folder next to the main script
            self._config_dir = Path(os.environ.get("LZR_LABELER_CONFIG_DIR") or
                (Path(QStandardPaths.writableLocation(QStandardPaths.GenericConfigLocation)) / "lzr-labeler"))
        else:
            self._config_dir = Path(config_dir)

        self._json_path = self._config_dir / "custom_labels.json"

        # Defect storage
        self._default_defects: list[DefectType] = list(DEFAULT_DEFECTS) if preset == "pcb" else []
        self._custom_defects: list[DefectType] = []

        # Fast canonical lookup
        self._lookup: dict[str, DefectType] = {}

        # Color palette for new defects
        self._palette = list(CATEGORICAL_20)
        self._palette_index = 0

        # Load custom defects from file
        self._load_custom_defects()
        self._rebuild_lookup()

    # ==================== Properties ====================

    @property
    def all_defects(self) -> list[DefectType]:
        """Get all defects (default + custom)."""
        return self._default_defects + self._custom_defects

    @property
    def default_defects(self) -> list[DefectType]:
        """Get only default defects."""
        return list(self._default_defects)

    @property
    def custom_defects(self) -> list[DefectType]:
        """Get only custom defects."""
        return list(self._custom_defects)

    # ==================== Public Methods ====================

    def _rebuild_lookup(self) -> None:
        """Rebuild normalized-name lookup table."""
        self._lookup.clear()
        for defect in self.all_defects:
            key = normalize_label_key(defect.name)
            if key:
                self._lookup[key] = defect

    def get_defect(self, name: str) -> Optional[DefectType]:
        """Get defect by normalized name."""
        return self._lookup.get(normalize_label_key(name))

    def get_color(self, name: str) -> str:
        """Get color for defect name. Returns default color if not found."""
        defect = self.get_defect(name)
        return defect.color if defect else "#FFEE00"

    def exists(self, name: str) -> bool:
        """Check if defect with given normalized name exists."""
        return normalize_label_key(name) in self._lookup

    def canonicalize(self, name: str) -> str:
        """Return official/canonical defect name if known, otherwise cleaned text."""
        defect = self.get_defect(name)
        if defect is not None:
            return defect.name
        return clean_label_text(name)

    def is_default(self, name: str) -> bool:
        """Check if defect is a default (non-removable) defect."""
        normalized = normalize_label_key(name)
        return any(normalize_label_key(d.name) == normalized for d in self._default_defects)

    def is_custom(self, name: str) -> bool:
        """Check if defect is a custom (user-added) defect."""
        normalized = normalize_label_key(name)
        return any(normalize_label_key(d.name) == normalized for d in self._custom_defects)

    def add_defect(self, name: str, color: Optional[str] = None) -> DefectType:
        """
        Add a new custom defect.

        Args:
            name: Defect name (must be unique after normalization)
            color: Hex color string. If None, auto-assigns from palette.

        Returns:
            The created DefectType

        Raises:
            ValueError: If defect with same normalized name already exists
        """
        canonical_name = clean_label_text(name)

        if not canonical_name:
            raise ValueError("Defect name cannot be empty")

        if self.exists(canonical_name):
            raise ValueError(f"Defect '{canonical_name}' already exists")

        if color is None:
            color = self._get_next_color()

        new_defect = DefectType(name=canonical_name, color=color)
        self._custom_defects.append(new_defect)
        self._rebuild_lookup()
        self._save_custom_defects()

        return new_defect

    def add_defect_if_not_exists(self, name: str, color: Optional[str] = None) -> DefectType:
        """
        Add defect if it doesn't exist, otherwise return existing.

        Args:
            name: Defect name
            color: Hex color string (used only if creating new)

        Returns:
            The DefectType (existing or newly created)
        """
        existing = self.get_defect(name)
        if existing:
            return existing
        return self.add_defect(name, color)

    def remove_defect(self, name: str) -> bool:
        """
        Remove a custom defect.

        Args:
            name: Defect name to remove

        Returns:
            True if removed, False if not found or is default defect
        """
        if self.is_default(name):
            return False

        normalized = normalize_label_key(name)

        for i, defect in enumerate(self._custom_defects):
            if normalize_label_key(defect.name) == normalized:
                self._custom_defects.pop(i)
                self._rebuild_lookup()
                self._save_custom_defects()
                return True

        return False

    def update_defect_color(self, name: str, new_color: str) -> bool:
        """
        Update color of a custom defect.

        Args:
            name: Defect name
            new_color: New hex color string

        Returns:
            True if updated, False if not found or is default defect
        """
        if self.is_default(name):
            return False

        normalized = normalize_label_key(name)

        for i, defect in enumerate(self._custom_defects):
            if normalize_label_key(defect.name) == normalized:
                self._custom_defects[i] = DefectType(name=defect.name, color=new_color)
                self._rebuild_lookup()
                self._save_custom_defects()
                return True

        return False

    def reload(self) -> None:
        """Reload custom defects from file."""
        self._load_custom_defects()
        self._rebuild_lookup()

    # ==================== Private Methods ====================

    def _get_next_color(self) -> str:
        """Get next available color from palette."""
        used_colors = {d.color for d in self.all_defects}

        for _ in range(len(self._palette)):
            color = self._palette[self._palette_index % len(self._palette)]
            self._palette_index += 1
            if color not in used_colors:
                return color

        # Fallback if all colors used
        return self._palette[0]

    def _load_custom_defects(self) -> None:
        """Load custom defects from JSON file."""
        self._custom_defects = []

        if not self._json_path.exists():
            return

        try:
            with open(self._json_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            labels = data.get("labels", [])
            for item in labels:
                name = clean_label_text(item.get("name", ""))
                color = item.get("color", "#FFEE00")

                if name and not self.is_default(name):
                    self._custom_defects.append(DefectType(name=name, color=color))

        except (json.JSONDecodeError, IOError) as e:
            print(f"Warning: Could not load custom labels from {self._json_path}: {e}")

    def _save_custom_defects(self) -> None:
        """Save custom defects to JSON file."""
        self._config_dir.mkdir(parents=True, exist_ok=True)

        data = {
            "labels": [
                {"name": d.name, "color": d.color}
                for d in self._custom_defects
            ]
        }

        try:
            with open(self._json_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except IOError as e:
            print(f"Warning: Could not save custom labels to {self._json_path}: {e}")

    # ==================== Dunder Methods ====================

    def __len__(self) -> int:
        return len(self.all_defects)

    def __iter__(self):
        return iter(self.all_defects)

    def __contains__(self, name: str) -> bool:
        return self.exists(name)