# EPUB → Greek Translator (DeepSeek)

A small Python GUI tool that translates `.epub` files into **Greek** using the DeepSeek API.

- Pick an `.epub` file
- Watch a progress bar while it works
- Saves a sibling file named `<name>-greek.epub`

> **Important:** Never hardcode API keys. This app reads `DEEPSEEK_API_KEY` from environment variables or a local `.env` file.

## 🔧 Installation (Windows/macOS/Linux)

1. Install **Python 3.10+**.
2. Clone/download this repository.
3. In a terminal from the project folder:
   ```bash
   python -m venv .venv
   # Windows
   .venv\Scripts\activate
   # macOS/Linux
   source .venv/bin/activate

   pip install -r requirements.txt
   ```

> On Linux you may need: `sudo apt install python3-tk` (for Tkinter GUI).

## 🔑 API Setup

Create a `.env` file (or export env vars) like:
```
DEEPSEEK_API_KEY=PASTE_YOUR_KEY_HERE
# Optional:
# DEEPSEEK_MODEL=deepseek-chat
# DEEPSEEK_API_URL=https://api.deepseek.com/v1/chat/completions
# MAX_WORKERS=8
# RETRY_COUNT=3
# TEMPERATURE=0.7
# APP_LANG=en   # set 'el' for Greek UI
```

> **Do not** commit `.env` to GitHub. It contains secrets.

## ▶️ Usage

- **GUI**:
  ```bash
  python translate_epub_gui_to_greek_fast_progress_deepseek.py
  ```
- **CLI (no GUI)**:
  ```bash
  python translate_epub_gui_to_greek_fast_progress_deepseek.py /path/to/book.epub
  ```

## 🌐 UI Language

The UI supports **English** and **Greek**. Set via env var:
```
APP_LANG=en   # or el
```
If `APP_LANG` is not set, it tries to infer from `LANG` (defaults to English).

## ⚙️ Quality & Consistency

- HTML-aware chunking that preserves structure (tags/attributes).
- Context tail from previous source chunk for better continuity.
- Heuristics to detect residual English and optionally run repair passes.

## 🛡️ Key Security

- Keys are read from environment or `.env` (see `.env.example`).
- `.gitignore` excludes `.env` from commits.

## ❗ Troubleshooting

- **429 Rate limited**: lower `MAX_WORKERS` or try later.
- **GUI fails on Linux**: `sudo apt install python3-tk`.
- **Missing key**: create `.env` or export `DEEPSEEK_API_KEY`.

## 📝 License

MIT (see `LICENSE`).

## 🤝 Contributing

See [CONTRIBUTING.en.md](CONTRIBUTING.en.md) or [CONTRIBUTING.el.md](CONTRIBUTING.el.md).

## 💶 Indicative Cost

For transparency: translating *"Wanden Two"* with **deepseek-chat** cost **about €0.33** (33 euro cents).  
Actual costs vary by model, token counts, and settings.
