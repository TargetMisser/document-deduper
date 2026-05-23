from pathlib import Path
import unittest

from doc_deduper.dedupe import dedupe_segments
from doc_deduper.models import DedupeOptions, DocumentSegment, SourceDocument
from doc_deduper.text import parse_date, readable_text


def make_segment(source_index: int, title: str, body: str) -> DocumentSegment:
    source = SourceDocument(path=Path(f"source{source_index}.docx"), label=f"source{source_index}.docx", index=source_index)
    segment = DocumentSegment(source=source, source_index=1, title=title, lines=[title, body])
    segment.number = "123"
    segment.year = 2025
    segment.dedupe_key = "2025-123"
    segment.fingerprint = str(source_index)
    return segment


class TextAndDedupeTests(unittest.TestCase):
    def test_readable_text_repairs_split_months(self) -> None:
        self.assertEqual(readable_text("Sentenza 7 m aggio 2026"), "Sentenza 7 maggio 2026")
        self.assertEqual(parse_date("5 m arzo 2026").isoformat(), "2026-03-05")

    def test_metadata_duplicate_keeps_longest(self) -> None:
        short = make_segment(1, "Sentenza 1 gennaio 2025, n. 123", "short")
        long = make_segment(2, "Sentenza 1 gennaio 2025, n. 123", "long text " * 50)
        unique, groups = dedupe_segments([short, long], DedupeOptions(prefer="longest"))
        self.assertEqual(len(unique), 1)
        self.assertEqual(unique[0].source.label, "source2.docx")
        self.assertEqual(len(groups), 1)


if __name__ == "__main__":
    unittest.main()
