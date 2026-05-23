from __future__ import annotations

from pathlib import Path

from .dedupe import dedupe_segments
from .export_docx import sort_key
from .models import DedupeOptions, MergeResult
from .segment import segment_file


def merge_documents(paths: list[Path], options: DedupeOptions) -> MergeResult:
    segments = []
    for source_index, path in enumerate(paths, 1):
        segments.extend(segment_file(path, source_index, options))
    unique, duplicate_groups = dedupe_segments(segments, options)
    unique.sort(key=sort_key, reverse=True)
    return MergeResult(
        segments_in=len(segments),
        unique_segments=unique,
        duplicates_removed=len(segments) - len(unique),
        duplicate_groups=duplicate_groups,
    )
