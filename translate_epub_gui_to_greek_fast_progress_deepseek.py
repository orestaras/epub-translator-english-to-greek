# translate_epub_gui_to_greek_fast_progress_deepseek.py
# Run -> pick .epub -> progress bar -> outputs "<name>-greek.epub" next to original.
# IMPORTANT: Do NOT hardcode secrets. Use environment variables or a .env file.
# This script loads DEEPSEEK_API_KEY from the environment (and .env if present).

import os, re, time, random, threading, queue, json, requests, sys
from concurrent.futures import ThreadPoolExecutor, as_completed
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

try:
    # Optional: load .env if present
    from dotenv import load_dotenv  # type: ignore
    load_dotenv()
except Exception:
    pass

from ebooklib import epub, ITEM_DOCUMENT

# ==== SETTINGS (env-first, with safe defaults) ====
API_KEY = (
    os.getenv("DEEPSEEK_API_KEY")                        # preferred
    or os.getenv("DS_API_KEY")                           # alt name
    or ""
)
API_URL = os.getenv("DEEPSEEK_API_URL", "https://api.deepseek.com/v1/chat/completions")
MODEL   = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")   # or "deepseek-reasoner"

MAX_WORKERS = int(os.getenv("MAX_WORKERS", "8"))
RETRY_COUNT = int(os.getenv("RETRY_COUNT", "3"))
TEMPERATURE_ENV = os.getenv("TEMPERATURE", "0.7")
TEMPERATURE = None if TEMPERATURE_ENV.lower() == "none" else float(TEMPERATURE_ENV)

MAX_TOKENS_PER_CHUNK = int(os.getenv("MAX_TOKENS_PER_CHUNK", "500"))  # rough target
CHARS_PER_TOKEN = int(os.getenv("CHARS_PER_TOKEN", "4"))              # heuristic

# Quality/consistency controls
REPAIR_PASSES = int(os.getenv("REPAIR_PASSES", "1"))         # 0..2 is reasonable
GREEK_MIN_RATIO = float(os.getenv("GREEK_MIN_RATIO", "0.90"))# min share of Greek letters in (Greek+Latin)
MAX_ENGLISH_RUNS = int(os.getenv("MAX_ENGLISH_RUNS", "0"))   # allow this many long English runs (A-Za-z{6,})
CONTEXT_TAIL_CHARS = int(os.getenv("CONTEXT_TAIL_CHARS", "800"))  # pass previous source tail (stripped) as context
REQUEST_TIMEOUT = int(os.getenv("REQUEST_TIMEOUT", "120"))


# ----- Simple i18n (English/Greek) for UI strings -----
APP_LANG = (os.getenv("APP_LANG") or os.getenv("LANG", "en")).lower()
APP_LANG = "el" if APP_LANG.startswith("el") else "en"

UI = {
    "en": {
        "choose_title": "Choose an EPUB to translate to Greek",
        "filetypes_epub": "EPUB files",
        "all_files": "All files",
        "not_a_file": "Selected path is not a file.",
        "read_error_title": "Read error",
        "prep_error_title": "Prep error",
        "empty_error_title": "Empty",
        "empty_error_msg": "No translatable HTML content found.",
        "progress_title": "Translating EPUB…",
        "done_title": "Done",
        "saved_prefix": "Saved:",
        "translation_error_title": "Translation error",
        "missing_key_title": "Missing API key",
        "missing_key_msg": "Missing DEEPSEEK_API_KEY. Create a .env file or set the environment variable and try again.",
        "no_file_selected": "No file selected.",
        "progress_fmt": "{done} / {total} chunks",
    },
    "el": {
        "choose_title": "Επιλέξτε EPUB για μετάφραση στα Ελληνικά",
        "filetypes_epub": "Αρχεία EPUB",
        "all_files": "Όλα τα αρχεία",
        "not_a_file": "Το επιλεγμένο μονοπάτι δεν είναι αρχείο.",
        "read_error_title": "Σφάλμα ανάγνωσης",
        "prep_error_title": "Σφάλμα προετοιμασίας",
        "empty_error_title": "Κενό",
        "empty_error_msg": "Δεν βρέθηκε μεταφράσιμο περιεχόμενο HTML.",
        "progress_title": "Μετάφραση EPUB…",
        "done_title": "Ολοκληρώθηκε",
        "saved_prefix": "Αποθηκεύτηκε:",
        "translation_error_title": "Σφάλμα μετάφρασης",
        "missing_key_title": "Λείπει API key",
        "missing_key_msg": "Λείπει το DEEPSEEK_API_KEY. Δημιουργήστε ένα .env αρχείο ή ορίστε τη μεταβλητή περιβάλλοντος και δοκιμάστε ξανά.",
        "no_file_selected": "Δεν επιλέχθηκε αρχείο.",
        "progress_fmt": "{done} / {total} τμήματα",
    },
}[APP_LANG]
# --------------------------------------------------------

# ====== Pro translation prompt (UPDATED) ======
SYSTEM_PROMPT = (
    "ROLE: You are a professional literary translator. Translate ONLY visible text nodes into Greek—"
    "return valid HTML with the SAME tag structure.\n\n"
    "STRUCTURE RULES (MUST FOLLOW):\n"
    "• Keep ALL tags, attributes, ids, classes, href/src exactly as-is; never add/remove/reorder tags.\n"
    "• Do NOT translate attribute values, URLs, anchors, code identifiers, or inside <code>, <pre>, <script>, <style>.\n"
    "• Preserve whitespace, line breaks, HTML entities (&nbsp;, &amp;, …).\n"
    "• Output must be valid HTML with identical structure; ONLY text nodes may change.\n\n"
    "TRANSLATION QUALITY:\n"
    "• Mirror tone/pacing/register (noir, whimsical, lyrical, tense; short punchy vs. languid).\n"
    "• Keep narrative distance and tense (incl. free indirect style) consistent.\n"
    "• Preserve imagery, metaphors, and symbolism; adapt metaphors ONLY if opaque in Greek—keep the same emotional weight.\n"
    "• Render idioms with Greek equivalents; if none fits, translate for meaning while keeping rhythm.\n"
    "• Keep names/places/brands as-is unless explicitly instructed.\n"
    "• Match the intensity of taboo/swear language—don’t sanitize or exaggerate.\n\n"
    "GREEK-SPECIFIC GUIDANCE:\n"
    "• Resolve grammatical gender and agreement naturally from context (articles, adjectives, participles).\n"
    "• Prefer Δημοτική (standard modern Greek). Maintain character voices (idiolects, slang, tics). Don’t flatten voices.\n"
    "• Keep typography sensible (dashes, quotes). Numbers/units stay as in source unless Greek usage clearly demands otherwise.\n\n"
    "ABSOLUTE REQUIREMENTS:\n"
    "• Do NOT leave any English source text untranslated (unless inside protected tags listed above).\n"
    "• Do NOT add translator notes or explanations.\n"
    "• Return ONLY the translated HTML fragment—no preface or commentary.\n\n"
    "You may be given a <CONTEXT> (do not translate) to keep continuity across chunks."
)

# ——— Chunking helpers (HTML-aware) ———
BLOCK_SPLIT_RE = re.compile(r'(?i)(</p>|</li>|</div>|</h[1-6]>|</blockquote>|</section>|</article>|<br\\s*/?>)')

def split_html_blocks(html: str):
    parts = BLOCK_SPLIT_RE.split(html)
    if len(parts) == 1:
        return [html]
    blocks, i = [], 0
    while i < len(parts):
        chunk = parts[i] or ""
        if i + 1 < len(parts) and BLOCK_SPLIT_RE.fullmatch(parts[i+1] or ""):
            chunk += parts[i+1] or ""
            i += 2
        else:
            i += 1
        blocks.append(chunk)
    return blocks

def chunk_html_for_llm(html: str, max_chars: int):
    blocks = split_html_blocks(html)
    out, buf, size = [], [], 0
    for b in blocks:
        blen = len(b)
        if size + blen > max_chars and buf:
            out.append("".join(buf))
            buf, size = [b], blen
        else:
            buf.append(b); size += blen
    if buf:
        out.append("".join(buf))
    return out

# ===== Quality checks & helpers =====
GREEK = re.compile(r'[\\u0370-\\u03FF\\u1F00-\\u1FFF]')   # Greek & extended
LATIN = re.compile(r'[A-Za-z]')
ENGLISH_RUN = re.compile(r'[A-Za-z]{6,}')

def strip_tags(html: str) -> str:
    return re.sub(r'<[^>]*>', ' ', html or '')

def greek_ratio(s: str) -> float:
    greek = len(GREEK.findall(s))
    latin = len(LATIN.findall(s))
    denom = (greek + latin) or 1
    return greek / denom

def english_runs_count(s: str) -> int:
    return len(ENGLISH_RUN.findall(s))

def looks_greek_enough(html: str) -> bool:
    ratio = greek_ratio(html)
    runs = english_runs_count(strip_tags(html))
    return ratio >= GREEK_MIN_RATIO and runs <= MAX_ENGLISH_RUNS

# ——— DeepSeek API helpers ———
def ds_chat(messages, temperature=TEMPERATURE, timeout=REQUEST_TIMEOUT):
    """Call DeepSeek chat/completions; return assistant content string."""
    if not API_KEY:
        raise RuntimeError("Missing DEEPSEEK_API_KEY. Set it in your environment or .env file.")
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {"model": MODEL, "messages": messages}
    if temperature is not None:
        payload["temperature"] = float(temperature)
    r = requests.post(API_URL, headers=headers, json=payload, timeout=timeout)
    if r.status_code == 429:
        # Rate limited
        raise RuntimeError(f"Rate limited (429). Consider lowering MAX_WORKERS or retrying later. Body: {r.text[:800]}")
    if r.status_code >= 400:
        raise RuntimeError(f"DeepSeek API error {r.status_code}: {r.text[:1500]}")
    data = r.json()
    try:
        return (data["choices"][0]["message"]["content"] or "").strip()
    except Exception:
        raise RuntimeError(f"Unexpected DeepSeek response shape: {json.dumps(data)[:800]}")

def translate_one_with_context(fragment: str, context: str = "") -> str:
    msgs = [{"role": "system", "content": SYSTEM_PROMPT}]
    if context:
        msgs.append({"role": "user", "content": f"<CONTEXT>(do not translate):\n{context}\n</CONTEXT>"})
    msgs.append({"role": "user", "content": fragment})

    delay = 0.6
    last_err = None
    for attempt in range(RETRY_COUNT):
        try:
            return ds_chat(msgs)
        except Exception as e:
            last_err = e
            if attempt == RETRY_COUNT - 1:
                break
            time.sleep(delay + random.random() * 0.2)
            delay *= 2
    raise last_err or RuntimeError("DeepSeek call failed")

def repair_fragment(original_fragment: str, bad_output: str, context: str = "") -> str:
    instruction = (
        "Fix any remaining untranslated English or mixed-language segments in the fragment below.\n"
        "Preserve the EXACT HTML structure and tags of the original.\n"
        "Return ONLY the corrected HTML in Greek."
    )
    msgs = [{"role": "system", "content": SYSTEM_PROMPT}]
    if context:
        msgs.append({"role": "user", "content": f"<CONTEXT>(do not translate):\n{context}\n</CONTEXT>"})
    msgs.append({
        "role": "user",
        "content": f"{instruction}\n\n<ORIGINAL_HTML>\n{original_fragment}\n</ORIGINAL_HTML>"
    })
    return ds_chat(msgs)

# ——— Translation worker (with context + QA/repair) ———
def translate_chunk(idx: int, fragment: str, context: str):
    delay = 0.6
    for attempt in range(RETRY_COUNT):
        try:
            out = translate_one_with_context(fragment, context)
            if not looks_greek_enough(out):
                fixed = out
                for _ in range(REPAIR_PASSES):
                    fixed = repair_fragment(fragment, fixed, context)
                    if looks_greek_enough(fixed):
                        break
                out = fixed
            return idx, (out or "").strip()
        except Exception as e:
            if attempt == RETRY_COUNT - 1:
                raise
            time.sleep(delay + random.random() * 0.2)
            delay *= 2

# ——— Main app ———
def main():
    # Preflight
    if not API_KEY:
        print("ERROR: Missing DEEPSEEK_API_KEY. Create a .env file or set the environment variable and try again.")
        messagebox.showerror(UI["missing_key_title"], UI["missing_key_msg"])
        return

    # Pick EPUB
    root = tk.Tk()
    root.withdraw()
    in_path = filedialog.askopenfilename(
        title=UI["choose_title"],
        filetypes=[(UI["filetypes_epub"], "*.epub"), (UI["all_files"], "*.*")]
    )
    if not in_path:
        print(UI["no_file_selected"])
        return
    if not os.path.isfile(in_path):
        messagebox.showerror("Error", UI["not_a_file"])
        return

    base, ext = os.path.splitext(in_path)
    out_path = f"{base}-greek{ext or '.epub'}"

    # Read EPUB
    try:
        book = epub.read_epub(in_path)
    except Exception as e:
        messagebox.showerror(UI["read_error_title"], f"Could not read EPUB:\n{e}")
        return

    # Gather XHTML items and pre-chunk (add per-chunk CONTEXT from previous source chunk)
    target_chars = max(500, int(MAX_TOKENS_PER_CHUNK * CHARS_PER_TOKEN))
    doc_items = list(book.get_items_of_type(ITEM_DOCUMENT))

    plan = []           # (doc_idx, chunk_idx, text, context)
    per_doc_counts = [] # number of chunks per doc
    try:
        for d_i, it in enumerate(doc_items):
            html = it.get_content().decode("utf-8", errors="ignore")
            chunks = chunk_html_for_llm(html, target_chars)
            per_doc_counts.append(len(chunks))

            prev_tail_src = ""  # source-based context tail (stripped)
            for c_i, c in enumerate(chunks):
                context = (prev_tail_src[-CONTEXT_TAIL_CHARS:]) if prev_tail_src else ""
                plan.append((d_i, c_i, c, context))
                prev_tail_src = strip_tags(c)  # update with source tail for next chunk
    except Exception as e:
        messagebox.showerror(UI["prep_error_title"], f"Failed preparing chunks:\n{e}")
        return

    if not plan:
        messagebox.showerror(UI["empty_error_title"], UI["empty_error_msg"])
        return

    # Progress UI
    prog = tk.Toplevel(root)
    prog.title(UI["progress_title"])
    prog.geometry("520x160")
    tk.Label(prog, text=os.path.basename(in_path), wraplength=480).pack(pady=(10, 4))
    bar = ttk.Progressbar(prog, orient="horizontal", mode="determinate", length=480)
    bar.pack(pady=6)
    bar["maximum"] = len(plan)
    bar["value"] = 0
    status = tk.Label(prog, text=UI["progress_fmt"].format(done=0, total=len(plan)))
    status.pack(pady=(0, 8))

    q = queue.Queue()

    def worker():
        try:
            translated = {d_i: [None] * n for d_i, n in enumerate(per_doc_counts)}
            with ThreadPoolExecutor(max_workers=min(MAX_WORKERS, len(plan))) as ex:
                futures = {
                    ex.submit(translate_chunk, i, text, context): (d_i, c_i)
                    for i, (d_i, c_i, text, context) in enumerate(plan)
                }
                for fut in as_completed(futures):
                    d_i, c_i = futures[fut]
                    _, html_greek = fut.result()
                    translated[d_i][c_i] = html_greek
                    q.put(("progress", 1))

            # Assemble each XHTML back (ensure no None remains)
            for d_i, it in enumerate(doc_items):
                chunks_list = translated[d_i]
                if any(x is None for x in chunks_list):
                    raise RuntimeError("Some chunks failed to translate. Try reducing MAX_WORKERS or increasing RETRY_COUNT.")
                new_html = "".join(chunks_list)
                it.set_content(new_html.encode("utf-8"))

            # Update metadata (title/lang), then write
            try:
                titles = book.get_metadata("DC", "title")
                title = titles[0][0] if titles and titles[0] and titles[0][0] else "Translated"
                book.set_title(f"{title} — Greek")
            except Exception:
                pass
            try:
                book.set_language("el")
            except Exception:
                pass

            epub.write_epub(out_path, book)
            q.put(("done", out_path))
        except Exception as e:
            q.put(("error", str(e)))

    threading.Thread(target=worker, daemon=True).start()

    def poll_queue():
        try:
            while True:
                kind, payload = q.get_nowait()
                if kind == "progress":
                    bar["value"] += payload
                    status.config(text=UI["progress_fmt"].format(done=int(bar["value"]), total=int(bar["maximum"])))
                elif kind == "done":
                    messagebox.showinfo(UI["done_title"], f"{UI['saved_prefix']}\n{payload}")
                    prog.destroy(); root.destroy()
                    return
                elif kind == "error":
                    messagebox.showerror(UI["translation_error_title"], payload)
                    prog.destroy(); root.destroy()
                    return
        except queue.Empty:
            pass
        prog.after(120, poll_queue)

    prog.after(120, poll_queue)
    root.mainloop()

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        # Graceful CLI fallback: allow running with a path argument (no GUI)
        if len(sys.argv) >= 2:
            # Simple non-GUI run if a path is provided
            in_path = sys.argv[1]
            if not API_KEY:
                print("ERROR: Missing DEEPSEEK_API_KEY")
                sys.exit(1)
            if not os.path.isfile(in_path):
                print("ERROR: not a file:", in_path)
                sys.exit(1)
            try:
                book = epub.read_epub(in_path)
            except Exception as ex:
                print("Read error:", ex)
                sys.exit(1)
            target_chars = max(500, int(MAX_TOKENS_PER_CHUNK * CHARS_PER_TOKEN))
            doc_items = list(book.get_items_of_type(ITEM_DOCUMENT))
            plan, per_doc_counts = [], []
            for d_i, it in enumerate(doc_items):
                html = it.get_content().decode("utf-8", errors="ignore")
                chunks = chunk_html_for_llm(html, target_chars)
                per_doc_counts.append(len(chunks))
                prev_tail_src = ""
                for c_i, c in enumerate(chunks):
                    context = (prev_tail_src[-CONTEXT_TAIL_CHARS:]) if prev_tail_src else ""
                    plan.append((d_i, c_i, c, context))
                    prev_tail_src = strip_tags(c)
            translated = {d_i: [None] * n for d_i, n in enumerate(per_doc_counts)}
            with ThreadPoolExecutor(max_workers=min(MAX_WORKERS, len(plan))) as ex:
                futures = {
                    ex.submit(translate_chunk, i, text, context): (d_i, c_i)
                    for i, (d_i, c_i, text, context) in enumerate(plan)
                }
                for fut in as_completed(futures):
                    d_i, c_i = futures[fut]
                    _, html_greek = fut.result()
                    translated[d_i][c_i] = html_greek
            for d_i, it in enumerate(doc_items):
                if any(x is None for x in translated[d_i]):
                    print("Some chunks failed; aborting.")
                    sys.exit(1)
                new_html = "".join(translated[d_i])
                it.set_content(new_html.encode("utf-8"))
            base, ext = os.path.splitext(in_path)
            out_path = f"{base}-greek{ext or '.epub'}"
            try:
                titles = book.get_metadata("DC", "title")
                title = titles[0][0] if titles and titles[0] and titles[0][0] else "Translated"
                book.set_title(f"{title} — Greek")
            except Exception:
                pass
            try:
                book.set_language("el")
            except Exception:
                pass
            epub.write_epub(out_path, book)
            print("Saved:", out_path)
        else:
            raise
