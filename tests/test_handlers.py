"""Tests für search/show/slots/specialities/watch/book."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from doctolib_cli import cli
from doctolib_cli.show import show_profile
from doctolib_cli.slots import slots_for_profile
from doctolib_cli.specialities import resolve_speciality
from doctolib_cli.watch import (
    add_watch,
    check_watches,
    list_watches,
    remove_watch,
)

from .fixtures.builders import (
    availabilities_json,
    empty_availabilities_json,
    info_json,
    profile_html,
    search_html_berlin,
)


# ----- search -------------------------------------------------------------

def test_search_speciality_location_happy_path(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """Vollständiger Such-Flow mit gestubbtem Playwright."""
    html = search_html_berlin([
        {"name": "Dr. A", "url": "/hautarzt/berlin/dr-a?pid=practice-1"},
        {"name": "Dr. B", "url": "/hautarzt/berlin/dr-b?pid=practice-2"},
    ])
    import doctolib_cli.search as search_mod
    monkeypatch.setattr(search_mod, "_fetch_search_html", lambda url: html)
    code, payload = search_mod.search_speciality_location(
        "hautarzt", "Berlin", limit=5)
    assert code == 0
    assert payload["query"]["speciality"] == "hautarzt"
    assert payload["count"] == 2
    assert payload["results"][0]["name"] == "Dr. A"


def test_search_unknown_speciality(monkeypatch: pytest.MonkeyPatch) -> None:
    import doctolib_cli.search as search_mod
    monkeypatch.setattr(search_mod, "_fetch_search_html", lambda url: "")
    code, payload = search_mod.search_speciality_location(
        "nonsense", "berlin", limit=5)
    assert code == 1
    assert payload["error"]["kind"] == "usage"


def test_search_invalid_limit() -> None:
    from doctolib_cli.search import search_speciality_location
    for bad in (0, 51, -1):
        code, payload = search_speciality_location(
            "hautarzt", "berlin", limit=bad)
        assert code == 1
        assert payload["error"]["kind"] == "usage"


def test_search_empty_location() -> None:
    from doctolib_cli.search import search_speciality_location
    code, payload = search_speciality_location("hautarzt", "  ", limit=5)
    assert code == 1


def test_search_resolves_clartext_speciality(
        monkeypatch: pytest.MonkeyPatch) -> None:
    html = search_html_berlin([
        {"name": "Dr. A", "url": "/zahnarzt/berlin/dr-a"},
    ])
    import doctolib_cli.search as search_mod
    monkeypatch.setattr(search_mod, "_fetch_search_html", lambda url: html)
    code, payload = search_mod.search_speciality_location(
        "Zahnarzt", "Berlin", limit=5)
    assert code == 0
    assert payload["query"]["speciality"] == "zahnarzt"


# ----- show ---------------------------------------------------------------

def test_show_profile_happy_path(http) -> None:  # type: ignore[no-untyped-def]
    """show_profile gegen Stub."""
    html = profile_html(name="Dr. Maria Test",
                        slug="hautarzt/berlin/test-profile")
    info = info_json(profile_slug="test-profile")
    http.route(contains="/test-profile", text=html)
    http.route(contains="info.json", json_data=info)
    code, payload = show_profile("hautarzt/berlin/test-profile")
    assert code == 0
    assert payload["name"] == "Dr. Maria Test"
    assert payload["slug"] == "hautarzt/berlin/test-profile"
    assert payload["practice_id"] == 635395


def test_show_profile_404(http) -> None:  # type: ignore[no-untyped-def]
    http.route(contains="/hautarzt/berlin/missing", status=404, text="")
    code, payload = show_profile("hautarzt/berlin/missing")
    assert code == 4
    assert payload["error"]["kind"] == "parse"


def test_show_profile_invalid_slug() -> None:
    code, payload = show_profile("not a slug")
    assert code == 1
    assert payload["error"]["kind"] == "usage"


def test_show_profile_empty() -> None:
    code, payload = show_profile("")
    assert code == 1


# ----- slots --------------------------------------------------------------

def _setup_slots(http, motive_name="Hautkrebsvorsorge",  # type: ignore[no-untyped-def]
                  motive_id=4711,
                  practice_id=635395,
                  agenda_id=4321,
                  insurance="public") -> None:
    info = info_json(motive_name=motive_name, motive_id=motive_id,
                      practice_id=practice_id, agenda_id=agenda_id,
                      insurance=insurance)
    http.route(contains="info.json", json_data=info)
    http.route(contains="availabilities.json",
               json_data=availabilities_json())


def test_slots_happy_path(http) -> None:  # type: ignore[no-untyped-def]
    _setup_slots(http)
    code, payload = slots_for_profile("hautarzt/berlin/test-profile",
                                       days=7, insurance="public")
    assert code == 0, payload
    assert payload["motive"]["name"] == "Hautkrebsvorsorge"
    assert payload["insurance_requested"] == "public"
    assert payload["insurances_queried"] == ["public"]
    assert payload["total"] >= 1


def test_slots_filter_private_drops_public_configs(
        http) -> None:  # type: ignore[no-untyped-def]
    # Profil kennt nur public-Konfigurationen → --insurance private
    # muss leer resultieren und exit 1 liefern.
    _setup_slots(http, insurance="public")
    code, payload = slots_for_profile("hautarzt/berlin/test-profile",
                                       days=7, insurance="private")
    assert code == 1
    assert "private" in payload["error"]["message"]
    assert "available_motives" in payload["error"]


def test_slots_filter_any_returns_combined(http) -> None:  # type: ignore[no-untyped-def]
    """Profil mit public + private; --insurance any ruft beide ab."""
    # info.json mit zwei Configurations (public + private) für denselben
    # visit_motive.
    info = {
        "data": {
            "profile": {"id": 1, "name_with_title": "Dr. X", "slug": "x"},
            "places": [{"name": "P", "address": "A", "zipcode": "1",
                        "city": "X", "slug": "x",
                        "practice_ids": [99]}],
            "agendas": [{"id": 1, "practice_id": 99,
                          "visit_motive_ids": [10], "booking_temporary_disabled": False}],
            "visit_motives": [{
                "id": 10,
                "name": "Beratung",
                "visit_motive_category_id": None,
                "configurations": [
                    {"insurance": "public", "agenda_id": None,
                     "disabled": False, "online_booking_status": "enabled_for_all"},
                    {"insurance": "private", "agenda_id": None,
                     "disabled": False, "online_booking_status": "enabled_for_all"},
                ],
            }],
            "visit_motive_categories": [],
        },
    }
    http.route(contains="info.json", json_data=info)
    http.route(contains="availabilities.json",
               json_data=availabilities_json())
    code, payload = slots_for_profile("hautarzt/berlin/x", days=7,
                                       insurance="any")
    assert code == 0, payload
    assert set(payload["insurances_queried"]) == {"public", "private"}


def test_slots_invalid_insurance_value() -> None:
    code, payload = slots_for_profile("hautarzt/berlin/test",
                                       days=7, insurance="foo")
    assert code == 1
    assert "--insurance" in payload["error"]["message"]


def test_slots_invalid_days() -> None:
    code, payload = slots_for_profile("hautarzt/berlin/test", days=0)
    assert code == 1
    code, _ = slots_for_profile("hautarzt/berlin/test", days=31)
    assert code == 1


def test_slots_unknown_motive(http) -> None:  # type: ignore[no-untyped-def]
    _setup_slots(http, motive_name="Hautkrebsvorsorge", motive_id=4711)
    code, payload = slots_for_profile("hautarzt/berlin/test-profile",
                                       motive="xyz", days=7, insurance="public")
    assert code == 1
    assert "available_motives" in payload["error"]


def test_slots_motive_id_match(http) -> None:  # type: ignore[no-untyped-def]
    _setup_slots(http, motive_id=4711)
    code, payload = slots_for_profile("hautarzt/berlin/test-profile",
                                       motive="4711", days=7,
                                       insurance="public")
    assert code == 0, payload


def test_slots_motive_substring_match(http) -> None:  # type: ignore[no-untyped-def]
    _setup_slots(http, motive_name="Hautkrebsvorsorge groß")
    code, payload = slots_for_profile("hautarzt/berlin/test-profile",
                                       motive="hautkrebs", days=7,
                                       insurance="public")
    assert code == 0, payload


def test_slots_empty_availabilities(http) -> None:  # type: ignore[no-untyped-def]
    _setup_slots(http)
    # Override availabilities mit leerer Antwort
    http.routes.clear()
    http.route(contains="info.json",
               json_data=info_json(motive_id=4711))
    http.route(contains="availabilities.json",
               json_data=empty_availabilities_json())
    code, payload = slots_for_profile("hautarzt/berlin/test-profile",
                                       days=7, insurance="public")
    # Leer = OK mit total=0, kein Fehler.
    assert code == 0
    assert payload["total"] == 0


def test_slots_404_profile(http) -> None:  # type: ignore[no-untyped-def]
    http.route(contains="info.json", status=404, text="")
    code, payload = slots_for_profile("hautarzt/berlin/missing", days=7)
    assert code == 4
    assert payload["error"]["kind"] == "parse"


def test_slots_disabled_config(http) -> None:  # type: ignore[no-untyped-def]
    """Wenn alle Configurations disabled sind → exit 4 (parse)."""
    info = info_json()
    info["data"]["visit_motives"][0]["configurations"][0]["disabled"] = True
    http.route(contains="info.json", json_data=info)
    code, payload = slots_for_profile("hautarzt/berlin/test-profile",
                                       days=7, insurance="public")
    assert code == 4
    assert payload["error"]["kind"] == "parse"


# ----- watch -------------------------------------------------------------

def test_watch_add_creates_file(tmp_config: Path) -> None:
    code, payload = add_watch("hautarzt/berlin/x",
                              motive="100", before="2026-12-01",
                              insurance="private")
    assert code == 0
    assert payload["id"]
    assert payload["before"] == "2026-12-01"
    assert payload["insurance"] == "private"
    f = tmp_config / "doctolib-cli" / "watch.json"
    assert f.exists()
    data = json.loads(f.read_text())
    assert data["watches"][0]["id"] == payload["id"]


def test_watch_add_is_idempotent_on_same_profile_motive(
        tmp_config: Path) -> None:
    code1, p1 = add_watch("hautarzt/berlin/x", motive="100",
                           before="2026-12-01")
    code2, p2 = add_watch("hautarzt/berlin/x", motive="100",
                           before="2027-01-01", insurance="private")
    assert code1 == 0 and code2 == 0
    assert p1["id"] == p2["id"]
    assert p2.get("updated") is True
    assert p2["before"] == "2027-01-01"
    assert p2["insurance"] == "private"


def test_watch_add_invalid_date(tmp_config: Path) -> None:
    code, payload = add_watch("foo", before="2026/12/01")
    assert code == 1
    assert payload["error"]["kind"] == "usage"


def test_watch_add_empty_profile(tmp_config: Path) -> None:
    code, payload = add_watch("  ")
    assert code == 1


def test_watch_list_empty(tmp_config: Path) -> None:
    code, payload = list_watches()
    assert code == 0
    assert payload["count"] == 0
    assert payload["watches"] == []


def test_watch_remove_known(tmp_config: Path) -> None:
    code, p1 = add_watch("foo/bar")
    wid = p1["id"]
    code, payload = remove_watch(wid)
    assert code == 0
    assert payload["removed"] == 1
    code, payload = list_watches()
    assert payload["count"] == 0


def test_watch_remove_unknown_returns_exit_1(tmp_config: Path) -> None:
    code, payload = remove_watch("deadbeef")
    assert code == 1
    assert payload["error"]["kind"] == "usage"
    assert "deadbeef" in payload["error"]["message"]


def test_watch_remove_empty_id(tmp_config: Path) -> None:
    code, payload = remove_watch("")
    assert code == 1


def test_watch_corrupt_json(tmp_config: Path) -> None:
    """Korrupte watch.json → exit 4."""
    p = tmp_config / "doctolib-cli" / "watch.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("{not valid", encoding="utf-8")
    code, payload = list_watches()
    assert code == 4
    assert payload["error"]["kind"] == "parse"
    assert "korrupt" in payload["error"]["message"]


def test_watch_atomic_write_keeps_good_content(tmp_config: Path) -> None:
    add_watch("foo/bar")
    p = tmp_config / "doctolib-cli" / "watch.json"
    raw = p.read_text()
    data = json.loads(raw)
    assert data["version"] == 1
    assert isinstance(data["watches"], list)


def test_watch_check_empty(tmp_config: Path) -> None:
    """Keine Watches → exit 0, leere Liste."""
    code, payload = check_watches()
    assert code == 0
    assert payload["count"] == 0
    assert payload["hits"] == []


def test_watch_check_persists_last_checked(tmp_config: Path) -> None:
    """Wenn Slots für einen Watch gefunden werden, wird last_checked gespeichert."""
    add_watch("hautarzt/berlin/test-profile", insurance="public")
    # Stub _slots_proxy mit synthetischem Erfolg
    import doctolib_cli.watch as watch_mod
    orig = watch_mod._slots_proxy

    def fake(slug, **kwargs):
        return 0, {
            "availabilities": [{"date": "2026-10-20",
                                 "slots": ["2026-10-20T09:00:00+02:00"]}],
            "total": 1,
            "next_slot": None,
            "reason": None,
            "motive": {"id": 1, "name": "x", "insurance": "public"},
            "profile": {"slug": slug, "practice_id": 1, "url": ""},
            "insurances_queried": ["public"],
            "truncated": False,
        }
    watch_mod._slots_proxy = fake
    try:
        code, payload = check_watches()
    finally:
        watch_mod._slots_proxy = orig
    assert code == 0
    assert payload["count"] == 1
    assert payload["hits"][0]["date"] == "2026-10-20"
    # last_checked persistiert?
    p = tmp_config / "doctolib-cli" / "watch.json"
    data = json.loads(p.read_text())
    assert data["watches"][0]["last_checked"] is not None


def test_watch_check_filters_before_date(tmp_config: Path) -> None:
    add_watch(".../x", before="2026-10-21")
    import doctolib_cli.watch as watch_mod
    orig = watch_mod._slots_proxy

    def fake(slug, **kwargs):
        return 0, {
            "availabilities": [
                {"date": "2026-10-20",
                 "slots": ["2026-10-20T09:00:00+02:00"]},
                {"date": "2026-10-25",
                 "slots": ["2026-10-25T09:00:00+02:00"]},
            ],
            "total": 2,
            "motive": {"id": 1, "name": "x", "insurance": "public"},
            "profile": {"slug": slug, "practice_id": 1, "url": ""},
            "insurances_queried": ["public"],
            "truncated": False,
        }
    watch_mod._slots_proxy = fake
    try:
        _, payload = check_watches()
    finally:
        watch_mod._slots_proxy = orig
    hits = payload["hits"]
    assert len(hits) == 1
    assert hits[0]["date"] == "2026-10-20"


# ----- book ---------------------------------------------------------------

def test_book_always_exit_5_json(capsys) -> None:  # type: ignore[no-untyped-def]
    code = cli.main(["book", "--json"])
    assert code == 5
    out = capsys.readouterr().out
    assert "\"unsupported\"" in out
    assert "\"code\": 5" in out


def test_book_always_exit_5_with_confirm(capsys) -> None:  # type: ignore[no-untyped-def]
    code = cli.main(["book", "foo", "bar", "--confirm", "--json"])
    assert code == 5


def test_book_no_json_text_mode(capsys) -> None:  # type: ignore[no-untyped-def]
    code = cli.main(["book", "foo", "bar", "--confirm"])
    assert code == 5
    err = capsys.readouterr().err
    assert "[unsupported]" in err


# ----- CLI / arg-parser ---------------------------------------------------

def test_cli_version(capsys) -> None:  # type: ignore[no-untyped-def]
    code = cli.main(["--version"])
    assert code == 0
    out = capsys.readouterr().out
    assert out.startswith("doctolib ")


def test_cli_help(capsys) -> None:  # type: ignore[no-untyped-def]
    code = cli.main(["--help"])
    assert code == 0
    out = capsys.readouterr().out
    assert "search" in out


def test_cli_search_missing_args_json(capsys) -> None:  # type: ignore[no-untyped-def]
    code = cli.main(["search", "--json"])
    assert code == 1
    out = capsys.readouterr().out
    assert "\"usage\"" in out


def test_cli_search_invalid_limit_json(capsys) -> None:  # type: ignore[no-untyped-def]
    code = cli.main(["search", "hautarzt", "berlin",
                      "--limit", "0", "--json"])
    assert code == 1


def test_cli_search_limit_51(capsys) -> None:  # type: ignore[no-untyped-def]
    code = cli.main(["search", "hautarzt", "berlin",
                      "--limit", "51", "--json"])
    assert code == 1


def test_cli_search_limit_abc(capsys) -> None:  # type: ignore[no-untyped-def]
    code = cli.main(["search", "hautarzt", "berlin",
                      "--limit", "abc", "--json"])
    assert code == 1


def test_cli_specialities_json(capsys) -> None:  # type: ignore[no-untyped-def]
    code = cli.main(["specialities", "--json"])
    assert code == 0
    out = capsys.readouterr().out
    data = json.loads(out)
    assert "specialities" in data
    assert data["count"] >= 10


def test_cli_watch_add_list_remove_flow(tmp_config,  # type: ignore[no-untyped-def]
                                          capsys) -> None:
    code = cli.main(["watch", "add", "hautarzt/berlin/x",
                      "--before", "2026-12-01", "--json"])
    assert code == 0
    out = capsys.readouterr().out
    data = json.loads(out)
    wid = data["id"]

    code = cli.main(["watch", "list", "--json"])
    assert code == 0
    out = capsys.readouterr().out
    assert wid in out

    code = cli.main(["watch", "remove", wid, "--json"])
    assert code == 0

    # zweiter remove → exit 1
    code = cli.main(["watch", "remove", wid, "--json"])
    assert code == 1