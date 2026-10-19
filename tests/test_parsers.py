"""Tests für Parser und Helper (kein Netz)."""

from __future__ import annotations

import json

from doctolib_cli.search import (
    _LdJsonExtractor,
    _extract_collection,
    _extract_window_place,
    _item_to_record,
    _provider_to_record,
    _slugify_location,
)
from doctolib_cli.show import (
    _load_ld_json_profile,
    _slug_from_input,
)
from doctolib_cli.specialities import (
    SPECIALITIES,
    list_specialities,
    resolve_speciality,
)
from doctolib_cli.slots import (
    _filter_configs_by_insurance,
    _match_motive,
    _resolve_insurance,
    INSURANCE_BY_ALIAS,
)

from .fixtures.builders import (
    profile_html,
    search_html_berlin,
)


# ----- search parser ------------------------------------------------------

def test_slugify_location_basic() -> None:
    assert _slugify_location("Heilbronn") == "heilbronn"
    assert _slugify_location("Bad Homburg") == "bad-homburg"
    assert _slugify_location("Müller-Str.") == "mueller-str"
    assert _slugify_location("Straße") == "strasse"
    assert _slugify_location("  Frankfurt am Main  ") == "frankfurt-am-main"
    assert _slugify_location("---") == ""  # komplett strip-bares → leer


def test_ldjson_extractor_recognizes_blocks() -> None:
    html = search_html_berlin([
        {"name": "Dr. A", "url": "/hautarzt/berlin/dr-a"},
        {"name": "Dr. B", "url": "/hautarzt/berlin/dr-b"},
    ])
    ext = _LdJsonExtractor()
    ext.feed(html)
    assert len(ext.ldjsons) == 2  # BreadcrumbList + CollectionPage
    types = [o.get("@type") for o in ext.ldjsons]
    assert "BreadcrumbList" in types
    assert "CollectionPage" in types


def test_extract_collection_returns_items() -> None:
    html = search_html_berlin([
        {"name": "Dr. A", "url": "/hautarzt/berlin/dr-a",
         "street": "Hauptstr. 1", "postal_code": "10115",
         "motive": "Akne-Behandlung"},
    ])
    items = _extract_collection(html)
    assert len(items) == 1
    assert items[0]["item"]["name"] == "Dr. A"


def test_extract_collection_empty_on_no_block() -> None:
    html = "<html><body></body></html>"
    assert _extract_collection(html) == []


def test_extract_collection_tolerates_malformed_json() -> None:
    html = (
        "<html><body>"
        '<script type="application/ld+json">{not valid</script>'
        "</body></html>"
    )
    assert _extract_collection(html) == []


def test_item_to_record_extracts_pid() -> None:
    rec = _item_to_record({
        "item": {
            "@type": "Physician",
            "name": "Dr. A",
            "url": "/hautarzt/berlin/dr-a?pid=practice-635395",
            "address": {"streetAddress": "Hauptstr. 1",
                        "postalCode": "10115",
                        "addressLocality": "Berlin"},
            "availableService": {"name": "Akne"},
        },
    })
    assert rec is not None
    assert rec["name"] == "Dr. A"
    assert rec["practice_id"] == 635395
    assert rec["address"]["city"] == "Berlin"
    assert rec["slug"] == "hautarzt/berlin/dr-a"


def test_item_to_record_rejects_missing_name() -> None:
    rec = _item_to_record({"item": {"url": "/foo"}})
    assert rec is None


def test_item_to_record_accepts_dict_without_inner_item() -> None:
    rec = _item_to_record({
        "@type": "Physician",
        "name": "Dr. B",
        "url": "/hautarzt/berlin/dr-b",
    })
    assert rec is not None
    assert rec["name"] == "Dr. B"


def test_extract_window_place_from_inline_script() -> None:
    html = (
        "<html><body><script>window.place = "
        '{"id": 1, "name": "Heilbronn", "slug": "heilbronn"};'
        "</script></body></html>"
    )
    place = _extract_window_place(html)
    assert place is not None
    assert place["slug"] == "heilbronn"


def test_provider_to_record_maps_phs_shape() -> None:
    rec = _provider_to_record({
        "name": "Dr. Zahn",
        "type": "PERSON",
        "link": "/zahnarzt/heilbronn/dr-zahn?pid=practice-99",
        "location": {"address": "Hauptstr. 1", "zipcode": "74072",
                     "city": "Heilbronn"},
        "matchedVisitMotive": {"name": "Kontrolle"},
        "references": {"practiceId": 99},
    })
    assert rec is not None
    assert rec["type"] == "Physician"
    assert rec["address"]["city"] == "Heilbronn"
    assert rec["practice_id"] == 99


# ----- show parser --------------------------------------------------------

def test_slug_from_input_keeps_slug() -> None:
    assert _slug_from_input("hautarzt/berlin/test") == "hautarzt/berlin/test"


def test_slug_from_input_strips_url() -> None:
    s = _slug_from_input("https://www.doctolib.de/hautarzt/berlin/test?pid=practice-1")
    assert s == "hautarzt/berlin/test"


def test_slug_from_input_rejects_non_doctolib_host() -> None:
    assert _slug_from_input("https://evil.example/foo") is None


def test_slug_from_input_rejects_no_slash() -> None:
    assert _slug_from_input("just-a-name") is None


def test_load_ld_json_profile_finds_physician() -> None:
    html = profile_html(name="Dr. Test", slug="hautarzt/berlin/test")
    obj = _load_ld_json_profile(html)
    assert obj is not None
    assert obj["name"] == "Dr. Test"


def test_load_ld_json_profile_returns_none_for_empty() -> None:
    assert _load_ld_json_profile("<html></html>") is None


# ----- specialities -------------------------------------------------------

def test_specialities_count_at_least_10() -> None:
    items = list_specialities()
    assert len(items) >= 10
    for it in items:
        assert "slug" in it and "name" in it
        assert it["slug"] == it["slug"].lower()
        assert "_" not in it