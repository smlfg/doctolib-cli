"""search-Handler: Doctolib-Trefferliste live abrufen.

Strategie: Die Suchseite wird per Playwright headless geladen (Doctolib
rendert die Treffer erst nach Microfrontend-JS-Hydration). Im DOM ist die
CollectionPage als `application/ld+json` vollständig vorhanden und liefert
20–30 Treffer strukturiert.

Eine reine `requests`-Variante ist nicht möglich: Doctolib liefert nur
BreadcrumbList im initialen HTML, die Microfrontend-API erwartet eine
komplexe Google-Places-POST-Payload + CSRF-Token. Playwright spart das
Reverse-Engineering.
"""

from __future__ import annotations

import json
import logging
import re
from html.parser import HTMLParser
from typing import Any

LOG = logging.getLogger("doctolib_cli.search")

PLAYWRIGHT_TIMEOUT_S = 30.0


def _slugify_location(value: str) -> str:
    s = value.strip().lower()
    s = (s.replace("ä", "ae").replace("ö", "oe").replace("ü", "ue")
           .replace("ß", "ss"))
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s


def _practice_id_from_url(url: str) -> int | None:
    m = re.search(r"pid=practice-(\d+)", url)
    return int(m.group(1)) if m else None


class _LdJsonExtractor(HTMLParser):
    """Sammelt alle <script type="application/ld+json">-Inhalte."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.ldjsons: list[dict[str, Any]] = []
        self._buf: list[str] = []
        self._in_ld = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "script":
            d = dict(attrs)
            if d.get("type") == "application/ld+json":
                self._in_ld = True
                self._buf = []

    def handle_endtag(self, tag: str) -> None:
        if tag == "script" and self._in_ld:
            raw = "".join(self._buf).strip()
            if raw:
                try:
                    obj = json.loads(raw)
                    if isinstance(obj, dict):
                        self.ldjsons.append(obj)
                except json.JSONDecodeError as exc:
                    LOG.debug("ld+json parse fail: %s", exc)
            self._in_ld = False
            self._buf = []

    def handle_data(self, data: str) -> None:
        if self._in_ld:
            self._buf.append(data)


def _extract_collection(html: str) -> list[dict[str, Any]]:
    """Sucht den CollectionPage-Block und gibt die ItemList zurück."""
    ext = _LdJsonExtractor()
    try:
        ext.feed(html)
    except Exception as exc:  # Parser-Fehler
        LOG.debug("HTMLParser error: %s", exc)
    for obj in ext.ldjsons:
        if not isinstance(obj, dict):
            continue
        if obj.get("@type") != "CollectionPage":
            continue
        me = obj.get("mainEntity")
        if not isinstance(me, dict):
            continue
        if me.get("@type") != "ItemList":
            continue
        items = me.get("itemListElement")
        if isinstance(items, list) and items:
            return items
    return []


def _item_to_record(item: Any) -> dict[str, Any] | None:
    if not isinstance(item, dict):
        return None
    inner_any = item.get("item")
    inner: dict[str, Any] = inner_any if isinstance(inner_any, dict) else item
    name = inner.get("name")
    url = inner.get("url")
    if not name or not url:
        return None
    addr_any = inner.get("address") or {}
    addr: dict[str, Any] = addr_any if isinstance(addr_any, dict) else {}
    motive_any = inner.get("availableService") or {}
    motive: dict[str, Any] = motive_any if isinstance(motive_any, dict) else {}
    return {
        "name": name,
        "type": inner.get("@type") or "Unknown",
        "address": {
            "street": addr.get("streetAddress"),
            "postal_code": addr.get("postalCode"),
            "city": addr.get("addressLocality"),
        },
        "motive": motive.get("name"),
        "slug": url.lstrip("/").split("?")[0],
        "url": f"https://www.doctolib.de{url}" if url.startswith("/") else url,
        "practice_id": _practice_id_from_url(url),
    }


def search_speciality_location(speciality: str, location: str,
                               *, limit: int = 20,
                               base_url: str = "https://www.doctolib.de",
                               ) -> tuple[int, dict[str, Any]]:
    """Suche. (exit_code, payload). 0=OK, 1=usage, 3=network, 4=parse."""
    if not speciality or not speciality.strip():
        return 1, {"error": {"kind": "usage", "code": 1,
                              "message": "speciality fehlt"}}
    if not location or not location.strip():
        return 1, {"error": {"kind": "usage", "code": 1,
                              "message": "location fehlt"}}
    if not isinstance(limit, int) or limit < 1 or limit > 50:
        return 1, {"error": {"kind": "usage", "code": 1,
                              "message": "--limit muss 1..50 sein"}}

    from .specialities import resolve_speciality
    sp_slug = resolve_speciality(speciality)
    if not sp_slug:
        return 1, {"error": {"kind": "usage", "code": 1,
                              "message": (f"unbekannte Fachrichtung: {speciality!r} "
                                          "(siehe `doctolib specialities`)")}}
    loc_slug = _slugify_location(location)
    if not loc_slug:
        return 1, {"error": {"kind": "usage", "code": 1,
                              "message": f"Ort nicht parsebar: {location!r}"}}

    url = f"{base_url.rstrip('/')}/{sp_slug}/{loc_slug}"
    try:
        html = _fetch_search_html(url)
    except _SearchFetchError as exc:
        return exc.code, {"error": {"kind": exc.kind, "code": exc.code,
                                     "message": str(exc)}}

    if html is None:
        return 3, {"error": {"kind": "network", "code": 3,
                              "message": f"Doctolib liefert nichts für {url}"}}

    items = _extract_collection(html)
    if not items:
        return 4, {"error": {"kind": "parse", "code": 4,
                              "message": ("keine ItemList im ld+json "
                                          "(Doctolib-Layout geändert?)")}}

    records: list[dict[str, Any]] = []
    for it in items[:limit]:
        rec = _item_to_record(it)
        if rec is not None:
            records.append(rec)

    return 0, {
        "query": {"speciality": sp_slug, "location": loc_slug,
                  "speciality_input": speciality, "location_input": location},
        "count": len(records),
        "results": records,
    }


class _SearchFetchError(Exception):
    def __init__(self, code: int, kind: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.kind = kind


def _fetch_search_html(url: str) -> str | None:
    """Lädt die Suchseite via Playwright headless."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise _SearchFetchError(
            3, "network",
            f"Playwright nicht installiert: {exc}. "
            "Installiere mit `pip install playwright && playwright install chromium`."
        ) from exc

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            try:
                ctx = browser.new_context(
                    user_agent=("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                                "(KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36"),
                    locale="de-DE",
                    extra_http_headers={"Accept-Language": "de-DE,de;q=0.9,en;q=0.8"},
                )
                page = ctx.new_page()
                resp = page.goto(url, wait_until="domcontentloaded",
                                 timeout=PLAYWRIGHT_TIMEOUT_S * 1000)
                if resp is None:
                    raise _SearchFetchError(3, "network",
                                            f"keine Antwort von {url}")
                status = resp.status
                if status == 404:
                    raise _SearchFetchError(3, "network",
                                            "kein Doctolib-Pass für diese "
                                            "Fach/Ort-Kombination (HTTP 404)")
                if status >= 400:
                    raise _SearchFetchError(3, "network",
                                            f"Doctolib HTTP {status}")
                # Microfrontend braucht etwas Zeit zum Hydraten – wir warten
                # höchstens 5 s, danach geben wir das aktuelle HTML zurück
                # (ld+json ist bei Doctolib bereits im initialen SSR).
                try:
                    page.wait_for_selector('script[type="application/ld+json"]',
                                            timeout=5000)
                except Exception:
                    pass
                return page.content()
            finally:
                browser.close()
    except _SearchFetchError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise _SearchFetchError(3, "network",
                                f"Browser-Fehler: {exc.__class__.__name__}: {exc}") from exc