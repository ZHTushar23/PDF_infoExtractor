#!/usr/bin/env python3
"""
PDF Chatbot — free, local, no API key.

Uses Ollama (llama3.2 / mistral / phi3 …) as the LLM.
Uses pdfplumber for digital PDFs and Tesseract OCR for scanned ones.

Data formats  ──────────────────────────────────────────────────────
  JSON   default, universal, strict syntax
  YAML   more readable, ~25 % smaller, supports # comments
  ────────────────────────────────────────────────────────────────
  (lighter alternatives: SQLite for tabular data, MessagePack for binary)

Commands  ──────────────────────────────────────────────────────────
  extract <pdf>  [--ocr] [--format json|yaml] [--output <path>]
  chat    <file> [--model <ollama-model>]
  edit    <file>
  list
  models
  convert <file> --to json|yaml
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Load .env if present (harmless if not)
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


# ─── Command handlers ─────────────────────────────────────────────────────────

def cmd_extract(args: argparse.Namespace) -> None:
    from pdf_chatbot.extractor import extract_pdf
    from pdf_chatbot.storage import default_save_path, save_file

    print(f"Extracting: {args.pdf_path}")
    if args.ocr:
        print("  Mode: force OCR (all pages treated as images)")

    data = extract_pdf(args.pdf_path, force_ocr=args.ocr)
    meta = data["metadata"]

    out = Path(args.output) if args.output else default_save_path(data, args.format)
    save_file(data, out, fmt=args.format)

    print(f"\nDone.")
    print(f"  Pages   : {meta['pages']}")
    print(f"  Method  : {meta['method']}")
    print(f"  Saved   : {out}")
    print(f"\nNext steps:")
    print(f"  python main.py chat {out}")
    print(f"  python main.py edit {out}")


def cmd_chat(args: argparse.Namespace) -> None:
    from pdf_chatbot.storage import load_file
    from pdf_chatbot.chat import start_chat

    try:
        data = load_file(args.file)
    except FileNotFoundError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)

    start_chat(data, model=args.model)


def cmd_edit(args: argparse.Namespace) -> None:
    from pdf_chatbot.editor import start_editor
    start_editor(args.file)


def cmd_list(_: argparse.Namespace) -> None:
    from pdf_chatbot.storage import list_stored_files
    files = list_stored_files()
    if not files:
        print("No files stored yet.\nRun: python main.py extract <pdf>")
    else:
        print(f"Stored files ({len(files)}):")
        for f in files:
            size_kb = f.stat().st_size // 1024
            print(f"  {f.name:<40} {size_kb:>6} KB")


def cmd_models(_: argparse.Namespace) -> None:
    from pdf_chatbot.chat import check_ollama, list_models, DEFAULT_MODEL
    if not check_ollama():
        print("Ollama is not running.")
        print("  Install : https://ollama.ai")
        print(f"  Pull    : ollama pull {DEFAULT_MODEL}")
        print("  Start   : ollama serve")
        return
    models = list_models()
    if not models:
        print(f"No models installed. Try: ollama pull {DEFAULT_MODEL}")
    else:
        print(f"Available models ({len(models)}):")
        for m in models:
            print(f"  • {m}")


def cmd_convert(args: argparse.Namespace) -> None:
    from pdf_chatbot.storage import load_file, save_file
    data   = load_file(args.file)
    fmt    = args.to
    ext    = ".yaml" if fmt == "yaml" else ".json"
    target = Path(args.file).with_suffix(ext)
    save_file(data, target, fmt=fmt)
    print(f"Converted → {target}")


# ─── Parser ───────────────────────────────────────────────────────────────────

def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="main.py",
        description="PDF Chatbot — local LLM, no API key.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    sub = parser.add_subparsers(dest="command", metavar="<command>")

    # extract ─────────────────────────────────────────────────────────────────
    p = sub.add_parser("extract", help="Extract a PDF and save as JSON/YAML")
    p.add_argument("pdf_path",  metavar="PDF",  help="Path to the PDF file")
    p.add_argument("--ocr",     action="store_true",
                   help="Force OCR for every page (use for scanned PDFs)")
    p.add_argument("--format",  "-f", choices=["json", "yaml"], default="json",
                   help="Output data format (default: json)")
    p.add_argument("--output",  "-o", default=None,
                   help="Custom output file path")

    # chat ────────────────────────────────────────────────────────────────────
    p = sub.add_parser("chat", help="Chat about an extracted file (uses Ollama)")
    p.add_argument("file",    metavar="FILE",  help="Path or name of stored file")
    p.add_argument("--model", "-m", default="llama3.2:1b",
                   help="Ollama model to use (default: llama3.2:1b)")

    # edit ────────────────────────────────────────────────────────────────────
    p = sub.add_parser("edit", help="Interactively view / modify extracted data")
    p.add_argument("file", metavar="FILE", help="Path or name of stored file")

    # list ────────────────────────────────────────────────────────────────────
    sub.add_parser("list", help="List all stored extraction files")

    # models ──────────────────────────────────────────────────────────────────
    sub.add_parser("models", help="List locally available Ollama models")

    # convert ─────────────────────────────────────────────────────────────────
    p = sub.add_parser("convert", help="Convert between JSON and YAML")
    p.add_argument("file",  metavar="FILE")
    p.add_argument("--to",  required=True, choices=["json", "yaml"])

    return parser


def main() -> None:
    parser = _build_parser()
    args   = parser.parse_args()

    dispatch = {
        "extract": cmd_extract,
        "chat":    cmd_chat,
        "edit":    cmd_edit,
        "list":    cmd_list,
        "models":  cmd_models,
        "convert": cmd_convert,
    }

    handler = dispatch.get(args.command)
    if handler is None:
        parser.print_help()
        sys.exit(0)

    handler(args)


if __name__ == "__main__":
    main()
