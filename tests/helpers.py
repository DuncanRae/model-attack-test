"""Shared by the tests: stand-in servers on this computer, and target files written to a temporary folder."""
from __future__ import annotations

import json
import sys
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from attack_test import target  # noqa: E402
from practice import bot  # noqa: E402


class Servers:
    """Starts servers on free ports and stops them all at the end of a test."""

    def __init__(self):
        self.running = []
        self.folder = tempfile.TemporaryDirectory()

    def _start(self, server) -> str:
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.running.append(server)
        return f"http://127.0.0.1:{server.server_address[1]}"

    def practice(self, kind: str, key: str = "") -> str:
        return self._start(bot.make_server(kind, 0, key))

    def scripted(self, answer) -> tuple[str, list]:
        """A server whose every POST is answered by `answer(path, body, headers)` -> (status, headers, text).
        Returns its address and the list every request is recorded in."""
        seen = []

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_POST(self):
                raw = self.rfile.read(int(self.headers.get("Content-Length", "0")))
                try:
                    body = json.loads(raw or b"{}")
                except ValueError:
                    body = None
                seen.append({"path": self.path, "body": body, "headers": dict(self.headers)})
                status, headers, text = answer(self.path, body, self.headers)
                data = text.encode("utf-8")
                self.send_response(status)
                for k, v in headers.items():
                    self.send_header(k, v)
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

        return self._start(ThreadingHTTPServer(("127.0.0.1", 0), Handler)), seen

    def file(self, name: str, data) -> str:
        path = Path(self.folder.name) / name
        path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        return str(path)

    def target(self, url: str, **changes) -> dict:
        """A checked target for a server that takes {"messages": [...]} and answers {"reply": "..."}."""
        data = {"name": "Test bot", "owner": "The tests", "environment": "local",
                "request": {"url": url + "/chat", "body": {"messages": "{{messages}}"}}, "reply": "reply",
                "refusals": ["I can only help with questions about leave"], "never_say": ["CANARY-7731"]}
        data.update(changes)
        return target.load(self.file(f"target-{len(list(Path(self.folder.name).iterdir()))}.json", data))

    def session_target(self, url: str) -> dict:
        return self.target(url, request={"url": url + "/say", "body": {"session": "{{session}}", "message": "{{message}}"}},
                           conversation={"style": "session", "start": {"url": url + "/session", "body": {}}, "session": "id"})

    def close(self):
        for s in self.running:
            s.shutdown()
            s.server_close()
        self.folder.cleanup()


def no_sleep(seconds):
    pass
