#!/usr/bin/env python3
"""
doc2audio - Document to Audio Converter
Converts PDF, DOCX, and TXT files to MP3 audio files.
Optimized for legal documents (briefs, motions, memos).
"""

import argparse
import os
import random
import re
import sys
import tempfile
import time
from pathlib import Path


# Default Edge TTS voices per language code
EDGE_DEFAULT_VOICES = {
    "en": "en-US-AriaNeural",
    "de": "de-DE-KatjaNeural",
    "fr": "fr-FR-DeniseNeural",
    "es": "es-ES-ElviraNeural",
    "it": "it-IT-ElsaNeural",
    "pt": "pt-BR-FranciscaNeural",
    "ja": "ja-JP-NanamiNeural",
    "zh": "zh-CN-XiaoxiaoNeural",
    "ko": "ko-KR-SunHiNeural",
    "nl": "nl-NL-ColetteNeural",
    "ru": "ru-RU-SvetlanaNeural",
    "ar": "ar-SA-ZariyahNeural",
}


# ─── TEXT EXTRACTION ──────────────────────────────────────────────────────────

def extract_pdf(path: str) -> str:
    try:
        import pdfplumber
    except ImportError:
        sys.exit("Missing dependency: pip install pdfplumber")

    pages = []
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                pages.append(text)
    return "\n\n".join(pages)


def extract_docx(path: str) -> str:
    try:
        from docx import Document
    except ImportError:
        sys.exit("Missing dependency: pip install python-docx")

    doc = Document(path)
    paragraphs = []
    for para in doc.paragraphs:
        if para.text.strip():
            paragraphs.append(para.text.strip())
    return "\n\n".join(paragraphs)


def extract_txt(path: str) -> str:
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        return f.read()


def extract_text(path: str) -> str:
    ext = Path(path).suffix.lower()
    if ext == ".pdf":
        print("  Extracting text from PDF...")
        return extract_pdf(path)
    elif ext == ".docx":
        print("  Extracting text from DOCX...")
        return extract_docx(path)
    elif ext == ".txt":
        print("  Extracting text from TXT...")
        return extract_txt(path)
    else:
        sys.exit(f"Unsupported file type: {ext}. Supported: .pdf, .docx, .txt")


# ─── TEXT PREPROCESSING ───────────────────────────────────────────────────────

# Heading patterns common in legal docs
HEADING_PATTERNS = [
    re.compile(r'^(INTRODUCTION|BACKGROUND|ARGUMENT|CONCLUSION|SUMMARY OF ARGUMENT|STATEMENT OF FACTS?|STATEMENT OF THE CASE|STANDARD OF REVIEW|PRELIMINARY STATEMENT)\s*$', re.MULTILINE | re.IGNORECASE),
    re.compile(r'^(?:I{1,3}V?|VI{0,3}|IX|X{1,3})\.\s+.+$', re.MULTILINE),   # Roman numeral headings - full line
    re.compile(r'^[A-Z]\.\s+.+$', re.MULTILINE),                              # Letter subheadings - full line
]

# Citation patterns — strip mode (aggressive, default): replaces everything
CITATION_PATTERNS = [
    # Id. citations (case-insensitive to catch "id." and "Id.")
    (re.compile(r'\bId\.\s+at\s+\d+[\d\-–,\s]*\.?', re.IGNORECASE), ". "),
    (re.compile(r'\bid\.', re.IGNORECASE), ". "),
    # Supra/infra
    (re.compile(r'\bsupra\s+note\s+\d+'), ""),
    (re.compile(r'\binfra\s+note\s+\d+'), ""),
    # Reporter citations: 123 F.3d 456, 123 U.S. 456, etc.
    (re.compile(r'\d+\s+(?:U\.S\.|F\.\d+[a-z]*|F\s+Supp\.?\s*\d*[a-z]*|S\.?\s*Ct\.|L\.?\s*Ed\.?\s*\d*[a-z]*|A\.\d+[a-z]*|P\.\d+[a-z]*|N\.E\.\d+[a-z]*|So\.\s*\d+[a-z]*|Cal\.(?:\s*\d+[a-z]*)?)\s+\d+(?:,\s*\d+)*'), ""),
    # Parenthetical years in citations: (9th Cir. 2020), (2021)
    (re.compile(r'\(\w+\.?\s+Cir\.\s+\d{4}\)'), ""),
    (re.compile(r'\(\d{4}\)'), ""),
    # Footnote numbers: superscript-style like ^1 or inline [1]
    (re.compile(r'\[\d+\]'), ""),
    (re.compile(r'\^\d+'), ""),
    # U.S.C., C.F.R. strings — consume trailing subsection parens like (a)(1)
    (re.compile(r'\d+\s+U\.S\.C\.?\s+§+\s*[\d\w\-\.]+(?:\([^)]+\))*'), "the statute"),
    (re.compile(r'\d+\s+C\.F\.R\.?\s+§+\s*[\d\w\-\.]+(?:\([^)]+\))*'), "the regulation"),
    # Section symbol — consume trailing subsection parens
    (re.compile(r'§+\s*\d[\d\w\-\.]*(?:\([^)]+\))*'), "section"),
]

# Citation patterns — light mode: removes unlistenable noise but keeps statutory references intact
CITATION_PATTERNS_LIGHT = [
    # Id. citations
    (re.compile(r'\bId\.\s+at\s+\d+[\d\-–,\s]*\.?', re.IGNORECASE), ". "),
    (re.compile(r'\bid\.', re.IGNORECASE), ". "),
    # Supra/infra
    (re.compile(r'\bsupra\s+note\s+\d+'), ""),
    (re.compile(r'\binfra\s+note\s+\d+'), ""),
    # Reporter citations (pure noise when spoken aloud)
    (re.compile(r'\d+\s+(?:U\.S\.|F\.\d+[a-z]*|F\s+Supp\.?\s*\d*[a-z]*|S\.?\s*Ct\.|L\.?\s*Ed\.?\s*\d*[a-z]*|A\.\d+[a-z]*|P\.\d+[a-z]*|N\.E\.\d+[a-z]*|So\.\s*\d+[a-z]*|Cal\.(?:\s*\d+[a-z]*)?)\s+\d+(?:,\s*\d+)*'), ""),
    # Parenthetical years
    (re.compile(r'\(\w+\.?\s+Cir\.\s+\d{4}\)'), ""),
    (re.compile(r'\(\d{4}\)'), ""),
    # Footnote markers
    (re.compile(r'\[\d+\]'), ""),
    (re.compile(r'\^\d+'), ""),
    # Section symbol → "section" but leave the number/subsection intact
    (re.compile(r'§+\s*'), "section "),
]

# TOC/TOA section markers
TOC_TOA_PATTERNS = [
    re.compile(r'TABLE OF CONTENTS.*?(?=\n[A-Z]{4}|\Z)', re.DOTALL | re.IGNORECASE),
    re.compile(r'TABLE OF AUTHORITIES.*?(?=\n[A-Z]{4}|\Z)', re.DOTALL | re.IGNORECASE),
    re.compile(r'INDEX OF AUTHORITIES.*?(?=\n[A-Z]{4}|\Z)', re.DOTALL | re.IGNORECASE),
]

# Page number patterns
PAGE_NUMBER_PATTERNS = [
    re.compile(r'^\s*-?\s*\d+\s*-?\s*$', re.MULTILINE),           # standalone page numbers
    re.compile(r'^\s*Page\s+\d+\s+of\s+\d+\s*$', re.MULTILINE | re.IGNORECASE),
    re.compile(r'^\s*\d+\s*\n', re.MULTILINE),                     # line that's just a number
]

# Header/footer patterns (lines that repeat or look like running headers)
HEADER_FOOTER_PATTERNS = [
    re.compile(r'^Case\s+\d+:\d+[-\w]+\s+Document\s+\d+.*$', re.MULTILINE | re.IGNORECASE),
    re.compile(r'^USCA\d*\s+Case.*$', re.MULTILINE | re.IGNORECASE),
    re.compile(r'^Filed\s+\d{2}/\d{2}/\d{4}.*$', re.MULTILINE | re.IGNORECASE),
]


def remove_toc_toa(text: str) -> str:
    for pattern in TOC_TOA_PATTERNS:
        text = pattern.sub("\n", text)
    return text


def remove_page_numbers(text: str) -> str:
    for pattern in PAGE_NUMBER_PATTERNS:
        text = pattern.sub("\n", text)
    return text


def remove_headers_footers(text: str) -> str:
    for pattern in HEADER_FOOTER_PATTERNS:
        text = pattern.sub("", text)
    return text


def simplify_citations(text: str, mode: str = "strip") -> str:
    if mode == "keep":
        return text
    patterns = CITATION_PATTERNS_LIGHT if mode == "light" else CITATION_PATTERNS
    for pattern, replacement in patterns:
        text = pattern.sub(replacement, text)
    return text


def add_pause_markers(text: str) -> str:
    """Insert pause cues at section headings so TTS reads them more naturally."""
    for pattern in HEADING_PATTERNS:
        text = pattern.sub(lambda m: "\n\n... " + m.group(0).strip() + " ...\n\n", text)
    return text


def clean_whitespace(text: str) -> str:
    # Collapse 3+ newlines to 2
    text = re.sub(r'\n{3,}', '\n\n', text)
    # Remove lines that are just punctuation or symbols
    text = re.sub(r'^\s*[*\-_=]{3,}\s*$', '', text, flags=re.MULTILINE)
    # Collapse multiple spaces
    text = re.sub(r'  +', ' ', text)
    return text.strip()


def preprocess(text: str, citation_mode: str = "strip") -> str:
    print(f"  Preprocessing text (citation mode: {citation_mode})...")
    text = remove_toc_toa(text)
    text = remove_page_numbers(text)
    text = remove_headers_footers(text)
    text = simplify_citations(text, mode=citation_mode)
    text = add_pause_markers(text)
    text = clean_whitespace(text)
    return text


# ─── SECTION SPLITTING ────────────────────────────────────────────────────────

def split_into_sections(text: str) -> list[tuple[str, str]]:
    """
    Split text into (title, content) sections at major headings.
    Returns list of (section_title, section_text) tuples.
    """
    # Find major section breaks
    section_pattern = re.compile(
        r'^((?:INTRODUCTION|BACKGROUND|ARGUMENT|CONCLUSION|SUMMARY OF ARGUMENT|'
        r'STATEMENT OF FACTS?|STATEMENT OF THE CASE|STANDARD OF REVIEW|'
        r'PRELIMINARY STATEMENT|(?:I{1,3}V?|VI{0,3}|IX|X{1,3})\.\s+[A-Z][^\n]+))\s*$',
        re.MULTILINE
    )

    splits = list(section_pattern.finditer(text))

    if not splits:
        return [("Document", text)]

    sections = []
    for i, match in enumerate(splits):
        title = match.group(1).strip()
        start = match.end()
        end = splits[i + 1].start() if i + 1 < len(splits) else len(text)
        content = text[start:end].strip()
        if content:
            sections.append((title, content))

    # Prepend any text before first heading as "Preamble"
    preamble = text[:splits[0].start()].strip()
    if preamble:
        sections.insert(0, ("Preamble", preamble))

    return sections if sections else [("Document", text)]


# ─── CHUNKING FOR TTS ─────────────────────────────────────────────────────────

def chunk_text(text: str, max_chars: int = 4500) -> list[str]:
    """Split text into chunks suitable for TTS API (gTTS limit ~5000 chars)."""
    chunks = []
    sentences = re.split(r'(?<=[.!?])\s+', text)
    current = ""
    for sentence in sentences:
        if len(current) + len(sentence) + 1 <= max_chars:
            current += (" " if current else "") + sentence
        else:
            if current:
                chunks.append(current)
                current = ""  # reset before handling next sentence
            if len(sentence) > max_chars:
                # Split on comma/semicolon/colon boundaries
                parts = re.split(r'(?<=,|;|:)\s+', sentence)
                sub = ""
                for part in parts:
                    if len(sub) + len(part) + 1 <= max_chars:
                        sub += (" " if sub else "") + part
                    else:
                        if sub:
                            chunks.append(sub)
                        sub = part
                if sub:
                    chunks.append(sub)
            else:
                current = sentence
    if current:
        chunks.append(current)
    return chunks


# ─── TTS ENGINES ──────────────────────────────────────────────────────────────

def tts_gtts(text: str, output_path: str, lang: str = "en") -> str | None:
    """Google TTS - free, requires internet, good quality."""
    try:
        from gtts import gTTS
        from tqdm import tqdm
        import io
        chunks = chunk_text(text)
        audio_segments = []

        for i, chunk in enumerate(tqdm(chunks, desc="  Converting", unit="chunk", ncols=60)):
            if not chunk.strip():
                continue

            # Retry with exponential backoff on rate-limit errors
            for attempt in range(3):
                try:
                    tts = gTTS(text=chunk, lang=lang, slow=False)
                    buf = io.BytesIO()
                    tts.write_to_fp(buf)
                    buf.seek(0)
                    audio_segments.append(buf.read())
                    break
                except Exception as e:
                    if attempt < 2:
                        wait = (2 ** attempt) * 5 + random.uniform(0, 2)
                        tqdm.write(f"  API error ({e}), retrying in {wait:.0f}s...")
                        time.sleep(wait)
                    else:
                        raise

            # Longer delay between chunks to stay under rate limit
            if i < len(chunks) - 1:
                time.sleep(1.0)

        # Concatenate raw MP3 data
        with open(output_path, "wb") as f:
            for segment in audio_segments:
                f.write(segment)
        return output_path

    except Exception as e:
        print(f"  gTTS failed: {e}")
        return None


def tts_macos(text: str, output_path: str, voice: str = "Samantha") -> str | None:
    """macOS say command - fully offline, robotic but functional."""
    import subprocess
    import shutil
    if not shutil.which("say"):
        return None
    try:
        # macOS say produces AIFF; convert to MP3 if ffmpeg available
        with tempfile.NamedTemporaryFile(suffix=".aiff", delete=False) as tmp:
            tmp_path = tmp.name

        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False, mode="w", encoding="utf-8") as txt_tmp:
            txt_tmp.write(text)
            txt_path = txt_tmp.name

        result = subprocess.run(
            ["say", "-v", voice, "-o", tmp_path, "-f", txt_path],
            capture_output=True, timeout=300
        )
        os.unlink(txt_path)
        if result.returncode != 0:
            return None

        if shutil.which("ffmpeg"):
            result = subprocess.run(
                ["ffmpeg", "-y", "-i", tmp_path, output_path],
                capture_output=True,
                check=True,
            )
            final_path = output_path
        else:
            # No ffmpeg: save as AIFF with correct extension rather than lying
            final_path = str(Path(output_path).with_suffix(".aiff"))
            shutil.copy(tmp_path, final_path)
            print(f"  Note: ffmpeg not found. Saved as AIFF (not MP3): {final_path}")
            print(f"  Install ffmpeg to get MP3: brew install ffmpeg")

        os.unlink(tmp_path)
        return final_path
    except Exception as e:
        print(f"  macOS say failed: {e}")
        return None


def tts_edge(text: str, output_path: str, lang: str = "en") -> str | None:
    """Microsoft Edge TTS - free, requires internet, excellent quality, high rate limits."""
    try:
        import asyncio
        import edge_tts
        from tqdm import tqdm
        import io

        voice = EDGE_DEFAULT_VOICES.get(lang, EDGE_DEFAULT_VOICES["en"])
        chunks = chunk_text(text)
        audio_segments = []

        async def _speak_chunk(chunk: str) -> bytes:
            communicate = edge_tts.Communicate(chunk, voice)
            buf = io.BytesIO()
            async for item in communicate.stream():
                if item["type"] == "audio":
                    buf.write(item["data"])
            buf.seek(0)
            return buf.read()

        async def _speak_all():
            for chunk in tqdm(chunks, desc="  Converting", unit="chunk", ncols=60):
                if chunk.strip():
                    audio_segments.append(await _speak_chunk(chunk))

        asyncio.run(_speak_all())

        with open(output_path, "wb") as f:
            for segment in audio_segments:
                f.write(segment)
        return output_path

    except ImportError:
        print("  Missing dependency: pip install edge-tts")
        return None
    except Exception as e:
        print(f"  edge-tts failed: {e}")
        return None


def tts_pyttsx3(text: str, output_path: str) -> str | None:
    """pyttsx3 - offline, uses system voices."""
    try:
        import pyttsx3
        engine = pyttsx3.init()
        engine.setProperty("rate", 175)
        engine.save_to_file(text, output_path)
        engine.runAndWait()
        return output_path
    except Exception as e:
        print(f"  pyttsx3 failed: {e}")
        return None


def convert_section_to_audio(title: str, text: str, output_path: str, engine: str, lang: str = "en") -> str | None:
    """Convert a section of text to an audio file. Returns actual output path or None on failure."""
    full_text = f"{title}. {text}" if title != "Document" else text

    print(f"  Converting: {title} ({len(full_text):,} chars)...")

    if engine == "gtts":
        result = tts_gtts(full_text, output_path, lang=lang)
        if not result:
            print("  Falling back to pyttsx3...")
            result = tts_pyttsx3(full_text, output_path)
    elif engine == "edge":
        result = tts_edge(full_text, output_path, lang=lang)
        if not result:
            print("  Falling back to gtts...")
            result = tts_gtts(full_text, output_path, lang=lang)
    elif engine == "macos":
        result = tts_macos(full_text, output_path)
        if not result:
            print("  Falling back to gtts...")
            result = tts_gtts(full_text, output_path, lang=lang)
    elif engine == "pyttsx3":
        result = tts_pyttsx3(full_text, output_path)
    else:
        result = tts_gtts(full_text, output_path, lang=lang)

    return result


# ─── MAIN ─────────────────────────────────────────────────────────────────────

def estimate_cost(text: str):
    """Print cost/time estimate."""
    chars = len(text)
    words = len(text.split())
    # ~150 words per minute for TTS
    minutes = words / 150
    print(f"\n  Document stats:")
    print(f"    Characters: {chars:,}")
    print(f"    Words:      {words:,}")
    print(f"    Est. audio: ~{minutes:.0f} minutes")
    print(f"    Cost:       Free (gTTS / offline)")


def main():
    parser = argparse.ArgumentParser(
        description="Convert PDF/DOCX/TXT documents to MP3 audio files.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python convert.py brief.pdf
  python convert.py motion.docx --mode sections
  python convert.py document.txt --engine macos --output ~/Desktop/
  python convert.py brief.pdf --no-preprocess

Engines:
  gtts     Google TTS (default) — requires internet, good quality, free
  edge     Microsoft Edge TTS   — requires internet, best quality, high rate limits, free
  macos    macOS 'say' command  — offline, needs macOS, requires ffmpeg for MP3
  pyttsx3  pyttsx3 library      — offline, cross-platform, robotic
        """
    )
    parser.add_argument("input", help="Input file (.pdf, .docx, .txt)")
    parser.add_argument(
        "--mode",
        choices=["combined", "sections"],
        default="combined",
        help="Output mode: 'combined' (one MP3) or 'sections' (one MP3 per section). Default: combined"
    )
    parser.add_argument(
        "--engine",
        choices=["gtts", "edge", "macos", "pyttsx3"],
        default="gtts",
        help="TTS engine to use. Default: gtts"
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Output directory (default: same as input file)"
    )
    parser.add_argument(
        "--no-preprocess",
        action="store_true",
        help="Skip legal text preprocessing (citations, TOC removal, etc.)"
    )
    parser.add_argument(
        "--citation-mode",
        choices=["keep", "light", "strip"],
        default="strip",
        dest="citation_mode",
        help=(
            "How aggressively to clean up citations. "
            "strip (default): replace U.S.C./C.F.R./§ with 'the statute'/'section'. "
            "light: remove case reporters and Id. but leave statutory references intact. "
            "keep: leave all citations exactly as they appear."
        )
    )
    parser.add_argument(
        "--lang",
        default="en",
        help="Language code for gTTS and edge-tts (default: en). Edge voices: de, fr, es, it, pt, ja, zh, ko, nl, ru, ar"
    )

    args = parser.parse_args()

    # Validate input
    if not os.path.exists(args.input):
        sys.exit(f"File not found: {args.input}")

    input_path = Path(args.input).resolve()
    stem = input_path.stem

    # Output directory
    if args.output:
        out_dir = Path(args.output)
        out_dir.mkdir(parents=True, exist_ok=True)
    else:
        out_dir = input_path.parent

    print(f"\n{'='*55}")
    print(f"  doc2audio - Document to Audio Converter")
    print(f"{'='*55}")
    print(f"  Input:  {input_path.name}")
    print(f"  Mode:   {args.mode}")
    print(f"  Engine: {args.engine}")
    print(f"  Output: {out_dir}/")

    # Extract
    raw_text = extract_text(str(input_path))

    if not raw_text.strip():
        sys.exit("No text could be extracted from the document.")

    # Preprocess
    if args.no_preprocess:
        print("  Skipping preprocessing (--no-preprocess)")
        processed = raw_text
    else:
        processed = preprocess(raw_text, citation_mode=args.citation_mode)

    estimate_cost(processed)

    # Auto-adjust for long documents
    char_count = len(processed)
    if char_count > 120_000 and args.mode == "combined":
        print(f"  Long document ({char_count:,} chars); switching to section mode for reliability.")
        args.mode = "sections"
    if char_count > 200_000 and args.engine == "gtts":
        print(f"  Very long document — gTTS may throttle. Consider --engine edge or --engine macos.")

    # Convert
    print(f"\n  Starting conversion...")

    if args.mode == "combined":
        output_file = out_dir / f"{stem}.mp3"
        actual_path = convert_section_to_audio("Document", processed, str(output_file), args.engine, lang=args.lang)
        if actual_path:
            size_mb = os.path.getsize(actual_path) / 1024 / 1024
            print(f"\n  ✓ Done! Output: {actual_path} ({size_mb:.1f} MB)")
        else:
            sys.exit("  ✗ Conversion failed.")

    elif args.mode == "sections":
        from tqdm import tqdm
        sections = split_into_sections(processed)
        print(f"  Found {len(sections)} section(s)")
        output_files = []

        for i, (title, content) in enumerate(tqdm(sections, desc="  Sections", unit="section", ncols=60), 1):
            safe_title = re.sub(r'[^\w\s-]', '', title)[:40].strip().replace(' ', '_')
            filename = f"{stem}_{i:02d}_{safe_title}.mp3"
            output_file = out_dir / filename
            actual_path = convert_section_to_audio(title, content, str(output_file), args.engine, lang=args.lang)
            if actual_path:
                output_files.append(Path(actual_path))
            else:
                tqdm.write(f"  ✗ Failed to convert section: {title}")

        print(f"\n  ✓ Done! {len(output_files)} file(s) saved to {out_dir}/")
        for f in output_files:
            size_kb = os.path.getsize(f) / 1024
            print(f"    {f.name} ({size_kb:.0f} KB)")

    print()


if __name__ == "__main__":
    main()
