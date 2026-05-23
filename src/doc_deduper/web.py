from __future__ import annotations

import html
import io
import shutil
import tempfile
import zipfile
from email import policy
from email.parser import BytesParser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import quote

from .export_docx import export_google_docs_chunks, export_word, write_manifest
from .models import DedupeOptions
from .pipeline import merge_documents


INDEX_HTML = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Document Deduper</title>
  <style>
    :root { color-scheme: light; font-family: Arial, sans-serif; }
    body { margin: 0; background: #f5f7f9; color: #182026; }
    main { max-width: 860px; margin: 0 auto; padding: 32px 20px 48px; }
    h1 { margin: 0 0 8px; font-size: 28px; }
    p { line-height: 1.45; }
    form { background: #fff; border: 1px solid #d8e0e8; border-radius: 8px; padding: 20px; }
    label { display: block; font-weight: 700; margin: 18px 0 6px; }
    input, select { width: 100%; box-sizing: border-box; font: inherit; padding: 9px; border: 1px solid #b8c4cf; border-radius: 6px; }
    input[type="checkbox"] { width: auto; margin-right: 8px; }
    .row { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; }
    .check { display: flex; align-items: center; margin-top: 18px; font-weight: 700; }
    button { margin-top: 22px; border: 0; border-radius: 6px; background: #0b5cab; color: #fff; padding: 11px 16px; font: inherit; font-weight: 700; cursor: pointer; }
    small { color: #52616f; display: block; margin-top: 4px; }
  </style>
</head>
<body>
  <main>
    <h1>Document Deduper</h1>
    <p>Upload DOCX/PDF files, remove duplicates, and download a Word file with a clickable summary.</p>
    <form method="post" action="/merge" enctype="multipart/form-data">
      <label for="files">Files</label>
      <input id="files" type="file" name="files" accept=".docx,.pdf" multiple required>
      <small>PDFs must contain selectable text.</small>

      <div class="row">
        <div>
          <label for="preset">Preset</label>
          <select id="preset" name="preset">
            <option value="cassazione">Cassazione/legal exports</option>
            <option value="whole-file">One record per file</option>
            <option value="custom">Custom start regex</option>
          </select>
        </div>
        <div>
          <label for="prefer">When duplicates differ</label>
          <select id="prefer" name="prefer">
            <option value="longest">Keep longest text</option>
            <option value="first">Keep first uploaded</option>
          </select>
        </div>
      </div>

      <label for="start_regex">Custom start regex</label>
      <input id="start_regex" name="start_regex" placeholder="^Report\\s+\\d{4}-\\d{2}-\\d{2}">

      <div class="row">
        <div>
          <label for="similarity">Similarity threshold</label>
          <input id="similarity" name="similarity" type="number" min="0.5" max="1" step="0.01" value="0.90">
        </div>
        <div>
          <label for="chunk_limit">Google Docs chunk limit</label>
          <input id="chunk_limit" name="chunk_limit" type="number" min="100000" max="1000000" step="10000" value="760000">
        </div>
      </div>

      <label class="check"><input type="checkbox" name="google_chunks" value="1"> Include Google Docs chunks</label>

      <button type="submit">Merge and download ZIP</button>
    </form>
  </main>
</body>
</html>
"""


def safe_name(filename: str) -> str:
    cleaned = "".join(ch if ch.isalnum() or ch in "._- " else "_" for ch in filename).strip()
    return cleaned or "upload"


def parse_form(handler: BaseHTTPRequestHandler) -> tuple[dict[str, str], list[tuple[str, bytes]]]:
    content_type = handler.headers.get("Content-Type", "")
    length = int(handler.headers.get("Content-Length", "0"))
    body = handler.rfile.read(length)
    message = BytesParser(policy=policy.default).parsebytes(
        f"Content-Type: {content_type}\r\nMIME-Version: 1.0\r\n\r\n".encode() + body
    )
    fields: dict[str, str] = {}
    files: list[tuple[str, bytes]] = []
    for part in message.iter_parts():
        disposition = part.get("Content-Disposition", "")
        name = part.get_param("name", header="content-disposition")
        filename = part.get_filename()
        payload = part.get_payload(decode=True) or b""
        if filename:
            files.append((safe_name(filename), payload))
        elif name:
            fields[name] = payload.decode(part.get_content_charset() or "utf-8", errors="replace")
    return fields, files


def build_zip(fields: dict[str, str], files: list[tuple[str, bytes]]) -> bytes:
    if not files:
        raise ValueError("No files uploaded")
    with tempfile.TemporaryDirectory(prefix="document-deduper-") as temp:
        temp_dir = Path(temp)
        input_paths = []
        for idx, (filename, content) in enumerate(files, 1):
            path = temp_dir / f"{idx:03d}-{filename}"
            path.write_bytes(content)
            input_paths.append(path)

        options = DedupeOptions(
            preset=fields.get("preset") or "cassazione",
            start_regex=fields.get("start_regex") or None,
            similarity_threshold=float(fields.get("similarity") or "0.90"),
            prefer=fields.get("prefer") or "longest",
        )
        result = merge_documents(input_paths, options)
        out_dir = temp_dir / "outputs"
        out_dir.mkdir()
        merged = out_dir / "merged-readable.docx"
        manifest = out_dir / "manifest.csv"
        export_word(merged, result.unique_segments, duplicates_removed=result.duplicates_removed)
        write_manifest(manifest, result.unique_segments)
        chunk_paths = []
        if fields.get("google_chunks"):
            chunk_paths = export_google_docs_chunks(
                out_dir / "google-docs-parts",
                result.unique_segments,
                duplicates_removed=result.duplicates_removed,
                char_limit=int(fields.get("chunk_limit") or "760000"),
            )

        report = out_dir / "report.txt"
        report.write_text(
            "\n".join(
                [
                    f"Input records: {result.segments_in}",
                    f"Unique records: {len(result.unique_segments)}",
                    f"Duplicates removed: {result.duplicates_removed}",
                    f"Duplicate groups: {len(result.duplicate_groups)}",
                    f"Google Docs chunks: {len(chunk_paths)}",
                ]
            )
            + "\n",
            encoding="utf-8",
        )

        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for path in out_dir.rglob("*"):
                if path.is_file():
                    zf.write(path, path.relative_to(out_dir))
        return buffer.getvalue()


class Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        if self.path not in {"/", "/index.html"}:
            self.send_error(404)
            return
        data = INDEX_HTML.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_POST(self) -> None:
        if self.path != "/merge":
            self.send_error(404)
            return
        try:
            fields, files = parse_form(self)
            data = build_zip(fields, files)
        except Exception as exc:
            body = f"<h1>Merge failed</h1><pre>{html.escape(str(exc))}</pre>".encode("utf-8")
            self.send_response(400)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        filename = quote("document-deduper-output.zip")
        self.send_response(200)
        self.send_header("Content-Type", "application/zip")
        self.send_header("Content-Disposition", f"attachment; filename*=UTF-8''{filename}")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, fmt: str, *args: object) -> None:
        print(f"{self.address_string()} - {fmt % args}")


def run_server(host: str = "127.0.0.1", port: int = 8765) -> None:
    server = ThreadingHTTPServer((host, port), Handler)
    print(f"Document Deduper running at http://{host}:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
