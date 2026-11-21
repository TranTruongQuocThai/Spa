"""Vercel adapter for the existing stdlib SpaFlow API.

On Vercel, set SPAFLOW_DATABASE=/tmp/spaflow_test.sqlite3 only for a disposable
demo. Use a managed database adapter before deploying real business data.
"""
import os
from urllib.parse import parse_qs, urlparse

if os.getenv("VERCEL"):
    os.environ.setdefault("SPAFLOW_DATABASE", "/tmp/spaflow_test.sqlite3")

from server import App, init_db  # noqa: E402

init_db(False)

class handler(App):
    """Translate the Vercel rewrite target back to the application's API path."""
    def _restore_api_path(self):
        parsed = urlparse(self.path)
        if parsed.path != "/api/index.py":
            return
        target = parse_qs(parsed.query).get("path", [""])[0].strip("/")
        self.path = "/api/" + target

    def do_GET(self):
        self._restore_api_path()
        return super().do_GET()

    def do_POST(self):
        self._restore_api_path()
        return super().do_POST()

    def do_PUT(self):
        self._restore_api_path()
        return super().do_PUT()

    def do_DELETE(self):
        self._restore_api_path()
        return super().do_DELETE()
