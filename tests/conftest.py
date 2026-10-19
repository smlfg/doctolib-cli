"""Pytest-Konfiguration und -Hilfen."""

from __future__ import annotations

import json
import os
import sys
import urllib.parse
from pathlib import Path
from typing import Any

import pytest

# Damit ``import doctolib_cli`` in Tests funktioniert ohne Install.
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

# Sandbox aktivieren, falls nicht explizit aus (z.B. Live-Smoke).
if os.environ.get("ACCEPTANCE_SANDBOX") is None:
    os.environ["ACCEPTANCE_SANDBOX"] = "1"


class _FakeResp:
    """requests-ähnliches Antwort-Objekt für die HTTP-Stubs."""

    def __init__(self, status: int, text: str = "",
                 json_data: Any = None) -> None:
        self.status_code = status
        self.text = text
        self._json = json_data

    def json(self) -> Any:
        return self._json


class HttpRecorder:
    """In-Memory-HTTP-Server. Wird in ``monkeypatch`` als
    ``requests.get`` injiziert. Match auf URL-Pfad oder Query-String."""

    def __init__(self) -> None:
        self.routes: list[dict[str, Any]] = []
        self.calls: list[dict[str, Any]] = []

    def route(self, *, contains: str | None = None,
              status: int = 200,
              text: str | None = None,
              json_data: Any = None,
              params_contains: dict[str, str] | None = None) -> None:
        """Fügt eine Route hinzu. Erste passende Route gewinnt."""
        self.routes.append({
            "contains": contains,
            "params_contains": params_contains or {},
            "status": status,
            "text": text,
            "json_data": json_data,
        })

    def respond(self, url: str, **kwargs: Any) -> _FakeResp:
        self.calls.append({"url": url, "kwargs": kwargs})
        # Param-Match
        params = kwargs.get("params") or {}
        for r in self.routes:
            ok = True
            if r["contains"] is not None and r["contains"] not in url:
                ok = False
            for k, v in r["params_contains"].items():
                if str(params.get(k)) != str(v):
                    ok = False
                    break
            if ok:
                if r["json_data"] is not None:
                    return _FakeResp(r["status"],
                                     text=json.dumps(r["json_data"]),
                                     json_data=r["json_data"])
                return _FakeResp(r["status"], text=r["text"] or "")
        # Default: 404
        return _FakeResp(404, text="")


@pytest.fixture
def http(monkeypatch: pytest.MonkeyPatch) -> HttpRecorder:
    """Stubert ``_do_get`` (in ``doctolib_cli.http``) auf einen Recorder.

    ``requests.get`` wird lokal in _do_get importiert; einfacher ist es,
    die interne Schicht zu patchen, damit unsere Fixtures in Tests
    ohne echte Netz-Calls funktionieren.
    """
    rec = HttpRecorder()
    import doctolib_cli.http as http_mod
    monkeypatch.setattr(http_mod, "_do_get",
                        lambda url, **kwargs: rec.respond(url, **kwargs),
                        raising=True)
    return rec


@pytest.fixture
def tmp_config(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    """Setzt XDG_CONFIG_HOME auf tmp_path."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    return tmp_path