"""Section-aware extraction of the supplied text-based policy manual."""

from dataclasses import dataclass
from hashlib import sha256
from io import BytesIO
from pathlib import Path
import re

from pypdf import PdfReader
from pypdf.errors import PdfReadError

PIPELINE_ID = "layout-sections-3000-overlap300"
MAX_CHARS = 3000
OVERLAP = 300
HEADING = re.compile(r"^(\d+(?:\.\d+)*)(?:\.)?\s+([^\d].+)$")


class PolicyError(RuntimeError):
    """A policy processing failure safe to show without credentials or content."""


@dataclass(frozen=True)
class PolicyChunk:
    chunk_index: int
    section: str
    section_title: str
    page_start: int
    page_end: int
    content: str


def read_policy(path: Path) -> bytes:
    try:
        if path.suffix.lower() != ".pdf" or path.stat().st_size > 20_000_000:
            raise PolicyError("Provide a policy PDF smaller than 20 MB.")
        return path.read_bytes()
    except OSError:
        raise PolicyError("Cannot read the policy PDF.") from None


def document_hash(content: bytes) -> str:
    return sha256(content).hexdigest()


def extract_chunks(content: bytes) -> list[PolicyChunk]:
    sections = []
    current = None
    parents = {}
    try:
        reader = PdfReader(BytesIO(content), strict=True)
        if reader.is_encrypted:
            raise PolicyError("Encrypted policy PDFs are not supported.")
        for page_number, page in enumerate(reader.pages, start=1):
            for raw_line in (page.extract_text(extraction_mode="layout") or "").splitlines():
                line = raw_line.strip()
                normalized_line = re.sub(r"\s+", " ", line)
                if not line or re.match(r"^P\u00e1gina\s+\d+$", line):
                    continue
                if "Manual de Pol\u00edticas e Procedimentos" in normalized_line:
                    continue
                heading = HEADING.match(raw_line)
                if heading:
                    section, title = heading.groups()
                    title = f"{section} {re.sub(r'\s+', ' ', title.strip())}"
                    if "." not in section:
                        parents[section] = title
                    current = {"section": section, "title": title, "parent": parents.get(section.split(".")[0], ""), "lines": []}
                    sections.append(current)
                elif current is not None:
                    table_line = re.sub(r"[ \t]{4,}", " | ", line)
                    current["lines"].append((page_number, re.sub(r"[ \t]+", " ", table_line)))
    except (PdfReadError, ValueError, TypeError, KeyError):
        raise PolicyError("Cannot extract readable sections from the policy PDF.") from None

    chunks = []
    for section in sections:
        if not section["lines"]:
            continue
        prefix = section["title"] + "\n"
        if section["parent"] and section["parent"] != section["title"]:
            prefix = section["parent"] + "\n" + prefix
        body = "\n".join(line for _, line in section["lines"])
        spans, offset = [], 0
        for page, line in section["lines"]:
            spans.append((offset, offset + len(line), page))
            offset += len(line) + 1
        start = 0
        capacity = MAX_CHARS - len(prefix)
        if capacity <= OVERLAP:
            raise PolicyError("A policy section heading is too long.")
        while start < len(body):
            end = min(start + capacity, len(body))
            if end < len(body):
                boundary = body.rfind("\n", start + capacity // 2, end)
                if boundary > start:
                    end = boundary
            pages = [page for left, right, page in spans if left < end and right > start]
            chunks.append(PolicyChunk(len(chunks), section["section"], section["title"], min(pages), max(pages), prefix + body[start:end]))
            if end == len(body):
                break
            start = max(start + 1, end - OVERLAP)
    if not chunks:
        raise PolicyError("The PDF has no readable numbered policy sections; OCR is not implemented.")
    return chunks
