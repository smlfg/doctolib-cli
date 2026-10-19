"""HTTP-Wrapper – requests mit Browser-UA, Timeout, klare Fehlerklassen."""

from __future__ import annotations

import logging
from typing import Any
from urllib.parse import urlparse

from .cli import USER_AGENT

LOG = logging.getLogger("doctolib_cli.http")

DEFAULT_BASE_URL = "https://www.doctolib.de"
DEFAULT_TIMEOUT = 30.0


class HttpError(Exception):
    """Vom Server zurückgegebener, vom Wrapper übersetzter Fehler."""

    def __init__(self, code: int, kind: str, message: str,
                 *, status: int | None = None,
                 url: str | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.kind = kind
        self.status = status
        self.url = url


def is_safe_url(url: str) -> bool:
    """Erlaubt nur https-URLs auf doctolib.de (oder konfigurierter Base)."""
    try:
        p = urlparse(url)
    except ValueError:
        return False
    return p.scheme in ("https",) and p.netloc.endswith("doctolib.de")


def get_text(url: str, *, base: str = DEFAULT_BASE_URL,
             params: dict[str, Any] | None = None,
             timeout: float = DEFAULT_TIMEOUT) -> tuple[int, str]:
    """GET → (status, text). Bei Netzwerkfehler wirft HttpError(code=3)."""
    import requests  # lokal importieren, damit Tests ohne requests starten

    full_url = url if url.startswith("http") else base.rstrip("/") + url
    if not is_safe_url(full_url):
        raise HttpError(1, "usage", f"URL nicht erlaubt: {full_url}",
                        url=full_url)
    headers = {
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "de-DE,de;q=0.9,en;q=0.8",
        }
    try:
        resp = requests.get(full_url, params=params, headers=headers,
                            timeout=timeout, allow_redirects=True)
    except requests.exceptions.Timeout as exc:
        raise HttpError(3, "network", f"Timeout: {exc}", url=full_url) from exc
    except requests.exceptions.SSLError as exc:
        raise HttpError(3, "network", f"TLS-Fehler: {exc}", url=full_url) from exc
    except requests.exceptions.ConnectionError as exc:
        raise HttpError(3, "network", f"Verbindung fehlgeschlagen: {exc}",
                        url=full_url) from exc
    except requests.exceptions.RequestException as exc:
        raise HttpError(3, "network", f"Netzwerkfehler: {exc}",
                        url=full_url) from exc

    if resp.status_code in (401, 403):
        raise HttpError(3, "network", f"Doctolib blockt (HTTP {resp.status_code})",
                        status=resp.status_code, url=full_url)
    return resp.status_code, resp.text