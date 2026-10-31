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
    assert "Di 20.10.: 09:00, 10:00" in text
    assert "slug" not in text
    assert "Termin(e)." not in text


def test_format_slots_verbose_keeps_context_and_slug() -> None:
    text = format_slots(_slots_payload(), verbose=True)
    assert "Freie Termine – Praxis X" in text
    assert "Slug: hautarzt/heilbronn/dr-x" in text
    assert "Di 20.10.: 09:00, 10:00" in text
    assert "2 Termin(e)." in text


def test_format_slots_wraps_after_eight_times() -> None:
    payload = {
        "profile": {"slug": "x"},
        "availabilities": [{
            "date": "2026-10-20",
            "slots": [f"2026-10-20T{n:02d}:00:00+02:00"
                      for n in range(10)],
        }],
        "total": 10,
    }
    text = format_slots(payload)
    lines = text.splitlines()
    assert lines[0].count(", ") == 7
    assert lines[0].endswith("07:00")
    assert lines[1] == "           08:00, 09:00"


def test_format_slots_empty_period() -> None:
    text = format_slots({"availabilities": [], "total": 0})
    assert "(keine freien Termine im Zeitraum)" in text


def test_format_show_is_compact_profile() -> None:
    record = {
        "name": "Dr. Maria Test",
        "type": "Physician",
        "speciality": "Hautarzt",
        "address": {"street": "Teststr. 42", "postal_code": "10115",
                    "city": "Berlin"},
        "telephone": "030 12345678",
        "practice_id": 635395,
        "motive": [{"id": 4711, "name": "Hautkrebsvorsorge"}],
        "slug": "hautarzt/berlin/test-profile",
        "url": "https://www.doctolib.de/hautarzt/berlin/test-profile",
    }
    text = format_show(record)
    lines = text.splitlines()
    assert lines[0] == "Dr. Maria Test"
    assert "Fach: Hautarzt" in text
    assert "Adresse: Teststr. 42, 10115 Berlin" in text
    assert "Telefon: 030 12345678" in text
    assert "Online-Buchung: ja" in text
    assert "Link: https://www.doctolib.de/hautarzt/berlin/test-profile" \
        in text
    assert "Slug:" not in text
    assert len(lines) == 6


def test_format_show_without_phone_and_booking() -> None:
    text = format_show({
        "name": "Dr. Offline",
        "speciality": None,
        "address": {"street": "Weg 3", "postal_code": "10115",
                    "city": "Berlin"},
        "motive": [{"id": None, "name": "Beratung"}],
        "slug": "arzt/berlin/offline",
        "url": "",
    })
    assert "Telefon" not in text
    assert "Online-Buchung: nein" in text
    assert "Fach:" not in text
    assert "Link:" not in text


def test_format_show_verbose_keeps_slug() -> None:
    text = format_show({
        "name": "Dr. Maria Test",
        "speciality": "Hautarzt",
        "address": {},
        "motive": [{"id": None, "name": "Beratung"}],
        "slug": "hautarzt/berlin/test-profile",
        "url": "https://www.doctolib.de/hautarzt/berlin/test-profile",
    }, verbose=True)
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
    assert "hautarzt/heilbronn/dr-x" not in out.split("Nummer wählen")[1]
    assert "Gewählt: Dr. med. X" in out
    assert "Di 20.10.: 09:00" in out
    assert out.count("Treffer für die Auswahl") == 0


def test_slots_interactive_verbose_shows_slug(monkeypatch, http,
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
                     "--insurance", "public", "-v"])
    assert code == 0
    out = capsys.readouterr().out
    assert "Gewählt: Dr. med. X (hautarzt/heilbronn/dr-x)" in out
    assert "Freie Termine – Praxis Mitte" in out
    assert "Di 20.10.: 09:00" in out


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


def test_show_terminal_is_compact_without_slug(monkeypatch, http,
                                               capsys) -> None:
    html = search_html_berlin([
        {"name": "Dr. med. X",
         "url": "/hautarzt/heilbronn/dr-x?pid=practice-635395"},
    ], city_name="Heilbronn")
    import doctolib_cli.search as search_mod
    monkeypatch.setattr(search_mod, "_fetch_search_html", lambda url: html)
    monkeypatch.setattr(cli, "_is_tty", lambda: True)
    http.route(contains="/dr-x", text=profile_html(
        name="Dr. med. X", slug="hautarzt/heilbronn/dr-x"))
    http.route(contains="info.json", json_data=info_json(
        profile_slug="dr-x"))

    code = cli.main(["show", "hautarzt", "heilbronn", "--pick", "1"])
    assert code == 0
    out = capsys.readouterr().out
    assert "Gewählt: Dr. med. X" in out
    assert "Dr. med. X\n" in out
    assert "Fach: Hautarzt" in out
    assert "Online-Buchung: ja" in out
    assert "Link: http" in out
    assert "Slug:" not in out
    assert "4711" not in out


def test_show_terminal_verbose_keeps_slug(monkeypatch, http, capsys) -> None:
    html = search_html_berlin([
        {"name": "Dr. med. X",
         "url": "/hautarzt/heilbronn/dr-x?pid=practice-635395"},
    ], city_name="Heilbronn")
    import doctolib_cli.search as search_mod
    monkeypatch.setattr(search_mod, "_fetch_search_html", lambda url: html)
    monkeypatch.setattr(cli, "_is_tty", lambda: True)
    http.route(contains="/dr-x", text=profile_html(
        name="Dr. med. X", slug="hautarzt/heilbronn/dr-x"))
    http.route(contains="info.json", json_data=info_json(
        profile_slug="dr-x"))

    code = cli.main(["show", "hautarzt", "heilbronn", "--pick", "1", "-v"])
    assert code == 0
    out = capsys.readouterr().out
    assert "Gewählt: Dr. med. X (hautarzt/heilbronn/dr-x)" in out
    assert "Slug: hautarzt/heilbronn/dr-x" in out


def test_show_profile_telephone_reaches_record(http) -> None:
    from doctolib_cli.show import show_profile
    html = profile_html().replace(
        '"@type": "Physician",',
        '"@type": "Physician", "telephone": "030 12345678",')
    http.route(contains="/test-profile", text=html)
    http.route(contains="info.json", json_data=info_json())
    code, payload = show_profile("hautarzt/berlin/test-profile")
    assert code == 0
    assert payload["telephone"] == "030 12345678"


def test_show_profile_without_telephone_has_no_key(http) -> None:
    from doctolib_cli.show import show_profile
    http.route(contains="/test-profile", text=profile_html())
    http.route(contains="info.json", json_data=info_json())
    _, payload = show_profile("hautarzt/berlin/test-profile")
    assert "telephone" not in payload


def test_help_documents_search_by_name(capsys) -> None:
    for cmd in ("slots", "show"):
        code = cli.main([cmd, "--help"])
        assert code == 0
        out = capsys.readouterr().out
        assert "--search" in out
        assert "--pick" in out
        assert "hautarzt heilbronn" in out


# ----- specialities: Filter + mehrspaltiges TTY-Raster ---------------------

def test_specialities_filter_matches_slug_and_name(monkeypatch,
                                                   capsys) -> None:
    monkeypatch.setattr(cli, "_is_tty", lambda: True)
    code = cli.main(["specialities", "haut"])
    assert code == 0
    out = capsys.readouterr().out
    assert "hautarzt" in out
    assert "dermatologie" in out
    assert "augenarzt" not in out
    assert "2 Fachrichtungen." in out


def test_specialities_filter_case_insensitive(monkeypatch, capsys) -> None:
    monkeypatch.setattr(cli, "_is_tty", lambda: True)
    code = cli.main(["specialities", "HAUTARZT"])
    assert code == 0
    out = capsys.readouterr().out
    assert "hautarzt" in out
    assert "psychotherapie" not in out


def test_specialities_no_match_exits_1(monkeypatch, capsys) -> None:
    monkeypatch.setattr(cli, "_is_tty", lambda: True)
    code = cli.main(["specialities", "xyzzynotfound"])
    assert code == 1
    err = capsys.readouterr().err
    assert "[usage]" in err
    assert "xyzzynotfound" in err


def test_specialities_no_match_json_error(monkeypatch, capsys) -> None:
    code = cli.main(["specialities", "xyzzynotfound", "--json"])
    assert code == 1
    out = capsys.readouterr().out
    data = json.loads(out)
    assert data["error"]["kind"] == "usage"


def test_specialities_filter_json_stays_same_shape(monkeypatch,
                                                   capsys) -> None:
    code = cli.main(["specialities", "haut", "--json"])
    assert code == 0
    data = json.loads(capsys.readouterr().out)
    assert data["count"] == 2
    slugs = {s["slug"] for s in data["specialities"]}
    assert slugs == {"hautarzt", "dermatologie"}


def test_specialities_default_listing_is_multicolumn(monkeypatch,
                                                     capsys) -> None:
    from doctolib_cli.specialities import SPECIALITIES
    monkeypatch.setattr(cli, "_is_tty", lambda: True)
    code = cli.main(["specialities"])
    assert code == 0
    out = capsys.readouterr().out
    lines = out.strip().splitlines()
    # Kompakter als 58 Einzeiler: jede Zeile trägt mehrere Slugs.
    assert len(lines) - 2 < len(SPECIALITIES)  # -1 Leerzeile, -1 Zähler
    assert "58 Fachrichtungen." in out


def test_specialities_grid_lines_column_count() -> None:
    from doctolib_cli.specialities import grid_lines
    lines = grid_lines(["aa", "bb", "cc", "dd", "ee"], width=10)
    assert len(lines) == 3
    assert lines[0] == "aa  bb"
    assert lines[2] == "ee"
