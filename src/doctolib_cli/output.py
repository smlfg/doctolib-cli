"""Lesbare Textausgabe für Menschen (nur bei TTY und ohne --json)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

_DE_WEEKDAYS = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]


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
        d = datetime.strptime(value, "%Y-%m-%d")
    except (TypeError, ValueError):
        return str(value)
    return f"{_DE_WEEKDAYS[d.weekday()]} {d.strftime('%d.%m.%Y')}"


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


def format_search(payload: dict[str, Any]) -> str:
    """Nummerierte Trefferliste inkl. Adresse und Slug."""
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
        address = format_address(rec.get("address"))
        slug = rec.get("slug") or ""
        line = f"[{i}] {name}"
        if kind:
            line += f" – {kind}"
        if address:
            line += f" | {address}"
        if slug:
            line += f" | slug: {slug}"
        lines.append(line)
    count = payload.get("count", len(results))
    lines.append("")
    lines.append(f"{count} Treffer.")
    return "\n".join(lines)


def format_show(record: dict[str, Any]) -> str:
    """Profil-Detail als kompakte, lesbare Blöcke."""
    name = record.get("name") or "?"
    kind = record.get("type") or "Unknown"
    lines = [f"{name} ({kind})"]
    if record.get("speciality"):
        lines.append(f"Fachrichtung: {record['speciality']}")
    if record.get("subtitle"):
        lines.append(str(record["subtitle"]))
    address = format_address(record.get("address"))
    if address:
        lines.append(f"Adresse: {address}")
    for extra in record.get("addresses") or []:
        if not isinstance(extra, dict):
            continue
        addr = format_address(extra)
        if addr and addr != address:
            label = extra.get("name") or "Weitere Adresse"
            lines.append(f"{label}: {addr}")
    motives = record.get("motive") or []
    if motives:
        lines.append("Motive:")
        for m in motives:
            if isinstance(m, dict):
                mid = m.get("id")
                mname = m.get("name") or "?"
                lines.append(f"  - {mid} {mname}" if mid is not None
                             else f"  - {mname}")
    hours = record.get("opening_hours") or []
    if hours:
        lines.append("Öffnungszeiten:")
        for h in hours:
            lines.append(f"  - {h}")
    if record.get("slug"):
        lines.append(f"Slug: {record['slug']}")
    if record.get("url"):
        lines.append(f"URL: {record['url']}")
    return "\n".join(lines)


def format_slots(payload: dict[str, Any]) -> str:
    """Freie Termine als Tage-mit-Uhrzeiten-Liste."""
    profile = payload.get("profile") or {}
    motive = payload.get("motive") or {}
    lines: list[str] = []
    title = profile.get("practice_name") or profile.get("slug") or "Profil"
    lines.append(f"Freie Termine – {title}")
    address = format_address({
        "street": profile.get("practice_address"),
        "postal_code": None,
        "city": None,
    })
    # practice_address ist bei Doctolib bereits eine vollständige Zeile.
    if not address and profile.get("practice_address"):
        address = str(profile["practice_address"])
    if address:
        lines.append(address)
    if profile.get("slug"):
        lines.append(f"Slug: {profile['slug']}")
    if motive.get("name"):
        ins = motive.get("insurance")
        lines.append(f"Motiv: {motive['name']}" + (f" ({ins})" if ins else ""))
    lines.append("")

    availabilities = payload.get("availabilities") or []
    if not availabilities:
        lines.append("(keine freien Termine im Zeitraum)")
    for day in availabilities:
        if not isinstance(day, dict) or not day.get("date"):
            continue
        times = sorted({_format_time(s) for s in (day.get("slots") or [])
                        if _format_time(s)})
        if times:
            lines.append(f"{_format_date(str(day['date']))}: "
                         f"{', '.join(times)}")
    total = payload.get("total", 0)
    lines.append("")
    lines.append(f"{total} Termin(e).")
    if payload.get("reason"):
        lines.append(f"Hinweis: {payload['reason']}")
    return "\n".join(lines)


__all__ = ["format_address", "format_search", "format_show", "format_slots"]
