import re
from typing import List

from pypdf import PdfReader


def read_pdf_text(pdf_path: str) -> str:
    """Read all text from a PDF file."""
    reader = PdfReader(pdf_path)
    pages: List[str] = []

    for page in reader.pages:
        page_text = page.extract_text() or ""
        cleaned = page_text.strip()
        if cleaned:
            pages.append(cleaned)

    return "\n".join(pages)


def split_text_into_chunks(text: str, chunk_size: int = 500) -> List[str]:
    """
    Split text into <=chunk_size chunks while trying to preserve sentence boundaries.

    If a single sentence is longer than chunk_size, it is split on soft punctuation
    first, then by hard character boundary as a fallback.
    """
    if not text or not text.strip():
        return []

    normalized_text = re.sub(r"\s+", " ", text).strip()
    sentences = re.split(r"(?<=[。！？.!?])\s+", normalized_text)

    chunks: List[str] = []
    current_chunk = ""

    def flush_current() -> None:
        nonlocal current_chunk
        if current_chunk:
            chunks.append(current_chunk)
            current_chunk = ""

    def split_oversized_sentence(sentence: str) -> List[str]:
        parts: List[str] = []
        remaining = sentence.strip()

        while len(remaining) > chunk_size:
            split_at = -1
            for delimiter in ["，", "；", "：", ",", ";", ":", " "]:
                pos = remaining.rfind(delimiter, 0, chunk_size)
                split_at = max(split_at, pos)

            if split_at <= 0:
                parts.append(remaining[:chunk_size].strip())
                remaining = remaining[chunk_size:].strip()
            else:
                parts.append(remaining[: split_at + 1].strip())
                remaining = remaining[split_at + 1 :].strip()

        if remaining:
            parts.append(remaining)

        return parts

    for sentence in sentences:
        sentence = sentence.strip()
        if not sentence:
            continue

        sentence_parts = (
            split_oversized_sentence(sentence)
            if len(sentence) > chunk_size
            else [sentence]
        )

        for part in sentence_parts:
            candidate = f"{current_chunk} {part}".strip() if current_chunk else part
            if len(candidate) <= chunk_size:
                current_chunk = candidate
            else:
                flush_current()
                current_chunk = part

    flush_current()
    return chunks


def preview_pdf_chunks(
    pdf_path: str,
    chunk_size: int = 500,
    max_print_chunks: int = 8,
) -> List[str]:
    """Print chunk preview for manual inspection and return all chunks."""
    text = read_pdf_text(pdf_path)
    chunks = split_text_into_chunks(text, chunk_size=chunk_size)

    print(f"PDF: {pdf_path}")
    print(f"Total chars: {len(text)}")
    print(f"Total chunks: {len(chunks)}")
    print("-" * 80)

    for idx, chunk in enumerate(chunks[:max_print_chunks], start=1):
        print(f"[Chunk {idx}] length={len(chunk)}")
        print(chunk)
        print("-" * 80)

    return chunks
