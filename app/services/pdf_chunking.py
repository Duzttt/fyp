import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from pypdf import PdfReader


def _normalize_path_arg(path: str) -> str:
    cleaned = str(path).strip()
    if (
        len(cleaned) >= 2
        and cleaned[0] == cleaned[-1]
        and cleaned[0] in {"'", '"'}
    ):
        cleaned = cleaned[1:-1].strip()
    return cleaned


def read_pdf_text(pdf_path: str) -> str:
    """Read all text from a PDF file."""
    pages = read_pdf_pages(pdf_path)
    return "\n".join([page["text"] for page in pages])


def read_pdf_pages(pdf_path: str) -> List[Dict[str, Any]]:
    """Read a PDF and return page-level text records with page number metadata."""
    cleaned_path = _normalize_path_arg(pdf_path)
    pdf_file = Path(cleaned_path)
    if not pdf_file.exists():
        raise FileNotFoundError(f"PDF file not found: {cleaned_path}")

    reader = PdfReader(str(pdf_file))
    pages: List[Dict[str, Any]] = []

    for page_idx, page in enumerate(reader.pages, start=1):
        page_text = page.extract_text() or ""
        cleaned = page_text.strip()
        if cleaned:
            pages.append(
                {
                    "page": page_idx,
                    "text": cleaned,
                }
            )

    return pages


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


def chunk_pdf_with_metadata(
    pdf_path: str,
    chunk_size: int = 500,
    source_name: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Chunk a PDF while preserving source filename and page number metadata."""
    cleaned_path = _normalize_path_arg(pdf_path)
    pdf_file = Path(cleaned_path)
    resolved_source = source_name or pdf_file.name
    page_records = read_pdf_pages(cleaned_path)

    chunk_records: List[Dict[str, Any]] = []
    for page_record in page_records:
        page_num = int(page_record["page"])
        page_text = str(page_record["text"])
        page_chunks = split_text_into_chunks(page_text, chunk_size=chunk_size)

        for chunk in page_chunks:
            chunk_records.append(
                {
                    "text": chunk,
                    "source": resolved_source,
                    "page": page_num,
                }
            )

    return chunk_records


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
