"""Tests für DOCTOLIB_BASE_URL und den lokalen HTTP-Suchpfad."""

from __future__ import annotations

import pytest

from doctolib_cli import http as http_mod
from doctolib_cli import search as search_mod
from doctolib_cli.show import show_profile
from doctolib_cli.slots import slots_for_profile

from .fixtures.builders import (
    availabilities_json,
    info_json,
    profile_html,
    search_html_berlin,
)


def test_resolve_base_default_and_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DOCTOLIB_BASE_URL", raising=False)
    assert http_mod.resolve_base() == "https://www.doctolib.de"
    monkeypatch.setenv("DOCTOLIB_BASE_URL", "http://127.0.0.1:8765/")
    assert http_mod.resolve_base() == "http://127.0.0.1:8765"


def test_is_safe_url_allows_configured_base(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DOCTOLIB_BASE_URL", "http://127.0.0.1:8765")
    assert http_mod.is_safe_url("https://www.doctolib.de/hautarzt/berlin")
    assert http_mod.is_safe_url("http://127.0.0.1:8765/hautarzt/berlin")
    assert not http_mod.is_safe_url("http://127.0.0.1:9999/hautarzt/berlin")
    assert not http_mod.is_safe_url("https://example.invalid/hautarzt")


def test_get_text_uses_env_base(monkeypatch: pytest.MonkeyPatch, http) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("DOCTOLIB_BASE_URL", "http://127.0.0.1:8765")
    http.route(contains="/probe", text="ok")
    status, text = http_mod.get_text("/probe")
    assert (status, text) == (200, "ok")
    assert http.calls[0]["url"] == "http://127.0.0.1:8765/probe"


def test_search_localhost_uses_http_without_playwright(
        monkeypatch: pytest.MonkeyPatch) -> None:
    html = search_html_berlin([
        {"name": "Dr. Lokal", "url": "/hautarzt/heilbronn/dr-lokal"},
    ], city_name="Heilbronn")
    monkeypatch.setenv("DOCTOLIB_BASE_URL", "http://127.0.0.1:8765")

    def _no_playwright(url: str) -> str:
        raise AssertionError("Playwright darf bei localhost nicht starten")

    monkeypatch.setattr(search_mod, "_fetch_search_html", _no_playwright)
    monkeypatch.setattr(search_mod, "_fetch_listing_requests", lambda url: html)
    code, payload = search_mod.search_speciality_location("hautarzt", "heilbronn")
    assert code == 0, payload
    assert payload["results"][0]["name"] == "Dr. Lokal"


def test_search_falls_back_when_playwright_fails(
        monkeypatch: pytest.MonkeyPatch) -> None:
    html = search_html_berlin([
        {"name": "Dr. Fallback", "url": "/hautarzt/berlin/dr-fallback"},
    ])
    monkeypatch.delenv("DOCTOLIB_BASE_URL", raising=False)

    def _broken(url: str) -> str:
        raise search_mod._SearchFetchError(3, "network", "chromium fehlt")

    monkeypatch.setattr(search_mod, "_fetch_search_html", _broken)
    monkeypatch.setattr(search_mod, "_fetch_listing_requests", lambda url: html)
    code, payload = search_mod.search_speciality_location("hautarzt", "berlin")
    assert code == 0, payload
    assert payload["results"][0]["name"] == "Dr. Fallback"


def test_show_profile_uses_env_base(monkeypatch: pytest.MonkeyPatch, http) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("DOCTOLIB_BASE_URL", "http://127.0.0.1:8765")
    http.route(contains="/test-profile", text=profile_html(
        name="Dr. Basis", slug="hautarzt/berlin/test-profile"))
    http.route(contains="info.json", json_data=info_json(
        profile_slug="test-profile"))
    code, payload = show_profile("hautarzt/berlin/test-profile")
    assert code == 0, payload
    assert all(call["url"].startswith("http://127.0.0.1:8765")
               for call in http.calls)


def test_slots_uses_env_base(monkeypatch: pytest.MonkeyPatch, http) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("DOCTOLIB_BASE_URL", "http://127.0.0.1:8765")
    http.route(contains="info.json", json_data=info_json(
        profile_slug="test-profile"))
    http.route(contains="availabilities.json",
               json_data=availabilities_json())
    code, payload = slots_for_profile("hautarzt/berlin/test-profile",
                                      days=7, insurance="public")
    assert code == 0, payload
    assert all(call["url"].startswith("http://127.0.0.1:8765")
               for call in http.calls)
