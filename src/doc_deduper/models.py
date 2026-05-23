from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from pathlib import Path


@dataclass
class SourceDocument:
    path: Path
    label: str
    index: int


@dataclass
class DocumentSegment:
    source: SourceDocument
    source_index: int
    title: str
    lines: list[str]
    number: str | None = None
    year: int | None = None
    decision_date: date | None = None
    dedupe_key: str = ""
    fingerprint: str = ""
    duplicate_sources: list[str] = field(default_factory=list)

    @property
    def source_ref(self) -> str:
        return f"{self.source.label} #{self.source_index}"

    @property
    def char_count(self) -> int:
        return sum(len(line) for line in self.lines)


@dataclass
class DedupeOptions:
    preset: str = "cassazione"
    start_regex: str | None = None
    similarity_threshold: float = 0.9
    prefer: str = "longest"
    max_paragraph_chars: int = 2800


@dataclass
class MergeResult:
    segments_in: int
    unique_segments: list[DocumentSegment]
    duplicates_removed: int
    duplicate_groups: list[dict[str, object]]
