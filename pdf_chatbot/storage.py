"""
Save and load extracted PDF data.

Supported formats
-----------------
JSON  — default, universal, human-readable
YAML  — more compact, supports comments, easier to hand-edit

Format comparison (same data):
  JSON  ~100 % size, strict syntax, no comments
  YAML  ~70-80 % size, relaxed syntax, supports # comments

The format is inferred from the file extension (.json / .yaml / .yml).
"""

from __future__ import annotations

import json
from pathlib import Path

_STORAGE_DIR = Path("pdf_data")


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _fmt_from_ext(path: Path) -> str:
    return "yaml" if path.suffix.lower() in (".yaml", ".yml") else "json"


def _load_yaml(path: Path) -> dict:
    try:
        import yaml
    except ImportError:
        raise ImportError("pyyaml not installed. Run: pip install pyyaml")
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def _save_yaml(data: dict, path: Path) -> None:
    try:
        import yaml
    except ImportError:
        raise ImportError("pyyaml not installed. Run: pip install pyyaml")
    with open(path, "w", encoding="utf-8") as f:
        yaml.dump(data, f, default_flow_style=False, allow_unicode=True, sort_keys=False)


# ─── Public API ───────────────────────────────────────────────────────────────

def save_file(data: dict, path: Path | str, fmt: str | None = None) -> Path:
    """
    Save *data* to *path*.

    Parameters
    ----------
    data : extracted PDF dict
    path : destination file (extension determines format unless *fmt* is given)
    fmt  : "json" or "yaml" — overrides the extension
    """
    path = Path(path)
    fmt  = fmt or _fmt_from_ext(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    if fmt == "yaml":
        _save_yaml(data, path)
    else:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    return path


def load_file(path: Path | str) -> dict:
    """
    Load a previously saved file.

    *path* can be:
      - a full path:  "pdf_data/report.json"
      - a bare stem:  "report"  (tries pdf_data/report.json then .yaml)
    """
    path = Path(path)

    if not path.exists():
        # Try adding extensions / prepending storage dir
        for candidate in [
            path.with_suffix(".json"),
            path.with_suffix(".yaml"),
            path.with_suffix(".yml"),
            _STORAGE_DIR / f"{path.stem}.json",
            _STORAGE_DIR / f"{path.stem}.yaml",
            _STORAGE_DIR / f"{path.stem}.yml",
        ]:
            if candidate.exists():
                path = candidate
                break
        else:
            raise FileNotFoundError(f"No stored file found for: {path}")

    fmt = _fmt_from_ext(path)
    if fmt == "yaml":
        return _load_yaml(path)
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def default_save_path(data: dict, fmt: str = "json") -> Path:
    """Return the default storage path for extracted PDF data."""
    _STORAGE_DIR.mkdir(exist_ok=True)
    stem = Path(data["metadata"]["filename"]).stem
    stem = "".join(c if (c.isalnum() or c in "-_.") else "_" for c in stem)
    ext  = ".yaml" if fmt == "yaml" else ".json"
    return _STORAGE_DIR / f"{stem}{ext}"


def list_stored_files() -> list[Path]:
    """Return all stored files, sorted alphabetically."""
    if not _STORAGE_DIR.exists():
        return []
    files: list[Path] = []
    for pattern in ("*.json", "*.yaml", "*.yml"):
        files.extend(_STORAGE_DIR.glob(pattern))
    return sorted(set(files))
