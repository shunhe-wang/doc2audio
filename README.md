# doc2audio

Convert legal documents (PDF, DOCX, TXT) to MP3 audio files.
Optimized for briefs, motions, memos, and other legal writing.

---

## Features

- **Smart preprocessing** strips page numbers, headers/footers, Tables of Contents/Authorities, and citation noise before converting — so you're not listening to "one twenty-three F third four fifty-six" on your commute
- **Configurable citation cleanup** — choose aggressive (`strip`), minimal (`light`), or none (`keep`) depending on whether statutory references matter to you
- **Section mode** splits long documents by heading (ARGUMENT, INTRODUCTION, etc.) into separate MP3s for easy navigation
- **Four TTS engines**: Edge TTS (best quality), gTTS (good quality), macOS `say` (offline), pyttsx3 (offline, cross-platform)
- **Long-document handling** — documents over ~120k characters automatically switch to section mode for reliability
- **Cost**: completely free

---

## Setup

### 1. Install Python dependencies

```bash
pip install -r requirements.txt
```

### 2. That's it

No API keys needed. The default engine (gTTS) uses Google's free TTS service. Edge TTS uses Microsoft's free service. Both require an internet connection but no account.

---

## Usage

### Basic — convert a PDF to a single MP3

```bash
python convert.py brief.pdf
```
Output: `brief.mp3` in the same folder as the input file.

### Use Edge TTS (better quality, higher rate limits)

```bash
python convert.py brief.pdf --engine edge
```

### Split into sections (one MP3 per heading)

```bash
python convert.py motion.docx --mode sections
```
Output: `motion_01_INTRODUCTION.mp3`, `motion_02_ARGUMENT.mp3`, etc.

### Keep statutory references intact (light citation cleanup)

```bash
python convert.py brief.pdf --citation-mode light
```
Removes case reporters and *Id.* citations but leaves `42 U.S.C. § 7411(a)(1)` as-is instead of collapsing it to "the statute."

### Save to a specific folder

```bash
python convert.py brief.pdf --output ~/Desktop/audio/
```

### Use macOS offline voice (no internet needed)

```bash
python convert.py brief.pdf --engine macos
```

### Skip preprocessing entirely

```bash
python convert.py notes.txt --no-preprocess
```

---

## All options

```
python convert.py [input file] [options]

Arguments:
  input                   Path to .pdf, .docx, or .txt file

Options:
  --mode   combined       One combined MP3 (default)
           sections       One MP3 per document section

  --engine gtts           Google TTS — good quality, free, needs internet (default)
           edge           Microsoft Edge TTS — best quality, higher rate limits, free
           macos          macOS 'say' command — offline, Mac only
           pyttsx3        pyttsx3 — offline, cross-platform, more robotic

  --citation-mode strip   Replace U.S.C./§ with "the statute"/"section" (default)
                  light   Remove case citations and Id. but leave statutory refs intact
                  keep    Leave all citations exactly as written

  --output [dir]          Output directory (default: same folder as input)
  --no-preprocess         Skip all citation/TOC/header cleanup
  --lang   [code]         Language for gTTS and Edge TTS, e.g. 'en', 'de' (default: en)
                          Edge voices supported: en, de, fr, es, it, pt, ja, zh, ko, nl, ru, ar
```

---

## What preprocessing does

For legal documents, the tool automatically removes or simplifies:

| Removes / Simplifies | Example | Result |
|---|---|---|
| Page numbers | `- 14 -` | removed |
| Court header/footer lines | `Case 1:20-cv-01234 Document 45` | removed |
| Table of Contents | Entire TOC section | removed |
| Table of Authorities | Entire TOA section | removed |
| *Id.* citations | `Id. at 847.` | short pause |
| Reporter citations | `123 F.3d 456` | removed |
| Parenthetical years | `(9th Cir. 2020)` | removed |
| U.S.C. references *(strip mode)* | `42 U.S.C. § 7411(a)(1)` | "the statute" |
| C.F.R. references *(strip mode)* | `40 C.F.R. § 60.1` | "the regulation" |
| Section symbols *(strip mode)* | `§ 4(a)` | "section 4(a)" |
| U.S.C./§ references *(light mode)* | `42 U.S.C. § 7411(a)(1)` | left as-is |

Section headings (INTRODUCTION, ARGUMENT, I., A., etc.) get small pause markers added so the audio flows more naturally.

---

## Tips

- **Long briefs**: use `--mode sections` so you can jump to specific arguments without scrubbing through a 45-minute file. Documents over ~120k characters do this automatically.
- **Rate limits**: for long filings, prefer `--engine edge` over `--engine gtts`. Edge has higher limits and better voice quality. For guaranteed no-limit conversion, use `--engine macos` or `--engine pyttsx3` (offline, no API calls).
- **Statutory arguments**: use `--citation-mode light` to preserve U.S.C./C.F.R. references — useful when the exact statute number is part of the argument
- **Send to phone**: AirDrop the MP3(s) directly, or save to iCloud Drive / Dropbox
- **Word docs**: works best if the DOCX uses proper heading styles rather than manually bolded text

---

## Engine comparison

| Engine | Cost | Quality | Internet | Rate limits |
|---|---|---|---|---|
| Edge TTS (`edge`) | Free | ★★★★★ | Required | High |
| gTTS (`gtts`, default) | Free | ★★★★☆ | Required | Moderate |
| macOS say (`macos`) | Free | ★★☆☆☆ | Not needed | None |
| pyttsx3 (`pyttsx3`) | Free | ★★☆☆☆ | Not needed | None |

---

## Troubleshooting

**"No text could be extracted"** — your PDF may be a scanned image. You'll need to run OCR first (try `ocrmypdf` or Adobe Acrobat).

**gTTS rate limit / network error** — switch to `--engine edge`, which has higher limits. For guaranteed offline conversion, use `--engine macos`.

**Long document stops mid-conversion** — use `--mode sections` or `--engine edge` / `--engine macos`. Very long documents (over ~120k characters) auto-switch to section mode.

**Audio cuts off mid-sentence** — the document may have unusual formatting. Try `--no-preprocess` to compare.

**macOS: output is AIFF instead of MP3** — install `ffmpeg` (`brew install ffmpeg`) and re-run. Without ffmpeg, the macOS engine saves as `.aiff` (which still plays in most apps) and prints a note telling you the actual filename.
