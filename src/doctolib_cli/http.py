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


def _do_get(full_url: str, *, headers: dict[str, str],
            timeout: float = DEFAULT_TIMEOUT,
            params: dict[str, Any] | None = None):
    """Intern: führt GET aus, übersetzt Exceptions in HttpError.

    Wirft NIEMALS status-bedingte Fehler (401/403/404); das macht der
    Aufrufer. So bleibt die Kontrolle über exit-Codes beim Handler.
    """
    import requests  # lokal importieren, damit Tests ohne requests starten
    try:
        return requests.get(full_url, params=params, headers=headers,
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


def get_text(url: str, *, base: str = DEFAULT_BASE_URL,
             params: dict[str, Any] | None = None,
             timeout: float = DEFAULT_TIMEOUT) -> tuple[int, str]:
    """GET → (status, text). Bei Netzwerkfehler wirft HttpError(code=3)."""
    full_url = url if url.startswith("http") else base.rstrip("/") + url
    if not is_safe_url(full_url):
        raise HttpError(1, "usage", f"URL nicht erlaubt: {full_url}",
                        url=full_url)
    headers = {
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "de-DE,de;q=0.9,en;q=0.8",
        }
    resp = _do_get(full_url, headers=headers, timeout=timeout, params=params)
    if resp.status_code in (401, 403):
        raise HttpError(3, "network", f"Doctolib blockt (HTTP {resp.status_code})",
                        status=resp.status_code, url=full_url)
    return resp.status_code, resp.text


def get_json(url: str, *, base: str = DEFAULT_BASE_URL,
             params: dict[str, Any] | None = None,
             timeout: float = DEFAULT_TIMEOUT,
             accept: str = "application/json, text/javascript, */*; q=0.01",
             referer: str | None = None,
             allow_status: tuple[int, ...] = (200,)) -> tuple[int, Any]:
    """GET → (status, parsed JSON).

    Doctolib gibt teils HTML auf 200 zurück (Bot-Wall), teils echtes JSON.
    Wirft HttpError(code=3) bei Netzfehler, HttpError(code=4) bei
    unlesbarem JSON, und HttpError(code=3) bei Status außerhalb
    ``allow_status``.
    """
    import json as _json

    full_url = url if url.startswith("http") else base.rstrip("/") + url
    if not is_safe_url(full_url):
        raise HttpError(1, "usage", f"URL nicht erlaubt: {full_url}",
                        url=full_url)
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": accept,
        "Accept-Language": "de-DE,de;q=0.9,en;q=0.8",
    }
    if referer:
        headers["Referer"] = referer
    resp = _do_get(full_url, headers=headers, timeout=timeout, params=params)
    if resp.status_code not in allow_status:
        raise HttpError(3, "network",
                        f"Doctolib HTTP {resp.status_code}",
                        status=resp.status_code, url=full_url)
    try:
        return resp.status_code, _json.loads(resp.text)
    except _json.JSONDecodeError as exc:
        raise HttpError(4, "parse",
                        f"kein JSON von {full_url} ({exc.msg})",
                        url=full_url) from exc