from __future__ import annotations

import re
from pathlib import Path

from .extract import extract_lines
from .models import DedupeOptions, DocumentSegment, SourceDocument
from .text import fingerprint, parse_date, parse_number, readable_text

CASSAZIONE_STARTS = [
    r"^SENT\.\s*CASS\.\s*PENALE$",
    r"^Cassazione\s+penale\s+sez\..*?\bn\.\s*\d+",
    r"^(?:Sentenza|Ordinanza)\s+\d{1,2}\s+.+?20\d{2},\s*n\.\s*\d+",
    r"^Sentenza\s*\|\s*20\d{2}$",
    r"^Cass\.\s*pen\.,\s*Sez\..*?\bn\.\s*\d+",
]

NOISE_PATTERNS = [
    r"^One LEGALE$",
    r"^WOLTERS KLUWER ONE LEGALE$",
    r"Copyright Wolters Kluwer Italia",
    r"^\d{1,2}\s+[A-Za-zàèéìòù]+\s+20\d{2}\s+pag\.\s*\d+",
]


def is_noise(line: str) -> bool:
    return any(re.search(pattern, line, re.I) for pattern in NOISE_PATTERNS)


def start_regex(options: DedupeOptions) -> re.Pattern[str] | None:
    if options.preset == "whole-file":
        return None
    if options.preset == "custom":
        if not options.start_regex:
            raise ValueError("--start-regex is required with --preset custom")
        return re.compile(options.start_regex, re.I)
    patterns = list(CASSAZIONE_STARTS)
    if options.start_regex:
        patterns.append(options.start_regex)
    return re.compile("|".join(f"(?:{pattern})" for pattern in patterns), re.I)


def title_for_chunk(chunk: list[str], fallback: str) -> str:
    for line in chunk[:12]:
        if re.search(r"\bn\.\s*\d+", line, re.I) and (
            re.search(r"Cass|Sentenza|Ordinanza", line, re.I)
        ):
            return readable_text(line)
    for line in chunk[:20]:
        if re.search(r"Cass\.\s*pen\.", line, re.I):
            return readable_text(line)
    return readable_text(chunk[0]) if chunk else fallback


def enrich(segment: DocumentSegment) -> DocumentSegment:
    head = "\n".join([segment.title, *segment.lines[:40]])
    segment.number = parse_number(head)
    segment.decision_date = parse_date(segment.title) or parse_date(head)
    segment.year = segment.decision_date.year if segment.decision_date else None
    if segment.year is None:
        m = re.search(r"\b(20\d{2})\b", head)
        segment.year = int(m.group(1)) if m else None
    if segment.number and segment.year:
        segment.dedupe_key = f"{segment.year}-{segment.number}"
    elif segment.number:
        segment.dedupe_key = f"n-{segment.number}"
    else:
        segment.dedupe_key = f"fp-{fingerprint(segment.lines)}"
    segment.fingerprint = fingerprint(segment.lines)
    return segment


def segment_lines(source: SourceDocument, lines: list[str], options: DedupeOptions) -> list[DocumentSegment]:
    lines = [readable_text(line) for line in lines if line and not is_noise(line)]
    regex = start_regex(options)
    if regex is None:
        return [
            enrich(
                DocumentSegment(
                    source=source,
                    source_index=1,
                    title=source.label,
                    lines=lines,
                )
            )
        ]

    starts = [idx for idx, line in enumerate(lines) if regex.search(line)]
    if not starts:
        return [
            enrich(
                DocumentSegment(
                    source=source,
                    source_index=1,
                    title=source.label,
                    lines=lines,
                )
            )
        ]

    segments: list[DocumentSegment] = []
    for ordinal, start in enumerate(starts, 1):
        end = starts[ordinal] if ordinal < len(starts) else len(lines)
        chunk = lines[start:end]
        if not chunk:
            continue
        segments.append(
            enrich(
                DocumentSegment(
                    source=source,
                    source_index=ordinal,
                    title=title_for_chunk(chunk, f"{source.label} #{ordinal}"),
                    lines=chunk,
                )
            )
        )
    return segments


def segment_file(path: Path, source_index: int, options: DedupeOptions) -> list[DocumentSegment]:
    source = SourceDocument(path=path, label=path.name, index=source_index)
    return segment_lines(source, extract_lines(path), options)
