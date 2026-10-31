"""Tests für menschenlesbare Ausgabe und Suche statt Slug."""

from __future__ import annotations

import io
import json
import sys

import pytest

from doctolib_cli import cli
from doctolib_cli.output import format_search, format_show, format_slots
from doctolib_cli.resolve import _parse_search_query, resolve_profile

from .fixtures.builders import (
    availabilities_json,
    info_json,
    profile_html,
    search_html_berlin,
)


def _search_payload() -> dict:
    return {
        "query": {"speciality": "hautarzt", "location": "heilbronn"},
        "count": 1,
        "results": [{
            "name": "Dr. med. X",
            "type": "Physician",
            "address": {"street": "Hauptstr. 1", "postal_code": "74072",
                        "city": "Heilbronn"},
            "motive": "Hautarzt",
            "slug": "hautarzt/heilbronn/dr-x",
        }],
    }


def _slots_payload() -> dict:
    return {
        "profile": {"slug": "hautarzt/heilbronn/dr-x",
                    "practice_name": "Praxis X",
                    "practice_address": "Hauptstr. 1, 74072 Heilbronn"},
        "motive": {"id": 1, "name": "Hautkrebsvorsorge", "insurance": "public"},
        "availabilities": [{
            "date": "2026-10-20",
            "slots": ["2026-10-20T09:00:00+02:00",
                      "2026-10-20T10:00:00+02:00"],
        }],
        "total": 2,
    }


# ----- Formatter ----------------------------------------------------------

def test_format_search_hides_slug_without_verbose() -> None:
    text = format_search(_search_payload())
    assert " 1. Dr. med. X – Hautarzt" in text
    assert "    Hauptstr. 1, 74072 Heilbronn" in text
    assert "slug" not in text
    assert "1 Treffer." in text


def test_format_search_verbose_adds_slug_line() -> None:
    text = format_search(_search_payload(), verbose=True)
    assert " 1. Dr. med. X – Hautarzt" in text
    assert "    slug: hautarzt/heilbronn/dr-x" in text


def test_format_slots_groups_times_per_day() -> None:
    text = format_slots(_slots_payload())
    assert "Freie Termine – Praxis X" in text
    assert "Di 20.10.2026: 09:00, 10:00" in text
    assert "2 Termin(e)." in text


def test_format_show_lists_core_fields() -> None:
    text = format_show({
        "name": "Dr. Maria Test",
        "type": "Physician",
        "speciality": "Hautarzt",
        "address": {"street": "Teststr. 42", "postal_code": "10115",
                    "city": "Berlin"},
        "motive": [{"id": 4711, "name": "Hautkrebsvorsorge"}],
        "slug": "hautarzt/berlin/test-profile",
        "url": "https://www.doctolib.de/hautarzt/berlin/test-profile",
    })
    assert "Dr. Maria Test (Physician)" in text
    assert "Fachrichtung: Hautarzt" in text
    assert "Teststr. 42, 10115 Berlin" in text
    assert "4711 Hautkrebsvorsorge" in text
    assert "Slug: hautarzt/berlin/test-profile" in text


# ----- CLI: TTY vs Pipe ---------------------------------------------------

def test_search_terminal_output_is_text(monkeypatch, capsys) -> None:
    html = search_html_berlin([
        {"name": "Dr. med. X", "url": "/hautarzt/berlin/dr-x"},
    ])
    import doctolib_cli.search as search_mod
    monkeypatch.setattr(search_mod, "_fetch_search_html", lambda url: html)
    monkeypatch.setattr(cli, "_is_tty", lambda: True)
    code = cli.main(["search", "hautarzt", "berlin"])
    assert code == 0
    out = capsys.readouterr().out
    assert out.startswith("Suche: hautarzt in berlin")
    assert " 1. Dr. med. X" in out
    assert "slug" not in out
    assert not out.lstrip().startswith("{")


def test_search_terminal_verbose_shows_slug(monkeypatch, capsys) -> None:
    html = search_html_berlin([
        {"name": "Dr. med. X", "url": "/hautarzt/berlin/dr-x"},
    ])
    import doctolib_cli.search as search_mod
    monkeypatch.setattr(search_mod, "_fetch_search_html", lambda url: html)
    monkeypatch.setattr(cli, "_is_tty", lambda: True)
    code = cli.main(["search", "hautarzt", "berlin", "-v"])
    assert code == 0
    out = capsys.readouterr().out
    assert "    slug: hautarzt/berlin/dr-x" in out


def test_search_pipe_keeps_json_without_flag(monkeypatch, capsys) -> None:
    html = search_html_berlin([
        {"name": "Dr. med. X", "url": "/hautarzt/berlin/dr-x"},
    ])
    import doctolib_cli.search as search_mod
    monkeypatch.setattr(search_mod, "_fetch_search_html", lambda url: html)
    monkeypatch.setattr(cli, "_is_tty", lambda: False)
    code = cli.main(["search", "hautarzt", "berlin"])
    assert code == 0
    data = json.loads(capsys.readouterr().out)
    assert data["count"] == 1


# ----- Query statt Slug ---------------------------------------------------

def test_parse_search_query_uses_longest_speciality_prefix() -> None:
    assert _parse_search_query("hautarzt heilbronn") == (
        "hautarzt", "heilbronn")
    assert _parse_search_query("plastische chirurgie bad homburg") == (
        "plastische chirurgie", "bad homburg")
    assert _parse_search_query("hautarzt") is None


def test_resolve_profile_keeps_slug_untouched(monkeypatch) -> None:
    import doctolib_cli.resolve as resolve_mod
    monkeypatch.setattr(resolve_mod, "_search_proxy", lambda *a, **k: (
        0, _search_payload()))
    code, payload = resolve_profile(["hautarzt/berlin/dr-x"])
    assert code == 0
    assert payload["slug"] == "hautarzt/berlin/dr-x"
    assert payload["from_search"] is False


def test_slots_with_search_and_pick(monkeypatch, http, capsys) -> None:
    html = search_html_berlin([
        {"name": "Dr. med. X",
         "url": "/hautarzt/heilbronn/dr-x?pid=practice-635395"},
    ], city_name="Heilbronn")
    import doctolib_cli.search as search_mod
    monkeypatch.setattr(search_mod, "_fetch_search_html", lambda url: html)
    http.route(contains="info.json", json_data=info_json(
        profile_slug="dr-x", practice_id=635395))
    http.route(contains="availabilities.json",
               json_data=availabilities_json())

    code = cli.main(["slots", "hautarzt", "heilbronn",
                      "--pick", "1", "--insurance", "public", "--json"])
    assert code == 0
    data = json.loads(capsys.readouterr().out)
    assert data["profile"]["slug"] == "hautarzt/heilbronn/dr-x"
    assert data["total"] >= 1


def test_slots_search_without_tty_exits_usage_with_candidates(
        monkeypatch, capsys) -> None:
    html = search_html_berlin([
        {"name": "Dr. med. X", "url": "/hautarzt/heilbronn/dr-x"},
    ], city_name="Heilbronn")
    import doctolib_cli.search as search_mod
    monkeypatch.setattr(search_mod, "_fetch_search_html", lambda url: html)
    monkeypatch.setattr(cli, "_is_tty", lambda: False)
    monkeypatch.setattr(cli, "_stdin_tty", lambda: False)

    code = cli.main(["slots", "hautarzt", "heilbronn", "--json"])
    assert code == 1
    data = json.loads(capsys.readouterr().out)
    assert data["error"]["kind"] == "usage"
    assert data["error"]["candidates"][0]["slug"] == \
        "hautarzt/heilbronn/dr-x"
    assert "--pick" in data["error"]["hint"]


def test_slots_interactive_prompt_selects_number(monkeypatch, http,
                                                 capsys) -> None:
    html = search_html_berlin([
        {"name": "Dr. med. X",
         "url": "/hautarzt/heilbronn/dr-x?pid=practice-635395"},
    ], city_name="Heilbronn")
    import doctolib_cli.search as search_mod
    monkeypatch.setattr(search_mod, "_fetch_search_html", lambda url: html)
    monkeypatch.setattr(cli, "_is_tty", lambda: True)
    monkeypatch.setattr(cli, "_stdin_tty", lambda: True)
    monkeypatch.setattr(sys, "stdin", io.StringIO("1\n"))
    http.route(contains="info.json", json_data=info_json(
        profile_slug="dr-x", practice_id=635395))
    http.route(contains="availabilities.json",
               json_data=availabilities_json())

    code = cli.main(["slots", "hautarzt", "heilbronn",
                     "--insurance", "public"])
    assert code == 0
    out = capsys.readouterr().out
    assert "Nummer wählen [1-1]" in out
    assert "Gewählt: Dr. med. X" in out
    assert "Di 20.10.2026: 09:00" in out


def test_slots_interactive_bad_choice_is_usage(monkeypatch, capsys) -> None:
    html = search_html_berlin([
        {"name": "Dr. med. X", "url": "/hautarzt/heilbronn/dr-x"},
    ], city_name="Heilbronn")
    import doctolib_cli.search as search_mod
    monkeypatch.setattr(search_mod, "_fetch_search_html", lambda url: html)
    monkeypatch.setattr(cli, "_is_tty", lambda: True)
    monkeypatch.setattr(cli, "_stdin_tty", lambda: True)
    monkeypatch.setattr(sys, "stdin", io.StringIO("99\n"))

    code = cli.main(["slots", "hautarzt", "heilbronn"])
    assert code == 1
    err = capsys.readouterr().err
    assert "[usage]" in err
    assert "Treffer für die Auswahl" in err


def test_show_with_search_and_pick(monkeypatch, http, capsys) -> None:
    html = search_html_berlin([
        {"name": "Dr. med. X", "url": "/hautarzt/heilbronn/dr-x"},
    ], city_name="Heilbronn")
    import doctolib_cli.search as search_mod
    monkeypatch.setattr(search_mod, "_fetch_search_html", lambda url: html)
    http.route(contains="/dr-x", text=profile_html(
        name="Dr. med. X", slug="hautarzt/heilbronn/dr-x"))
    http.route(contains="info.json", json_data=info_json(
        profile_slug="dr-x"))

    code = cli.main(["show", "hautarzt", "heilbronn", "--pick", "1",
                     "--json"])
    assert code == 0
    data = json.loads(capsys.readouterr().out)
    assert data["name"] == "Dr. med. X"
    assert data["slug"] == "hautarzt/heilbronn/dr-x"


def test_show_pick_out_of_range(monkeypatch, capsys) -> None:
    html = search_html_berlin([
        {"name": "Dr. med. X", "url": "/hautarzt/heilbronn/dr-x"},
    ], city_name="Heilbronn")
    import doctolib_cli.search as search_mod
    monkeypatch.setattr(search_mod, "_fetch_search_html", lambda url: html)

    code = cli.main(["show", "hautarzt", "heilbronn", "--pick", "5",
                     "--json"])
    assert code == 1
    data = json.loads(capsys.readouterr().out)
    assert data["error"]["kind"] == "usage"
    assert data["error"]["candidates"]


def test_help_documents_search_by_name(capsys) -> None:
    for cmd in ("slots", "show"):
        code = cli.main([cmd, "--help"])
        assert code == 0
        out = capsys.readouterr().out
        assert "--search" in out
        assert "--pick" in out
        assert "hautarzt heilbronn" in out
