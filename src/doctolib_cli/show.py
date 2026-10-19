"""show-Handler: Doctolib-Profil live auslesen.

Datenquellen:

1. Profil-HTML → ``application/ld+json`` (`Physician`/`MedicalOrganization`).
   Liefert: Name, Typ, (Haupt-)Adresse, Image, availableService-Namen,
   openingHours, URL.
2. Online-Booking-API
   ``https://www.doctolib.de/online_booking/api/slot_selection_funnel/v1/info.json``
   liefert zusätzlich ``places`` (mehrere Praxen mit Adressen, inkl.
   ``practice_ids``), ``visit_motives`` (mit ID + Name),
   ``visit_motive_categories`` und ``agendas`` (mit ``agenda_id`` +
   verknüpften ``visit_motive_ids`` + ``practice_id``).

Beide Quellen sind ohne Playwright erreichbar. Wir kombinieren sie zu
einem Record; Fehlen einzelner Felder ist erlaubt (nie erfinden).
"""

from __future__ import annotations

import json
import logging
import re
from html.parser import HTMLParser
from typing import Any
from urllib.parse import urlparse, urlunparse

from .http import HttpError, get_json, get_text
from .search import _LdJsonExtractor  # reuse Parser

LOG = logging.getLogger("doctolib_cli.show")


def _slug_from_input(value: str) -> str | None:
    """Akzeptiert Slug oder volle URL.

    - ``hautarzt/berlin/kosar-hedayat``         → 그대로
    - ``https://www.doctolib.de/hautarzt/berlin/kosar-hedayat?pid=...`` → ``hautarzt/berlin/kosar-hedayat``
    - alles ohne ``/`` oder ohne doctolib-Host → ``None``
    """
    if not value:
        return None
    v = value.strip()
    if not v:
        return None
    if v.startswith("http://") or v.startswith("https://"):
        try:
            p = urlparse(v)
        except ValueError:
            return None
        if not p.netloc.endswith("doctolib.de"):
            return None
        path = p.path.lstrip("/")
        return path.rstrip("/") or None
    if "/" in v:
        return v.strip("/")
    return None


def _short_slug(full: str) -> str:
    """Aus ``hautarzt/berlin/kosar-hedayat`` den letzten Pfadteil ziehen."""
    if not full:
        return ""
    return full.rsplit("/", 1)[-1]


def _load_ld_json_profile(html: str) -> dict[str, Any] | None:
    """Gibt den ersten Physician/MedicalOrganization-Block zurück."""
    ext = _LdJsonExtractor()
    try:
        ext.feed(html)
    except Exception as exc:  # Parser-Fehler
        LOG.debug("HTMLParser error: %s", exc)
    for obj in ext.ldjsons:
        if not isinstance(obj, dict):
            continue
        t = obj.get("@type")
        if t in ("Physician", "MedicalOrganization", "Organization",
                 "LocalBusiness"):
            return obj
    return None


def _load_info_json(profile_slug: str,
                    base_url: str = "https://www.doctolib.de") -> dict[str, Any] | None:
    """Lädt Online-Booking-Info. ``None`` wenn Endpoint nicht verfügbar."""
    short = _short_slug(profile_slug)
    info_url = (
        f"{base_url.rstrip('/')}/online_booking/api/slot_selection_funnel/v1/info.json"
        f"?profile_slug={short}&locale=de"
    )
    try:
        _, payload = get_json(info_url, referer=f"{base_url.rstrip('/')}/{profile_slug}")
    except HttpError as exc:
        LOG.debug("info.json: %s", exc)
        return None
    if isinstance(payload, dict) and isinstance(payload.get("data"), dict):
        return payload["data"]
    return None


def _normalize_record(ld: dict[str, Any],
                      info: dict[str, Any] | None,
                      profile_slug: str) -> dict[str, Any]:
    """Baut das JSON-konforme Record aus beiden Quellen."""
    # Adresse aus ld+json (Hauptadresse)
    addr_any = ld.get("address") or {}
    addr: dict[str, Any] = addr_any if isinstance(addr_any, dict) else {}
    address: dict[str, Any] = {
        "street": addr.get("streetAddress"),
        "postal_code": addr.get("postalCode"),
        "city": addr.get("addressLocality"),
        "name": addr.get("name"),
    }

    visit_motives: list[dict[str, Any]] = []
    addresses: list[dict[str, Any]] = []
    practice_ids: list[int] = []
    profile_id: int | None = None

    if info:
        prof = info.get("profile") or {}
        if isinstance(prof.get("id"), int):
            profile_id = prof["id"]
        # visit_motives (mit ID)
        for m in info.get("visit_motives") or []:
            if not isinstance(m, dict):
                continue
            mid = m.get("id")
            name = m.get("name")
            if not isinstance(mid, int) or not name:
                continue
            tmpl = {"id": mid, "name": name}
            cat_id = m.get("visit_motive_category_id")
            if isinstance(cat_id, int):
                for c in info.get("visit_motive_categories") or []:
                    if isinstance(c, dict) and c.get("id") == cat_id:
                        if c.get("name"):
                            tmpl["category"] = c["name"]
                        break
            visit_motives.append(tmpl)
        # places → practice_ids + alle Adressen
        for p in info.get("places") or []:
            if not isinstance(p, dict):
                continue
            addresses.append({
                "name": p.get("name"),
                "street": p.get("address"),
                "postal_code": p.get("zipcode"),
                "city": p.get("city"),
                "practice_ids": p.get("practice_ids") or [],
                "slug": p.get("slug"),
            })
            for pid in p.get("practice_ids") or []:
                if isinstance(pid, int) and pid not in practice_ids:
                    practice_ids.append(pid)

    # availableService-Namen (aus ld+json, IDs nicht enthalten)
    motives_ld: list[str] = []
    for s in (ld.get("availableService") or []):
        if isinstance(s, dict) and s.get("name"):
            motives_ld.append(s["name"])
        elif isinstance(s, str):
            motives_ld.append(s)

    # Wenn info.json keine visit_motives brachte, wenigstens die Namen aus ld+json melden
    if visit_motives:
        motives_out = visit_motives
    elif motives_ld:
        motives_out = [{"id": None, "name": n} for n in motives_ld]
    else:
        motives_out = []

    # Profile-URL (kanonisch)
    base = "https://www.doctolib.de"
    pid_qs = ""
    if practice_ids:
        pid_qs = f"?pid=practice-{practice_ids[0]}"
    elif profile_id:
        # URL sieht ?pid=practice-NXX nicht vor; lassen wir weg
        pid_qs = ""
    profile_url = f"{base}/{profile_slug}{pid_qs}"

    return {
        "name": ld.get("name"),
        "type": ld.get("@type") or "Unknown",
        "address": address,
        "addresses": addresses,
        "image": _cloudinary_url(ld.get("image")),
        "subtitle": (info.get("profile") or {}).get("subtitle") if info else None,
        "speciality": _speciality(info),
        "motive": motives_out,
        "opening_hours": ld.get("openingHours") or [],
        "slug": profile_slug,
        "profile_id": profile_id,
        "practice_id": practice_ids[0] if practice_ids else None,
        "practice_ids": practice_ids,
        "url": profile_url,
    }


def _cloudinary_url(value: Any) -> str | None:
    """Doctolib liefert Cloudinary-Pfade ohne Scheme → https:// davor."""
    if not value or not isinstance(value, str):
        return None
    v = value.strip()
    if v.startswith("http://") or v.startswith("https://"):
        return v
    if v.startswith("//"):
        return "https:" + v
    return f"https://res.cloudinary.com/doctolib/image/upload/q_auto:eco,f_auto/{v}"


def _speciality(info: dict[str, Any] | None) -> str | None:
    if not info:
        return None
    prof = info.get("profile") or {}
    sp = prof.get("speciality")
    if isinstance(sp, dict):
        return sp.get("name") or sp.get("alternate_name")
    return None


def show_profile(slug_or_url: str,
                 *, base_url: str = "https://www.doctolib.de"
                 ) -> tuple[int, dict[str, Any]]:
    """Lädt ein Doctolib-Profil. (exit_code, payload)."""
    if not slug_or_url or not slug_or_url.strip():
        return 1, {"error": {"kind": "usage", "code": 1,
                             "message": "Slug oder URL fehlt"}}
    slug = _slug_from_input(slug_or_url)
    if not slug:
        return 1, {"error": {"kind": "usage", "code": 1,
                             "message": f"Slug/URL nicht parsebar: {slug_or_url!r}"}}
    if not re.fullmatch(r"[a-z0-9][a-z0-9_\-]*(/[a-z0-9][a-z0-9_\-]*)+", slug):
        # Fall: nur ein kurzer Slug ("kosar-hedayat") → als solcher akzeptieren
        if not re.fullmatch(r"[a-z0-9][a-z0-9_\-]+", slug):
            return 1, {"error": {"kind": "usage", "code": 1,
                                 "message": f"Slug/URL nicht parsebar: {slug_or_url!r}"}}

    profile_url = f"{base_url.rstrip('/')}/{slug}"
    try:
        status, html = get_text(profile_url)
    except HttpError as exc:
        return exc.code, {"error": {"kind": exc.kind, "code": exc.code,
                                    "message": str(exc)}}
    if status in (404, 410):
        return 4, {"error": {"kind": "parse", "code": 4,
                             "message": (f"Doctolib kennt dieses Profil nicht "
                                         f"(HTTP {status}): {slug}")}}
    if status >= 400:
        return 3, {"error": {"kind": "network", "code": 3,
                             "message": f"Doctolib HTTP {status} für {slug}"}}
    if status >= 300:
        # Doctolib redirected (z. B. /hautarzt/... → /arzt/...); ohne
        # playwright kennen wir das Ziel nicht. Wir nehmen, was kam.
        LOG.debug("Profil-HTML lieferte HTTP %d für %s", status, slug)


    ld = _load_ld_json_profile(html)
    if not ld:
        return 4, {"error": {"kind": "parse", "code": 4,
                             "message": "kein ld+json Physician/Organization-Block auf der Profilseite"}}

    info = _load_info_json(slug, base_url=base_url)
    record = _normalize_record(ld, info, slug)
    return 0, record


__all__ = ["show_profile", "_slug_from_input"]
