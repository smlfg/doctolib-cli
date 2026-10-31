"""Lesbare Textausgabe für Menschen (nur bei TTY und ohne --json)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

_DE_WEEKDAYS = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]

MAX_TIMES_PER_LINE = 8


def format_address(address: Any) -> str:
    """Formatiert ``street``/``postal_code``/``city`` als eine Zeile."""
    if not isinstance(address, dict):
        return ""
    street = (address.get("street") or "").strip()
    plz = (address.get("postal_code") or "").strip()
    city = (address.get("city") or "").strip()
    city_line = " ".join(part for part in (plz, city) if part)
    return ", ".join(part for part in (street, city_line) if part)


def _format_date(value: str) -> str:
    try:
        d = datetime.strptime(value[:10], "%Y-%m-%d")
    except (TypeError, ValueError):
        return str(value)
    return f"{_DE_WEEKDAYS[d.weekday()]} {d.day:02d}.{d.month:02d}."


def _format_time(value: Any) -> str:
    s = str(value or "")
    if not s:
        return ""
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00")).strftime("%H:%M")
    except ValueError:
        if "T" in s:
            return s.split("T", 1)[1][:5]
        return s


def format_search(payload: dict[str, Any], *, verbose: bool = False) -> str:
    """Nummerierte Trefferliste: „ 1. Name – Fach“, Adresse eingerückt.

    Der Slug erscheint nur mit ``verbose`` (``-v``/``--verbose``).
    """
    query = payload.get("query") or {}
    lines: list[str] = []
    if query:
        speciality = query.get("speciality") or query.get("speciality_input")
        location = query.get("location") or query.get("location_input")
        if speciality or location:
            lines.append(f"Suche: {speciality or '?'} in {location or '?'}")
            lines.append("")
    results = payload.get("results") or []
    if not results:
        lines.append("(keine Treffer)")
    for i, rec in enumerate(results, 1):
        if not isinstance(rec, dict):
            continue
        name = rec.get("name") or "?"
        kind = rec.get("motive") or rec.get("type") or ""
        line = f"{i:>2}. {name}"
        if kind:
            line += f" – {kind}"
        lines.append(line)
        address = format_address(rec.get("address"))
        if address:
            lines.append(f"    {address}")
        if verbose and rec.get("slug"):
            lines.append(f"    slug: {rec['slug']}")
    count = payload.get("count", len(results))
    lines.append("")
    lines.append(f"{count} Treffer.")
    return "\n".join(lines)


def format_show(record: dict[str, Any], *, verbose: bool = False) -> str:
    """Kompakte Profil-Ansicht.

    Name, Fach, Adresse, Telefon (falls vorhanden), Online-Buchung ja/nein,
    Link. Der Slug erscheint zusätzlich nur mit ``verbose``.
    """
    name = record.get("name") or "?"
    lines = [str(name)]
    if record.get("speciality"):
        lines.append(f"Fach: {record['speciality']}")
    address = format_address(record.get("address"))
    if address:
        lines.append(f"Adresse: {address}")
    telephone = str(record.get("telephone") or "").strip()
    if telephone:
        lines.append(f"Telefon: {telephone}")
    online = bool(record.get("practice_id")) or any(
        isinstance(m, dict) and m.get("id")
        for m in (record.get("motive") or [])
    )
    lines.append(f"Online-Buchung: {'ja' if online else 'nein'}")
    if record.get("url"):
        lines.append(f"Link: {record['url']}")
    if verbose and record.get("slug"):
        lines.append(f"Slug: {record['slug']}")
    return "\n".join(lines)


def format_slots(payload: dict[str, Any], *, verbose: bool = False) -> str:
    """Freie Termine kompakt: je Tag „Di 03.11.: 09:00, 10:30“.

    Maximal ``MAX_TIMES_PER_LINE`` Uhrzeiten pro Zeile; lange Zeilen
    fortgeführt. Kontext (Praxis, Motiv, Slug, Zähler) nur mit ``verbose``.
    """
    profile = payload.get("profile") or {}
    motive = payload.get("motive") or {}
    lines: list[str] = []
    if verbose:
        title = profile.get("practice_name") or profile.get("slug") or "Profil"
        lines.append(f"Freie Termine – {title}")
        address = str(profile.get("practice_address") or "").strip()
        if address:
            lines.append(address)
        if profile.get("slug"):
            lines.append(f"Slug: {profile['slug']}")
        if motive.get("name"):
            ins = motive.get("insurance")
            lines.append(f"Motiv: {motive['name']}"
                         + (f" ({ins})" if ins else ""))
        lines.append("")

    availabilities = payload.get("availabilities") or []
    if not availabilities:
        lines.append("(keine freien Termine im Zeitraum)")
    for day in availabilities:
        if not isinstance(day, dict) or not day.get("date"):
            continue
        times = [t for t in sorted({_format_time(s)
                                    for s in (day.get("slots") or [])}) if t]
        if not times:
            continue
        label = _format_date(str(day['date']))
        chunks = [times[i:i + MAX_TIMES_PER_LINE]
                  for i in range(0, len(times), MAX_TIMES_PER_LINE)]
        lines.append(f"{label}: {', '.join(chunks[0])}")
        indent = " " * (len(label) + 2)
        for chunk in chunks[1:]:
            lines.append(f"{indent}{', '.join(chunk)}")

    if verbose:
        total = payload.get("total", 0)
        lines.append("")
        lines.append(f"{total} Termin(e).")
    if payload.get("reason"):
        lines.append(f"Hinweis: {payload['reason']}")
    return "\n".join(lines)


__all__ = [
    "MAX_TIMES_PER_LINE",
    "format_address",
    "format_search",
    "format_show",
    "format_slots",
]
