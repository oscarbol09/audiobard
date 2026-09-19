# PDF2Bard Companion Guide

AudioBard natively ingests clean **EPUB** and **TXT** files. If your manuscript or public domain book is in **PDF format**, raw text extraction usually results in mangled audio due to layout artifacts.

For this reason, we created [**PDF2Bard (`oscarbol09/pdf2bard`)**](https://github.com/oscarbol09/pdf2bard) — a dedicated, rule-based PDF pre-processor built specifically for audiobook TTS pipelines.

---

## The Problem with Raw PDF Text Extraction

When traditional tools extract text from a PDF:
- **Visual Line Breaks:** Sentences are split mid-clause at margin boundaries, creating unnatural pauses in TTS speech.
- **Marginal Hyphenation:** Words like `dis- / cover` are read as two separate broken words ("dis" ... "cover").
- **Running Headers & Footers:** Page numbers and chapter titles printed on every page are read aloud by the narrator.
- **Damaged Dialog Marks:** Guillemets and em-dashes get mangled, confusing the character attribution engine.

---

## What PDF2Bard Solves

1. **Smart Paragraph Reflow:** Distinguishes genuine paragraph/dialog breaks from soft visual wraps.
2. **Automatic De-Hyphenation:** Seamlessly welds hyphenated words across line boundaries without breaking compound words like "well-known".
3. **Header & Footer Stripping:** Detects repetitive running titles and page counters and eliminates them.
4. **Dialogue Punctuation Normalization:** Standardizes quotes (`“ ”`, `« »`, `—`) so AudioBard can accurately extract characters and detect speaker turns.

---

## Quick Usage

Visit the repository: [**oscarbol09/pdf2bard**](https://github.com/oscarbol09/pdf2bard)

```bash
# Clone & install PDF2Bard
git clone https://github.com/oscarbol09/pdf2bard.git
cd pdf2bard
pip install -e .

# Convert PDF to clean EPUB
pdf2bard convert novel.pdf --output novel.epub

# Ingest directly into AudioBard
audiobard generate novel.epub -o audiobook.mp3
```

