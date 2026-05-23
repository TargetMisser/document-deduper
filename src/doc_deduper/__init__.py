"""Document collection merger and deduper."""

from .models import DedupeOptions, DocumentSegment, MergeResult
from .pipeline import merge_documents

__all__ = ["DedupeOptions", "DocumentSegment", "MergeResult", "merge_documents"]
