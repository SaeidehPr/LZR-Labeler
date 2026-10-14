import sys
from pathlib import Path

def base_dir() -> Path:
    if getattr(sys, "frozen", False):
        exe_dir = Path(sys.executable).resolve().parent
        internal = exe_dir / "_internal"
        if internal.exists():
            return internal
        return exe_dir
    return Path(__file__).resolve().parents[1]

def resource_path(rel: str) -> str:
    return str(base_dir() / rel)

