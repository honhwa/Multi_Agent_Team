from __future__ import annotations

import io
import json
import os
import re
import tempfile
from hashlib import sha256
from pathlib import Path


_DOC_CACHE_VERSION = "pdf-pages-v1"
_DOC_CACHE_DIR = (Path(__file__).resolve().parent / "data" / "document_cache").resolve()


def truncate_text(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    keep = max_chars - 64
    return f"{text[:keep]}\n\n[内容已截断，原始长度 {len(text)} 字符]"


def _score_extracted_text(text: str) -> int:
    compact = re.sub(r"\s+", "", text or "")
    return len(compact)


def _cache_key_for_path(path: Path) -> str:
    stat = path.stat()
    payload = f"{_DOC_CACHE_VERSION}|{path.resolve()}|{stat.st_size}|{stat.st_mtime_ns}"
    return sha256(payload.encode("utf-8")).hexdigest()


def _cache_path_for_pdf(path: Path) -> Path:
    return _DOC_CACHE_DIR / f"{_cache_key_for_path(path)}.json"


def _read_cached_pdf_pages(path: Path) -> list[tuple[int, str]] | None:
    cache_path = _cache_path_for_pdf(path)
    if not cache_path.is_file():
        return None
    try:
        payload = json.loads(cache_path.read_text(encoding="utf-8"))
    except Exception:
        return None
    if payload.get("version") != _DOC_CACHE_VERSION:
        return None
    pages_raw = payload.get("pages")
    if not isinstance(pages_raw, list):
        return None
    pages: list[tuple[int, str]] = []
    for item in pages_raw:
        if not isinstance(item, dict):
            continue
        try:
            page_num = int(item.get("page") or 0)
        except Exception:
            page_num = 0
        body = str(item.get("text") or "")
        if page_num > 0 and body.strip():
            pages.append((page_num, body))
    return pages or None


def _write_cached_pdf_pages(path: Path, pages: list[tuple[int, str]]) -> None:
    try:
        _DOC_CACHE_DIR.mkdir(parents=True, exist_ok=True)
        cache_path = _cache_path_for_pdf(path)
        payload = {
            "version": _DOC_CACHE_VERSION,
            "source_path": str(path.resolve()),
            "pages": [{"page": page_num, "text": body} for page_num, body in pages],
        }
        with tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            dir=str(_DOC_CACHE_DIR),
            delete=False,
            suffix=".tmp",
        ) as fp:
            json.dump(payload, fp, ensure_ascii=False)
            temp_name = fp.name
        os.replace(temp_name, cache_path)
    except Exception:
        try:
            if "temp_name" in locals() and temp_name:
                Path(temp_name).unlink(missing_ok=True)
        except Exception:
            pass


def _append_page_block(chunks: list[str], idx: int, body: str, total: int, limit: int) -> tuple[int, bool]:
    normalized = (body or "").strip()
    if not normalized:
        return total, False
    block = f"\n--- Page {idx} ---\n{normalized}\n"
    chunks.append(block)
    total += len(block)
    return total, total >= limit


def _table_to_lines(table: list[list[object]] | None) -> list[str]:
    if not table:
        return []
    lines: list[str] = []
    for row in table:
        if not row:
            continue
        cells = [re.sub(r"\s+", " ", str(cell or "")).strip() for cell in row]
        if not any(cells):
            continue
        lines.append(" | ".join(cells))
    return lines


def _pdfplumber_page_texts(raw_pdf: bytes) -> list[tuple[int, str]]:
    import pdfplumber  # lazy import

    pages: list[tuple[int, str]] = []
    with pdfplumber.open(io.BytesIO(raw_pdf)) as pdf:
        for idx, page in enumerate(pdf.pages, start=1):
            text = (page.extract_text(layout=True) or "").strip()
            table_lines: list[str] = []
            try:
                for table in page.extract_tables() or []:
                    table_lines.extend(_table_to_lines(table))
            except Exception:
                table_lines = []

            body_parts: list[str] = []
            if text:
                body_parts.append(text)
            if table_lines:
                body_parts.append("[Extracted tables]")
                body_parts.extend(table_lines)
            body = "\n".join(body_parts).strip()
            if body:
                pages.append((idx, body))
    return pages


def _pypdf_page_texts(raw_pdf: bytes) -> list[tuple[int, str]]:
    from pypdf import PdfReader  # lazy import

    reader = PdfReader(io.BytesIO(raw_pdf))
    pages: list[tuple[int, str]] = []
    for idx, page in enumerate(reader.pages, start=1):
        body = (page.extract_text() or "").strip()
        if body:
            pages.append((idx, body))
    return pages


def extract_pdf_page_texts_from_bytes(raw_pdf: bytes) -> list[tuple[int, str]]:
    errors: list[str] = []
    for extractor in (_pdfplumber_page_texts, _pypdf_page_texts):
        try:
            pages = extractor(raw_pdf)
        except Exception as exc:
            errors.append(f"{extractor.__name__}: {exc}")
            continue
        if pages:
            return pages

    if errors:
        raise RuntimeError("; ".join(errors))
    return []


def extract_pdf_page_texts_from_path(path: Path) -> list[tuple[int, str]]:
    cached = _read_cached_pdf_pages(path)
    if cached is not None:
        return cached
    pages = extract_pdf_page_texts_from_bytes(path.read_bytes())
    if pages:
        _write_cached_pdf_pages(path, pages)
    return pages


def _extract_pdf_with_pdfplumber(raw_pdf: bytes, max_chars: int) -> str:
    chunks: list[str] = []
    total = 0
    limit = max(512, int(max_chars))
    for idx, body in _pdfplumber_page_texts(raw_pdf):
        total, reached = _append_page_block(chunks, idx, body, total, limit)
        if reached:
            break
    return truncate_text("".join(chunks).strip(), limit)


def _extract_pdf_with_pypdf(raw_pdf: bytes, max_chars: int) -> str:
    chunks: list[str] = []
    total = 0
    limit = max(512, int(max_chars))
    for idx, body in _pypdf_page_texts(raw_pdf):
        total, reached = _append_page_block(chunks, idx, body, total, limit)
        if reached:
            break
    return truncate_text("".join(chunks).strip(), limit)


def extract_pdf_text_from_bytes(raw_pdf: bytes, max_chars: int) -> str:
    limit = max(512, int(max_chars))
    candidates: list[tuple[int, str]] = []
    errors: list[str] = []

    for extractor in (_extract_pdf_with_pdfplumber, _extract_pdf_with_pypdf):
        try:
            text = extractor(raw_pdf, limit)
        except Exception as exc:
            errors.append(f"{extractor.__name__}: {exc}")
            continue
        if text.strip():
            candidates.append((_score_extracted_text(text), text))

    if candidates:
        candidates.sort(key=lambda item: item[0], reverse=True)
        return candidates[0][1]

    if errors:
        raise RuntimeError("; ".join(errors))
    return ""


def extract_pdf_text_from_path(path: Path, max_chars: int) -> str:
    pages = extract_pdf_page_texts_from_path(path)
    if not pages:
        return extract_pdf_text_from_bytes(path.read_bytes(), max_chars=max_chars)
    chunks: list[str] = []
    total = 0
    limit = max(512, int(max_chars))
    for idx, body in pages:
        total, reached = _append_page_block(chunks, idx, body, total, limit)
        if reached:
            break
    return truncate_text("".join(chunks).strip(), limit)
