"""
Chat about extracted PDF data using a locally running Ollama model.

No API key required. Completely free and offline after initial model download.

Setup
-----
1. Install Ollama  : https://ollama.ai  (Windows installer)
2. In your conda env, install the Python client:
       pip install ollama
3. Pull a model (one-time, runs Ollama in the background automatically):
       python -c "import ollama; ollama.pull('llama3.2')"
   Or use the Ollama desktop app to pull models.

Then run: python main.py chat <file>
"""

from __future__ import annotations

import sys

import ollama

DEFAULT_MODEL = "llama3.2"

# Local models have limited context windows. Keep the PDF excerpt short enough
# that the conversation history also fits. Increase if your model supports it.
MAX_CONTEXT_CHARS = 6_000


# ─── Ollama helpers ───────────────────────────────────────────────────────────

def check_ollama() -> bool:
    """Return True if Ollama is running and reachable."""
    try:
        ollama.list()
        return True
    except Exception:
        return False


def list_models() -> list[str]:
    """Return names of locally available Ollama models."""
    try:
        response = ollama.list()
        return [m.model for m in response.models]
    except Exception:
        return []


def pull_model(model: str) -> None:
    """Pull a model from Ollama, showing progress."""
    print(f"  Pulling '{model}' — this may take a few minutes on first run…")
    try:
        for progress in ollama.pull(model, stream=True):
            status = getattr(progress, "status", "")
            if status:
                print(f"  {status}", end="\r")
        print()
    except Exception as exc:
        print(f"  Pull failed: {exc}", file=sys.stderr)


def _stream_response(messages: list[dict], model: str) -> str:
    """Send a chat request to Ollama, stream tokens to stdout, return full text."""
    full = ""
    try:
        for chunk in ollama.chat(model=model, messages=messages, stream=True):
            token = chunk.message.content or ""
            print(token, end="", flush=True)
            full += token
    except ollama.ResponseError as exc:
        print(f"\n[Error] Ollama: {exc.error}", file=sys.stderr)
    except Exception as exc:
        print(f"\n[Error] {exc}", file=sys.stderr)
    return full


# ─── Context builder ─────────────────────────────────────────────────────────

def _build_context(data: dict, max_chars: int = MAX_CONTEXT_CHARS) -> str:
    """Condense extracted PDF data into a text block for the system prompt."""
    meta  = data.get("metadata", {})
    lines = [
        "=== DOCUMENT ===",
        f"File  : {meta.get('filename', 'unknown')}",
    ]
    if meta.get("title"):
        lines.append(f"Title : {meta['title']}")
    if meta.get("author"):
        lines.append(f"Author: {meta['author']}")
    lines.append(f"Pages : {meta.get('pages', '?')}")
    lines.append("")

    header_len = sum(len(l) + 1 for l in lines)
    budget     = max_chars - header_len
    full_text  = data.get("full_text", "")

    if len(full_text) > budget:
        full_text = full_text[:budget] + "\n…[content truncated — PDF is large]"

    lines.append(full_text)
    return "\n".join(lines)


# ─── Chat session ─────────────────────────────────────────────────────────────

def start_chat(data: dict, model: str = DEFAULT_MODEL) -> None:
    """Run an interactive multi-turn chat about *data* using Ollama."""

    # ── Pre-flight checks ────────────────────────────────────────────────────
    if not check_ollama():
        print("\nError: Ollama is not running.", file=sys.stderr)
        print("  1. Install  → https://ollama.ai  (Windows installer)", file=sys.stderr)
        print("  2. Launch   → open the Ollama desktop app, or run 'ollama serve'", file=sys.stderr)
        print(f"  3. Pull     → python -c \"import ollama; ollama.pull('{model}')\"", file=sys.stderr)
        sys.exit(1)

    available = list_models()
    if available and model not in available:
        print(f"Model '{model}' not found locally.")
        print(f"Available: {', '.join(available)}")
        ans = input(f"  Pull '{model}' now? [y/N]: ").strip().lower()
        if ans == "y":
            pull_model(model)
            available = list_models()
        if model not in available:
            if available:
                model = available[0]
                print(f"Using '{model}' instead.\n")
            else:
                print(f"No models available. Run: python -c \"import ollama; ollama.pull('llama3.2')\"")
                sys.exit(1)
    elif not available:
        print(f"No models installed.")
        ans = input(f"  Pull '{model}' now? (~2 GB, one-time download) [y/N]: ").strip().lower()
        if ans == "y":
            pull_model(model)
        else:
            print(f"  Run later: python -c \"import ollama; ollama.pull('{model}')\"")
            sys.exit(1)

    # ── Build system prompt ───────────────────────────────────────────────────
    context = _build_context(data)
    system  = (
        "You are a helpful assistant. The user has loaded a PDF document. "
        "Answer questions based solely on the document content shown below. "
        "When citing information, mention the page number if known. "
        "If the answer is not in the document, say so clearly.\n\n"
        f"{context}"
    )

    messages: list[dict] = [{"role": "system", "content": system}]

    filename = data["metadata"]["filename"]
    pages    = data["metadata"]["pages"]
    method   = data["metadata"].get("method", "text")

    print(f"\n{'─'*60}")
    print(f"  File  : {filename}  ({pages} pages, {method})")
    print(f"  Model : {model}  [local — no API key]")
    print(f"{'─'*60}")
    print("  Ask anything about this document.")
    print("  Commands: quit | clear (reset history) | info")
    print(f"{'─'*60}\n")

    while True:
        try:
            user_input = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye!")
            break

        if not user_input:
            continue

        # ── Built-in commands ─────────────────────────────────────────────────
        if user_input.lower() in {"quit", "exit", "q"}:
            print("Goodbye!")
            break

        if user_input.lower() == "clear":
            messages = [{"role": "system", "content": system}]
            print("  [Conversation history cleared]\n")
            continue

        if user_input.lower() == "info":
            print(f"  Model        : {model}")
            print(f"  File         : {filename}")
            print(f"  Pages        : {pages}")
            print(f"  Method       : {method}")
            print(f"  History turns: {(len(messages) - 1) // 2}\n")
            continue

        # ── LLM call ──────────────────────────────────────────────────────────
        messages.append({"role": "user", "content": user_input})
        print("Assistant: ", end="", flush=True)

        reply = _stream_response(messages, model)
        print("\n")

        if reply:
            messages.append({"role": "assistant", "content": reply})
        else:
            # Remove the unanswered user turn so history stays consistent
            messages.pop()
