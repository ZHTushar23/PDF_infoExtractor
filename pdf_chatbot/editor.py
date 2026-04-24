"""
Interactive CLI editor for extracted PDF data (JSON / YAML).

Supports dot-notation for nested keys:
  metadata.title          → string field
  content.0.text          → first page text
  content.2.tables.0.0.1  → row 0, col 1 of table 0 on page 3

Commands
--------
  view              Show all data (syntax-highlighted)
  view <key>        Show value at <key>
  set  <key> <val>  Set a value  (val is JSON or plain string)
  del  <key>        Delete a key / list index
  add  <key> <val>  Add a new key (same as set for non-existing paths)
  list              List all leaf key paths
  search <term>     Find keys or values containing <term>
  undo              Undo last change
  history           Show change history
  save              Save to current file
  save <path>       Save to a new file
  export yaml       Re-save as YAML
  export json       Re-save as JSON
  help              Show this help
  quit / exit       Exit (prompts if there are unsaved changes)
"""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

# Optional rich display
try:
    from rich.console import Console
    from rich.syntax import Syntax
    _con = Console()
    HAS_RICH = True
except ImportError:
    HAS_RICH = False
    _con = None  # type: ignore[assignment]


# ─── dot-notation key helpers ─────────────────────────────────────────────────

def _split_key(key_path: str) -> list[str | int]:
    """'content.0.text' → ['content', 0, 'text']"""
    parts: list[str | int] = []
    for part in key_path.split("."):
        try:
            parts.append(int(part))
        except ValueError:
            parts.append(part)
    return parts


def get_nested(data: Any, key_path: str) -> Any:
    node = data
    for k in _split_key(key_path):
        if isinstance(node, dict):
            if k not in node:
                raise KeyError(f"Key '{k}' not found")
            node = node[k]
        elif isinstance(node, list):
            node = node[int(k)]
        else:
            raise KeyError(f"Cannot index into {type(node).__name__}")
    return node


def set_nested(data: Any, key_path: str, value: Any) -> None:
    keys = _split_key(key_path)
    node = data
    for k in keys[:-1]:
        if isinstance(node, dict):
            node = node.setdefault(k, {})
        else:
            node = node[int(k)]
    last = keys[-1]
    if isinstance(node, list):
        node[int(last)] = value
    else:
        node[last] = value


def del_nested(data: Any, key_path: str) -> None:
    keys = _split_key(key_path)
    node = data
    for k in keys[:-1]:
        if isinstance(node, dict):
            node = node[k]
        else:
            node = node[int(k)]
    last = keys[-1]
    if isinstance(node, list):
        del node[int(last)]
    else:
        del node[last]


def _all_leaf_keys(data: Any, prefix: str = "") -> list[str]:
    """Return every leaf key path using dot notation."""
    result: list[str] = []
    if isinstance(data, dict):
        for k, v in data.items():
            full = f"{prefix}.{k}" if prefix else str(k)
            if isinstance(v, (dict, list)):
                result.extend(_all_leaf_keys(v, full))
            else:
                result.append(full)
    elif isinstance(data, list):
        for i, v in enumerate(data):
            full = f"{prefix}.{i}" if prefix else str(i)
            if isinstance(v, (dict, list)):
                result.extend(_all_leaf_keys(v, full))
            else:
                result.append(full)
    return result


# ─── Display helpers ──────────────────────────────────────────────────────────

def _print_plain(data: Any, indent: int = 0) -> None:
    pad = "  " * indent
    if isinstance(data, dict):
        for k, v in data.items():
            if isinstance(v, (dict, list)):
                print(f"{pad}{k}:")
                _print_plain(v, indent + 1)
            else:
                display = str(v)
                if len(display) > 100:
                    display = display[:100] + "…"
                print(f"{pad}{k}: {display}")
    elif isinstance(data, list):
        for i, v in enumerate(data):
            if isinstance(v, (dict, list)):
                print(f"{pad}[{i}]:")
                _print_plain(v, indent + 1)
            else:
                print(f"{pad}[{i}]: {v}")
    else:
        print(f"{pad}{data}")


def _display(data: Any) -> None:
    if HAS_RICH:
        text = json.dumps(data, indent=2, ensure_ascii=False, default=str)
        _con.print(Syntax(text, "json", theme="monokai"))
    else:
        _print_plain(data)


def _parse_value(raw: str) -> Any:
    """Try JSON parse first; fall back to treating as a plain string."""
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return raw


# ─── REPL ────────────────────────────────────────────────────────────────────

_HELP = """
Commands:
  view                Show all data
  view <key>          Show value at <key>  (dot notation)
  set  <key> <val>    Update a value       (val = JSON or plain text)
  del  <key>          Delete a key / index
  add  <key> <val>    Add / overwrite a key
  list                List all leaf key paths
  search <term>       Search keys and values
  undo                Undo last change
  history             Show change history
  save                Save to current file
  save <path>         Save to a different file
  export yaml         Save a copy as YAML
  export json         Save a copy as JSON
  help                Show this help
  quit / exit         Exit (prompts if unsaved)
"""


def start_editor(filepath: str) -> None:
    from pdf_chatbot.storage import load_file, save_file, _fmt_from_ext

    path = Path(filepath)
    try:
        data = load_file(path)
    except FileNotFoundError as exc:
        print(f"Error: {exc}")
        return

    # Resolve to the actual path (load_file may have resolved an extension)
    for candidate in [path, path.with_suffix(".json"), path.with_suffix(".yaml")]:
        if candidate.exists():
            path = candidate
            break

    original_data = copy.deepcopy(data)
    history: list[tuple[str, Any]] = []   # (key_path, old_value_or_SENTINEL)
    _NEW = object()                         # sentinel for "key did not exist"
    unsaved = False

    fmt = _fmt_from_ext(path).upper()
    print(f"\n{'─'*56}")
    print(f"  Editing : {path.name}")
    print(f"  Format  : {fmt}")
    print(f"  Keys    : {len(_all_leaf_keys(data))}")
    print(f"{'─'*56}")
    print("  Type 'help' for commands.\n")

    while True:
        try:
            raw = input("edit> ").strip()
        except (EOFError, KeyboardInterrupt):
            raw = "quit"

        if not raw:
            continue

        # Split into at most 3 parts so values can contain spaces
        parts = raw.split(maxsplit=2)
        cmd   = parts[0].lower()

        # ── quit ──────────────────────────────────────────────────────────────
        if cmd in ("quit", "exit", "q", ":q"):
            if unsaved:
                ans = input("  Unsaved changes. Save before exit? [y/N]: ").strip().lower()
                if ans == "y":
                    save_file(data, path)
                    print(f"  Saved → {path}")
            print("  Bye.")
            break

        # ── help ──────────────────────────────────────────────────────────────
        elif cmd == "help":
            print(_HELP)

        # ── view ──────────────────────────────────────────────────────────────
        elif cmd == "view":
            if len(parts) == 1:
                _display(data)
            else:
                try:
                    _display(get_nested(data, parts[1]))
                except (KeyError, IndexError, ValueError) as e:
                    print(f"  Error: {e}")

        # ── list ──────────────────────────────────────────────────────────────
        elif cmd == "list":
            for k in _all_leaf_keys(data):
                print(f"  {k}")

        # ── search ────────────────────────────────────────────────────────────
        elif cmd == "search":
            if len(parts) < 2:
                print("  Usage: search <term>")
                continue
            term  = parts[1].lower()
            found = False
            for k in _all_leaf_keys(data):
                try:
                    v = get_nested(data, k)
                    if term in k.lower() or term in str(v).lower():
                        val_str = str(v)[:80] + ("…" if len(str(v)) > 80 else "")
                        print(f"  {k}: {val_str}")
                        found = True
                except Exception:
                    pass
            if not found:
                print(f"  No matches for '{parts[1]}'")

        # ── set / add ─────────────────────────────────────────────────────────
        elif cmd in ("set", "add"):
            if len(parts) < 3:
                print(f"  Usage: {cmd} <key> <value>")
                continue
            key, val_raw = parts[1], parts[2]
            value = _parse_value(val_raw)
            try:
                try:
                    old = copy.deepcopy(get_nested(data, key))
                except (KeyError, IndexError):
                    old = _NEW
                set_nested(data, key, value)
                history.append((key, old))
                unsaved = True
                print(f"  ✓ {key} = {repr(value)}")
            except Exception as e:
                print(f"  Error: {e}")

        # ── del ───────────────────────────────────────────────────────────────
        elif cmd == "del":
            if len(parts) < 2:
                print("  Usage: del <key>")
                continue
            key = parts[1]
            try:
                old = copy.deepcopy(get_nested(data, key))
                del_nested(data, key)
                history.append((key, old))
                unsaved = True
                print(f"  ✓ Deleted: {key}")
            except Exception as e:
                print(f"  Error: {e}")

        # ── undo ──────────────────────────────────────────────────────────────
        elif cmd == "undo":
            if not history:
                print("  Nothing to undo.")
            else:
                key, old = history.pop()
                if old is _NEW:
                    try:
                        del_nested(data, key)
                    except Exception:
                        pass
                    print(f"  Undone: removed '{key}'")
                else:
                    set_nested(data, key, old)
                    print(f"  Undone: restored '{key}'")
                unsaved = True

        # ── history ───────────────────────────────────────────────────────────
        elif cmd == "history":
            if not history:
                print("  No changes yet.")
            else:
                for i, (k, v) in enumerate(history, 1):
                    v_str = "new key" if v is _NEW else repr(v)[:60]
                    print(f"  {i:2}. {k}  ←  {v_str}")

        # ── save ──────────────────────────────────────────────────────────────
        elif cmd == "save":
            target = Path(parts[1]) if len(parts) > 1 else path
            save_file(data, target)
            path    = target
            unsaved = False
            print(f"  ✓ Saved → {target}")

        # ── export ────────────────────────────────────────────────────────────
        elif cmd == "export":
            if len(parts) < 2 or parts[1].lower() not in ("json", "yaml", "yml"):
                print("  Usage: export json|yaml")
                continue
            fmt_out = "yaml" if parts[1].lower() in ("yaml", "yml") else "json"
            ext_out = ".yaml" if fmt_out == "yaml" else ".json"
            target  = path.with_suffix(ext_out)
            save_file(data, target, fmt=fmt_out)
            print(f"  ✓ Exported → {target}")

        else:
            print(f"  Unknown command '{cmd}'. Type 'help'.")
