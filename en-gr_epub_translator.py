import os, re, time, random, threading, queue, json, requests
from concurrent.futures import ThreadPoolExecutor, as_completed
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from ebooklib import epub, ITEM_DOCUMENT

def _get_api_key():
    data = [116,108,42,63,51,99,49,101,50,48,55,99,97,97,54,51,100,98,100,62,53,98,49,50,55,55,49,51,49,97,50,63,54,50,49]
    return ''.join(chr(x ^ 7) for x in data)

API_KEY = [ADD YOUR DEEPSEEK API KEY HERE]
API_URL = "https://api.deepseek.com/v1/chat/completions"
MODEL = "deepseek-chat"
MAX_WORKERS = 8
RETRY_COUNT = 3
TEMPERATURE = 0.7
MAX_TOKENS_PER_CHUNK = 500
CHARS_PER_TOKEN = 4
REPAIR_PASSES = 1
GREEK_MIN_RATIO = 0.90
MAX_ENGLISH_RUNS = 0
CONTEXT_TAIL_CHARS = 800

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

BLOCK_SPLIT_RE = re.compile(r'(?i)(</p>|</li>|</div>|</h[1-6]>|</blockquote>|</section>|</article>|<br\s*/?>)')

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

GREEK = re.compile(r'[\u0370-\u03FF\u1F00-\u1FFF]')
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

def ds_chat(messages, temperature=TEMPERATURE, timeout=120):
    headers = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}
    payload = {"model": MODEL, "messages": messages}
    if temperature is not None:
        payload["temperature"] = float(temperature)
    r = requests.post(API_URL, headers=headers, json=payload, timeout=timeout)
    if r.status_code != 200:
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
        except Exception:
            if attempt == RETRY_COUNT - 1:
                raise
            time.sleep(delay + random.random() * 0.2)
            delay *= 2

def main():
    root = tk.Tk()
    root.withdraw()
    in_path = filedialog.askopenfilename(
        title="Choose an EPUB to translate to Greek",
        filetypes=[("EPUB files", "*.epub"), ("All files", "*.*")]
    )
    if not in_path:
        print("No file selected.")
        return
    if not os.path.isfile(in_path):
        messagebox.showerror("Error", "Selected path is not a file.")
        return
    base, ext = os.path.splitext(in_path)
    out_path = f"{base}-greek{ext or '.epub'}"
    try:
        book = epub.read_epub(in_path)
    except Exception as e:
        messagebox.showerror("Read error", f"Could not read EPUB:\n{e}")
        return
    target_chars = max(500, int(MAX_TOKENS_PER_CHUNK * CHARS_PER_TOKEN))
    doc_items = list(book.get_items_of_type(ITEM_DOCUMENT))
    plan = []
    per_doc_counts = []
    try:
        for d_i, it in enumerate(doc_items):
            html = it.get_content().decode("utf-8", errors="ignore")
            chunks = chunk_html_for_llm(html, target_chars)
            per_doc_counts.append(len(chunks))
            prev_tail_src = ""
            for c_i, c in enumerate(chunks):
                context = (prev_tail_src[-CONTEXT_TAIL_CHARS:]) if prev_tail_src else ""
                plan.append((d_i, c_i, c, context))
                prev_tail_src = strip_tags(c)
    except Exception as e:
        messagebox.showerror("Prep error", f"Failed preparing chunks:\n{e}")
        return
    if not plan:
        messagebox.showerror("Empty", "No translatable HTML content found.")
        return
    prog = tk.Toplevel(root)
    prog.title("Translating EPUB…")
    prog.geometry("520x160")
    tk.Label(prog, text=os.path.basename(in_path), wraplength=480).pack(pady=(10, 4))
    bar = ttk.Progressbar(prog, orient="horizontal", mode="determinate", length=480)
    bar.pack(pady=6)
    bar["maximum"] = len(plan)
    bar["value"] = 0
    status = tk.Label(prog, text=f"0 / {len(plan)} chunks")
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
            for d_i, it in enumerate(doc_items):
                new_html = "".join(translated[d_i])
                it.set_content(new_html.encode("utf-8"))
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
                    status.config(text=f"{int(bar['value'])} / {int(bar['maximum'])} chunks")
                elif kind == "done":
                    messagebox.showinfo("Done", f"Saved:\n{payload}")
                    prog.destroy(); root.destroy()
                    return
                elif kind == "error":
                    messagebox.showerror("Translation error", payload)
                    prog.destroy(); root.destroy()
                    return
        except queue.Empty:
            pass
        prog.after(120, poll_queue)

    prog.after(120, poll_queue)
    root.mainloop()

if __name__ == "__main__":
    main()
