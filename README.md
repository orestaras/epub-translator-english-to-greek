# translate_epub_gui_to_greek (DeepSeek)

A tiny, GUI-based EPUB translator that preserves HTML structure and outputs a fully localized Greek EPUB next to your original file.

- **Click-to-run GUI** (Tkinter): pick `.epub` → progress bar → saves `<name>-greek.epub`
- **Structure-preserving**: keeps all tags/attributes; translates only visible text nodes
- **Fast & low-cost**: parallel requests, retry/repair passes, light quality checks
- **No code edits needed**: just set your API key and run

---

## ✨ What it does (in short)

- Reads your EPUB with `ebooklib`
- Splits each XHTML into HTML-aware chunks (paragraphs, headers, etc.)
- Sends chunks to **DeepSeek** (`deepseek-chat` by default) with a strict system prompt to **translate to Greek while preserving HTML**
- Runs minimal QA (Greek-ratio & “long English runs”) and optional repair passes
- Stitches everything back and writes a clean Greek EPUB with updated metadata (`lang="el"`)

---

## 🚀 Quick start

### 1) Requirements
- **Python 3.9+**
- `pip install ebooklib requests`

> On Linux you may need Tk support: `sudo apt-get install python3-tk`

### 2) Get a DeepSeek API key
Create a key from your DeepSeek account, then keep it private.

### 3) Configure the key
This repo ships a tiny obfuscation helper (XOR) so the key isn’t stored plainly in the file.  
Open `translate_epub_gui_to_greek_fast_progress_deepseek.py` and update the `_get_api_key()` encoder data with **your** key.

> Tip: For open-source/public repos, prefer environment variables or an OS keychain. Never commit real keys.

### 4) Run
```bash
python translate_epub_gui_to_greek_fast_progress_deepseek.py
```
Choose your `.epub`. A progress window will show chunk counts; the app saves `<name>-greek.epub` next to the original.

---

## ⚙️ Notable settings

- `MODEL = "deepseek-chat"` (you can switch to `"deepseek-reasoner"`)
- `MAX_WORKERS = 8` (parallelism)
- `REPAIR_PASSES = 1` (extra polish if English slips through)
- `GREEK_MIN_RATIO = 0.90`, `MAX_ENGLISH_RUNS = 0` (basic QA)
- `CONTEXT_TAIL_CHARS = 800` (keeps narrative continuity across chunks)
- `MAX_TOKENS_PER_CHUNK = 500` and `CHARS_PER_TOKEN = 4` (chunk sizing heuristic)

---

## 🧠 How it preserves structure

- The system prompt **forbids** tag/attribute changes and skips translating inside `<code>`, `<pre>`, `<script>`, `<style>`
- Chunking respects common block boundaries (e.g., `</p>`, `</h1>` …), reducing broken HTML
- QA checks scan only **text** (tags stripped) to avoid false positives

---

## 💸 Cost example — *“Walden Two” (310 pages) ≈ $0,33*

In a real-world run, translating the ~310-page novel **Walden Two** via `deepseek-chat` cost **about $0,33** in total API usage.  
Your exact cost will vary with edition length (tokens), chunking, retries, and provider pricing at the time you run it. Always check your provider’s current price card before large jobs.

**Back-of-the-envelope:** if a novel yields ~100k–150k input tokens and similar output, translation typically lands in the **tens of cents** range with current pricing.

---

## 📚 Usage notes & limits

- **EPUB quality matters:** well-formed XHTML translates best. Scanned/OCR’d EPUBs may need cleanup.
- **Language output:** Modern Greek (Δημοτική), preserving voices/idioms and tone.
- **Rate limits & stability:** extremely aggressive parallelism can hit provider limits; tune `MAX_WORKERS` and retries.

---

## 🔐 Security

- The included XOR method only **obscures** the key and stops casual scraping; it’s not cryptographic security.
- Prefer **environment variables** or an OS **keychain/credential manager** for real protection.
- **Never** commit live keys to public repos (rotate immediately if you did).

---

## ⚖️ Legal

Translate only content you **own** or are **licensed** to process. This tool doesn’t bypass DRM. Respect the copyright and terms of your content sources.

---

## 🛠 Troubleshooting

- **“Could not read EPUB”** → re-export or validate with an EPUB checker.
- **Broken accents/encoding** → ensure UTF-8; `ebooklib` reads/outputs UTF-8 by default.
- **HTML out of balance** → reduce `MAX_TOKENS_PER_CHUNK` or set `REPAIR_PASSES = 2`.
- **Provider errors** → lower `MAX_WORKERS` or increase `RETRY_COUNT`.

---

## 📄 License

MIT. See `LICENSE` in the repo.
