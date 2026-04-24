# PDF Information Extractor

Extract information from PDF files, store as JSON/YAML, and chat about the content using a **free local LLM — no API key required**.

---

## Features

- **Text PDFs** — fast extraction with `pdfplumber`
- **Scanned PDFs** — automatic OCR fallback via `pytesseract` + `pdf2image`
- **Mixed PDFs** — per-page detection (text vs image)
- **Interactive editor** — view and modify extracted data with dot-notation
- **Local LLM chat** — powered by [Ollama](https://ollama.ai) (llama3.2, mistral, phi3, …)
- **Two data formats** — JSON (default) or YAML (more readable, ~25% smaller)

---

## Installation

### 1. Clone the repository

```bash
git clone https://github.com/zhtushar23/pdf_infoEaxtractor.git
cd pdf-infoExtractor
```

### 2. Create and activate a virtual environment

**Using conda:**

```bash
conda create -n pdf-chatbot python=3.11
conda activate pdf-chatbot
```

**Or using venv:**

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate
```

### 3. Install Python dependencies

```bash
pip install -r requirements.txt
```

### 4. Install Ollama (free local LLM)

Download and install from **https://ollama.ai**

Then pull a model (one-time download):

```bash
ollama pull llama3.2      # 2 GB — recommended
ollama pull phi3          # 1.7 GB — lightest / fastest
ollama pull mistral       # 4 GB — strongest reasoning
```

Start the Ollama server (keep this running in the background):

```bash
ollama serve
```

### 5. (Optional) OCR support — for scanned / image-only PDFs

Install two system-level binaries:

| Tool | Download |
|---|---|
| **Tesseract** | https://github.com/UB-Mannheim/tesseract/wiki (Windows) · `brew install tesseract` (macOS) · `apt install tesseract-ocr` (Linux) |
| **Poppler** | https://github.com/oschwartz10612/poppler-windows/releases (Windows) · `brew install poppler` (macOS) · `apt install poppler-utils` (Linux) |

After installing on Windows, add both to your system `PATH`:

```
C:\Program Files\Tesseract-OCR
C:\poppler\Library\bin
```

Verify:
```bash
tesseract --version
pdftoppm -v
```

---

## VS Code Setup

### Select the interpreter

`Ctrl+Shift+P` → **Python: Select Interpreter** → choose the environment you created above.

### Enable conda in the VS Code terminal (Windows)

Run once in Anaconda Prompt, then restart VS Code:

```powershell
conda init powershell
```

---

## Usage

### Extract a PDF

```bash
# Digital PDF (text-based)
python main.py extract report.pdf

# Scanned PDF (force OCR)
python main.py extract scan.pdf --ocr

# Save as YAML instead of JSON
python main.py extract report.pdf --format yaml

# Custom output path
python main.py extract report.pdf --output my_data/report.json
```

### Chat about an extracted PDF

```bash
# Default model (llama3.2)
python main.py chat pdf_data/report.json

# Choose a specific model
python main.py chat pdf_data/report.json --model mistral
python main.py chat pdf_data/report.json --model phi3
```

**Chat commands (inside the session):**

| Command | Action |
|---|---|
| `quit` / `exit` | Exit chat |
| `clear` | Reset conversation history |
| `info` | Show file and model info |

### Edit extracted data interactively

```bash
python main.py edit pdf_data/report.json
```

**Editor commands:**

| Command | Description |
|---|---|
| `view` | Show all data (syntax-highlighted) |
| `view metadata.title` | Show a specific field (dot notation) |
| `set metadata.title "New Title"` | Update a value |
| `set content.0.text "corrected text"` | Edit page text |
| `del content.2.tables.0` | Delete a key or list item |
| `add metadata.tags ["research","tag2"]` | Add a new field (JSON value) |
| `list` | List all leaf key paths |
| `search keyword` | Search keys and values |
| `undo` | Undo last change |
| `history` | Show change history |
| `save` | Save to current file |
| `save path/to/new.json` | Save to a different file |
| `export yaml` | Save a copy as YAML |
| `export json` | Save a copy as JSON |
| `help` | Show all commands |
| `quit` | Exit (prompts if unsaved) |

**Dot notation examples:**

```
metadata.title          → top-level field
content.0.text          → first page text
content.2.tables.0      → first table on page 3
content.2.tables.0.1    → second row of that table
```

### List stored files

```bash
python main.py list
```

### List available Ollama models

```bash
python main.py models
```

### Convert between JSON and YAML

```bash
python main.py convert pdf_data/report.json --to yaml
python main.py convert pdf_data/report.yaml --to json
```

---

## Data Format Comparison

| Format | Size | Human-editable | Comments | Best for |
|---|---|---|---|---|
| **JSON** | 100% | Yes | No | Default, universal |
| **YAML** | ~75% | Easiest | Yes (`#`) | Hand-editing |
| SQLite | ~40% | No | No | Tabular / relational data |
| MessagePack | ~35% | No | No | High-performance binary |

> **Recommendation:** use **YAML** if you plan to hand-edit files; **JSON** for programmatic use.

---

## Extracted JSON Structure

```json
{
  "metadata": {
    "filename": "report.pdf",
    "filepath": "/path/to/report.pdf",
    "extracted_at": "2026-04-19T12:00:00",
    "pages": 10,
    "method": "text | ocr | mixed (3/10 pages OCR)",
    "title": "Document Title",
    "author": "Author Name",
    "subject": "",
    "creator": ""
  },
  "content": [
    {
      "page": 1,
      "text": "Page content here ...",
      "tables": [
        [
          ["Header 1", "Header 2"],
          ["Row 1 Col 1", "Row 1 Col 2"]
        ]
      ],
      "ocr": false
    }
  ],
  "full_text": "[Page 1]\nAll pages concatenated..."
}
```

---

## Troubleshooting

| Problem | Fix |
|---|---|
| `ollama: command not found` | Install Ollama from https://ollama.ai and run `ollama serve` |
| `Model 'llama3.2' not found` | Run `ollama pull llama3.2` |
| OCR produces no text | Ensure Tesseract and Poppler are installed and in PATH |
| Blank text extracted | PDF is likely scanned — re-run with `--ocr` flag |
| `pdfplumber` not found | Run `pip install -r requirements.txt` |
| VS Code terminal has no conda | Run `conda init powershell` in Anaconda Prompt, then restart VS Code |

---

## Project Structure

```
pdf_infoExtractor/
├── main.py                  # CLI entry point
├── requirements.txt         # Python dependencies
├── README.md                # This file
├── .vscode/
│   └── settings.json        # VS Code interpreter + terminal config
├── pdf_chatbot/
│   ├── extractor.py         # PDF text extraction + OCR fallback
│   ├── storage.py           # JSON / YAML save & load
│   ├── editor.py            # Interactive data editor
│   └── chat.py              # Ollama chat session
└── pdf_data/                # Extracted files (auto-created)
    ├── report.json
    └── report.yaml
```

---

## License

MIT
