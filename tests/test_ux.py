"""Tests für menschenlesbare Ausgabe im Terminal."""

from __future__ import annotations

import json

from doctolib_cli import cli
from doctolib_cli.output import format_search, format_show, format_slots

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

def test_format_search_is_numbered_with_address_and_slug() -> None:
    text = format_search(_search_payload())
    assert "[1] Dr. med. X – Hautarzt" in text
    assert "Hauptstr. 1, 74072 Heilbronn" in text
    assert "slug: hautarzt/heilbronn/dr-x" in text
    assert "1 Treffer." in text


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
    assert "[1] Dr. med. X" in out
    assert "slug: hautarzt/berlin/dr-x" in out
    assert not out.lstrip().startswith("{")


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


# ----- CLI: show/slots lesbar --------------------------------------------

def test_show_terminal_output_is_text(monkeypatch, http, capsys) -> None:
    monkeypatch.setattr(cli, "_is_tty", lambda: True)
    http.route(contains="/test-profile", text=profile_html(
        name="Dr. Maria Test", slug="hautarzt/berlin/test-profile"))
    http.route(contains="info.json", json_data=info_json(
        profile_slug="test-profile"))
    code = cli.main(["show", "hautarzt/berlin/test-profile"])
    assert code == 0
    out = capsys.readouterr().out
    assert "Dr. Maria Test (Physician)" in out
    assert "Slug: hautarzt/berlin/test-profile" in out
    assert not out.lstrip().startswith("{")


def test_slots_terminal_output_is_text(monkeypatch, http, capsys) -> None:
    monkeypatch.setattr(cli, "_is_tty", lambda: True)
    http.route(contains="info.json", json_data=info_json(
        profile_slug="test-profile"))
    http.route(contains="availabilities.json",
               json_data=availabilities_json())
    code = cli.main(["slots", "hautarzt/berlin/test-profile",
                     "--insurance", "public"])
    assert code == 0
    out = capsys.readouterr().out
    assert "Freie Termine – Praxis Mitte" in out
    assert "Di 20.10.2026: 09:00, 10:00, 11:00" in out
    assert not out.lstrip().startswith("{")
