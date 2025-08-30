# EPUB → Greek Translator (DeepSeek)

GUI εργαλείο Python που μεταφράζει αρχεία `.epub` στα **Ελληνικά** χρησιμοποιώντας το DeepSeek API.

- Επιλέγετε `.epub` αρχείο
- Βλέπετε μπάρα προόδου
- Αποθηκεύει δίπλα στο αρχικό ένα νέο αρχείο `<name>-greek.epub`

> **Σημαντικό:** Μην βάζετε API keys μέσα στον κώδικα. Το κλειδί διαβάζεται από μεταβλητές περιβάλλοντος ή από `.env`.

## 🔧 Εγκατάσταση (Windows/macOS/Linux)

1. Εγκαταστήστε **Python 3.10+**.
2. Κατεβάστε ή κλωνοποιήστε αυτό το αποθετήριο.
3. Σε τερματικό στον φάκελο του έργου:
   ```bash
   python -m venv .venv
   # Windows
   .venv\Scripts\activate
   # macOS/Linux
   source .venv/bin/activate

   pip install -r requirements.txt
   ```

> Σε Linux ίσως απαιτείται: `sudo apt install python3-tk` (για Tkinter).

## 🔑 Ρύθμιση API

Δημιουργήστε `.env` (ή ορίστε μεταβλητές περιβάλλοντος):
```
DEEPSEEK_API_KEY=ΕΠΙΚΟΛΛΗΣΤΕ_ΤΟ_ΚΛΕΙΔΙ_ΣΑΣ
# Προαιρετικά:
# DEEPSEEK_MODEL=deepseek-chat
# DEEPSEEK_API_URL=https://api.deepseek.com/v1/chat/completions
# MAX_WORKERS=8
# RETRY_COUNT=3
# TEMPERATURE=0.7
# APP_LANG=el  # 'en' για αγγλικό UI
```

> **Προσοχή:** Μην ανεβάζετε ποτέ το `.env` στο GitHub.

## ▶️ Χρήση

- **Με GUI**:
  ```bash
  python translate_epub_gui_to_greek_fast_progress_deepseek.py
  ```
- **Χωρίς GUI (CLI)**:
  ```bash
  python translate_epub_gui_to_greek_fast_progress_deepseek.py /path/to/book.epub
  ```

## 🌐 Γλώσσα UI

Το UI υποστηρίζει **Αγγλικά** και **Ελληνικά**. Ορίζεται με:
```
APP_LANG=el   # ή en
```
Αν δεν οριστεί, γίνεται προσπάθεια αυτόματης ανίχνευσης από `LANG` (προεπιλογή Αγγλικά).

## ⚙️ Ποιότητα/Συνέπεια

- Τμηματοποίηση HTML με διατήρηση δομής (tags/attributes).
- Χρήση «ουράς» κειμένου προηγούμενου chunk ως context για συνοχή.
- Εντοπισμός υπολειμμάτων αγγλικών & προαιρετικά repair passes.

## 🛡️ Ασφάλεια κλειδιών

- Κλειδιά από περιβάλλον ή `.env` (βλ. `.env.example`).
- `.gitignore` αποκλείει `.env` από commit.

## ❗ Αντιμετώπιση προβλημάτων

- **429 Rate limited**: μειώστε `MAX_WORKERS` ή δοκιμάστε αργότερα.
- **GUI σε Linux**: `sudo apt install python3-tk`.
- **Λείπει κλειδί**: φτιάξτε `.env` ή ορίστε `DEEPSEEK_API_KEY`.

## 📝 Άδεια

MIT (βλ. `LICENSE`).

## 🤝 Συνεισφορές

Δείτε [CONTRIBUTING.el.md](CONTRIBUTING.el.md) ή [CONTRIBUTING.en.md](CONTRIBUTING.en.md).

## 💶 Ενδεικτικό Κόστος

Για διαφάνεια: η μετάφραση του *«Wanden Two»* με **deepseek-chat** κόστισε **περίπου 0,33 €** (33 cents).  
Το πραγματικό κόστος διαφέρει ανάλογα με το μοντέλο, τα tokens και τις ρυθμίσεις.
