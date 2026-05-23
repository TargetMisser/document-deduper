from __future__ import annotations

import socket
import threading
import webbrowser
from http.server import ThreadingHTTPServer
from tkinter import BOTH, LEFT, Button, Frame, Label, Tk, messagebox

from doc_deduper.web import Handler


def find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


class DesktopApp:
    def __init__(self) -> None:
        self.host = "127.0.0.1"
        self.port = find_free_port()
        self.url = f"http://{self.host}:{self.port}"
        self.server = ThreadingHTTPServer((self.host, self.port), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)

        self.root = Tk()
        self.root.title("Document Deduper")
        self.root.geometry("460x190")
        self.root.minsize(420, 180)
        self.root.protocol("WM_DELETE_WINDOW", self.close)

        Label(
            self.root,
            text="Document Deduper is running locally",
            font=("Segoe UI", 13, "bold"),
            pady=14,
        ).pack()
        Label(
            self.root,
            text="Upload DOCX/PDF files in your browser, then download the merged ZIP.",
            wraplength=390,
            justify=LEFT,
            padx=22,
        ).pack(fill=BOTH)
        Label(
            self.root,
            text=self.url,
            fg="#0b5cab",
            pady=10,
        ).pack()

        buttons = Frame(self.root, pady=8)
        buttons.pack()
        Button(buttons, text="Open browser", command=self.open_browser, width=16).pack(side=LEFT, padx=6)
        Button(buttons, text="Quit", command=self.close, width=10).pack(side=LEFT, padx=6)

    def start(self) -> None:
        self.thread.start()
        self.root.after(350, self.open_browser)
        self.root.mainloop()

    def open_browser(self) -> None:
        webbrowser.open(self.url)

    def close(self) -> None:
        try:
            self.server.shutdown()
            self.server.server_close()
        except Exception as exc:
            messagebox.showwarning("Document Deduper", f"Could not stop the local server cleanly: {exc}")
        self.root.destroy()


def main() -> None:
    DesktopApp().start()


if __name__ == "__main__":
    main()
