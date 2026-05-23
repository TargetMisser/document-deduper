from __future__ import annotations

from pathlib import Path
from typing import Iterable

from docx import Document
from docx.document import Document as DocxDocument
from docx.oxml.table import CT_Tbl
from docx.oxml.text.paragraph import CT_P
from docx.table import Table
from docx.text.paragraph import Paragraph
from pypdf import PdfReader

from .text import normalize_text


def iter_docx_blocks(parent: DocxDocument | object) -> Iterable[Paragraph | Table]:
    parent_elm = parent.element.body if isinstance(parent, DocxDocument) else parent._tc
    for child in parent_elm.iterchildren():
        if isinstance(child, CT_P):
            yield Paragraph(child, parent)
        elif isinstance(child, CT_Tbl):
            yield Table(child, parent)


def table_lines(table: Table) -> list[str]:
    lines: list[str] = []
    for row in table.rows:
        seen_cells: set[int] = set()
        for cell in row.cells:
            cell_id = id(cell._tc)
            if cell_id in seen_cells:
                continue
            seen_cells.add(cell_id)
            for paragraph in cell.paragraphs:
                text = normalize_text(paragraph.text)
                if text:
                    lines.append(text)
    return lines


def extract_docx(path: Path) -> list[str]:
    doc = Document(path)
    lines: list[str] = []
    for block in iter_docx_blocks(doc):
        if isinstance(block, Paragraph):
            text = normalize_text(block.text)
            if text:
                lines.append(text)
        else:
            lines.extend(table_lines(block))
    return lines


def extract_pdf(path: Path) -> list[str]:
    reader = PdfReader(str(path))
    lines: list[str] = []
    for page in reader.pages:
        text = page.extract_text() or ""
        lines.extend(normalize_text(line) for line in text.splitlines() if normalize_text(line))
    return lines


def extract_lines(path: Path) -> list[str]:
    suffix = path.suffix.lower()
    if suffix == ".docx":
        return extract_docx(path)
    if suffix == ".pdf":
        return extract_pdf(path)
    raise ValueError(f"Unsupported file type: {path}")
