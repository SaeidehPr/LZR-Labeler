from __future__ import annotations

import re
import unicodedata


def clean_label_text(label: str | None) -> str:
    """Readable cleaned text for display/save fallback."""
    if not label:
        return ""

    s = str(label).strip()
    s = unicodedata.normalize("NFKC", s)
    s = s.replace("_", " ")
    s = re.sub(r"\s+", " ", s)
    return s


def normalize_label_key(label: str | None) -> str:
    """Generic comparison key."""
    s = clean_label_text(label)
    return s.casefold()