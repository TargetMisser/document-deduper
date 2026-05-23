from __future__ import annotations

import argparse
import json
from pathlib import Path

from .export_docx import export_google_docs_chunks, export_word, write_manifest
from .models import DedupeOptions
from .pipeline import merge_documents
from .web import run_server


def merge_command(args: argparse.Namespace) -> None:
    options = DedupeOptions(
        preset=args.preset,
        start_regex=args.start_regex,
        similarity_threshold=args.similarity,
        prefer=args.prefer,
        max_paragraph_chars=args.max_paragraph_chars,
    )
    result = merge_documents([Path(path) for path in args.inputs], options)
    export_word(
        Path(args.out),
        result.unique_segments,
        duplicates_removed=result.duplicates_removed,
        max_paragraph_chars=args.max_paragraph_chars,
    )
    if args.manifest:
        write_manifest(Path(args.manifest), result.unique_segments)
    chunk_paths = []
    if args.google_docs_dir:
        chunk_paths = export_google_docs_chunks(
            Path(args.google_docs_dir),
            result.unique_segments,
            duplicates_removed=result.duplicates_removed,
            char_limit=args.google_docs_limit,
        )
    print(
        json.dumps(
            {
                "output": args.out,
                "segments_in": result.segments_in,
                "unique": len(result.unique_segments),
                "duplicates_removed": result.duplicates_removed,
                "google_docs_chunks": [str(path) for path in chunk_paths],
            },
            indent=2,
            ensure_ascii=False,
        )
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="document-deduper")
    sub = parser.add_subparsers(dest="command", required=True)

    merge = sub.add_parser("merge", help="Merge DOCX/PDF files and remove duplicates")
    merge.add_argument("inputs", nargs="+", help="Input .docx/.pdf files")
    merge.add_argument("--out", default="outputs/merged.docx", help="Output .docx path")
    merge.add_argument("--manifest", default=None, help="Optional CSV manifest path")
    merge.add_argument(
        "--preset",
        choices=["cassazione", "custom", "whole-file"],
        default="cassazione",
        help="Segmentation preset",
    )
    merge.add_argument("--start-regex", default=None, help="Custom regex for document starts")
    merge.add_argument("--similarity", type=float, default=0.9, help="Same-number similarity threshold")
    merge.add_argument("--prefer", choices=["longest", "first"], default="longest")
    merge.add_argument("--max-paragraph-chars", type=int, default=2800)
    merge.add_argument("--google-docs-dir", default=None, help="Optional directory for Google Docs chunks")
    merge.add_argument("--google-docs-limit", type=int, default=760000)
    merge.set_defaults(func=merge_command)

    web = sub.add_parser("web", help="Run the local web UI")
    web.add_argument("--host", default="127.0.0.1")
    web.add_argument("--port", type=int, default=8765)
    web.set_defaults(func=lambda args: run_server(args.host, args.port))
    return parser


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
