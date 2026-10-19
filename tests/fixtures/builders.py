"""HTML/JSON-Builder für die Test-Fixtures."""

from __future__ import annotations

import json
from typing import Any


def search_html_berlin(results: list[dict[str, Any]],
                        city_name: str = "Berlin") -> str:
    """Baut eine Doctolib-Such-HTML-Seite mit ItemList-ld+json."""
    items: list[dict[str, Any]] = []
    for r in results:
        items.append({
            "@type": "ListItem",
            "position": r.get("position", 1),
            "item": {
                "@type": r.get("type", "Physician"),
                "name": r["name"],
                "url": r["url"],
                "address": {
                    "@type": "PostalAddress",
                    "streetAddress": r.get("street", "Musterstr. 1"),
                    "postalCode": r.get("postal_code", "10115"),
                    "addressLocality": r.get("city", city_name),
                },
                "availableService": {"@type": "MedicalProcedure",
                                    "name": r.get("motive", "Allgemein")},
                "image": "res.cloudinary.com/doctolib/image/upload/sample.jpg",
            },
        })
    collection = {
        "@context": "https://schema.org",
        "@type": "CollectionPage",
        "name": f"{city_name} – Suchergebnisse",
        "mainEntity": {
            "@type": "ItemList",
            "itemListElement": items,
        },
    }
    breadcrumb = {
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        "itemListElement": [{"@type": "ListItem", "position": 1,
                             "name": "Start", "item": "https://www.doctolib.de/"}],
    }
    return (
        "<html><head><title>Doctolib – Suche</title></head><body>"
        f'<script type="application/ld+json">{json.dumps(breadcrumb)}</script>'
        f'<script type="application/ld+json">{json.dumps(collection)}</script>'
        "</body></html>"
    )


def profile_html(name: str = "Dr. Maria Test",
                  slug: str = "hautarzt/berlin/test-profile",
                  address: dict[str, Any] | None = None) -> str:
    """Baut eine Doctolib-Profilseite mit ld+json Physician-Block."""
    address = address or {"streetAddress": "Teststr. 42",
                          "postalCode": "10115",
                          "addressLocality": "Berlin"}
    physician = {
        "@context": "https://schema.org",
        "@type": "Physician",
        "name": name,
        "url": f"https://www.doctolib.de/{slug}",
        "address": {"@type": "PostalAddress", **address},
        "availableService": [{"@type": "MedicalProcedure",
                              "name": "Hautkrebsvorsorge"}],
        "openingHours": ["Mo 08:00-13:00"],
        "image": "res.cloudinary.com/doctolib/image/upload/test.jpg",
    }
    return (
        "<html><head><title>Profil</title></head><body>"
        f'<script type="application/ld+json">{json.dumps(physician)}</script>'
        "</body></html>"
    )


def info_json(profile_slug: str = "test-profile",
               motive_name: str = "Hautkrebsvorsorge",
               motive_id: int = 4711,
               practice_id: int = 635395,
               agenda_id: int = 4321,
               insurance: str = "public",
               online_status: str = "enabled_for_all") -> dict[str, Any]:
    """info.json-Daten für ``online_booking/.../info.json``."""
    return {
        "data": {
            "profile": {
                "id": 12345,
                "name_with_title": "Dr. Maria Test",
                "slug": profile_slug,
                "speciality": {"name": "Hautarzt"},
                "subtitle": "Hautärztin in Berlin",
            },
            "places": [{
                "name": "Praxis Mitte",
                "address": "Teststr. 42",
                "zipcode": "10115",
                "city": "Berlin",
                "slug": profile_slug,
                "practice_ids": [practice_id],
            }],
            "agendas": [{
                "id": agenda_id,
                "practice_id": practice_id,
                "visit_motive_ids": [motive_id],
                "booking_temporary_disabled": False,
            }],
            "visit_motives": [{
                "id": motive_id,
                "name": motive_name,
                "visit_motive_category_id": None,
                "configurations": [{
                    "insurance": insurance,
                    "agenda_id": None,
                    "disabled": False,
                    "online_booking_status": online_status,
                }],
            }],
            "visit_motive_categories": [],
        }
    }


def availabilities_json(dates: list[str] | None = None,
                         slots_per_day: int = 3) -> dict[str, Any]:
    """availabilities.json mit Datum + ISO8601-Slots."""
    if dates is None:
        dates = ["2026-10-20", "2026-10-21", "2026-10-22"]
    out: list[dict[str, Any]] = []
    for d in dates:
        slots = [f"{d}T09:00:00.000+02:00",
                 f"{d}T10:00:00.000+02:00",
                 f"{d}T11:00:00.000+02:00"][:slots_per_day]
        out.append({"date": d, "slots": slots})
    return {"availabilities": out, "total": sum(len(d["slots"])
                                                for d in out),
            "next_slot": "2026-10-20T09:00:00.000+02:00"}


def empty_availabilities_json(reason: str = "no_availability") -> dict[str, Any]:
    return {"availabilities": [], "total": 0, "reason": reason}


__all__ = [
    "search_html_berlin", "profile_html", "info_json",
    "availabilities_json", "empty_availabilities_json",
]