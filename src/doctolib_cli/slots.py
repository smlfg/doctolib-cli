"""slots-Handler: freie Doctolib-Termine abfragen.

Strategie:

1. Slug parsen (URL oder ``spec/city/name``).
2. ``info.json`` (Online-Booking-API) holen → ``places``/``agendas``/
   ``visit_motives`` plus das ``configuration``-Mapping (welche
   Kombination aus ``agenda_id`` + ``visit_motive_id`` ist für welche
   Versicherungsart ``public``/``private`` aktiv geschaltet).
3. ``--motive ID|TEXT`` auflösen:
   - numerisch → visit_motive.id
   - sonst case-insensitive substring match auf visit_motive.name.
     Kein Treffer → ``exit 1`` mit ``{available_motives:[...]}``.
4. Für jedes ``(visit_motive, agenda, practice, insurance)``-Tupel, das
   eine **enabled**-Konfiguration hat (also nicht ``disabled`` und
   mit ``online_booking_status in ('enabled_for_all', 'enabled_for_existing_only')``)
   genau ein ``availabilities.json``-Call.
5. Antworten aggregieren → JSON-Record wie im INTERFACE beschrieben.

Wenn Doctolib ``HTTP 400`` mit Hinweis auf fehlendes ``visit_motive_id``
liefert, geben wir ``exit 1`` mit ``Motiv angeben mit --motive``-Hinweis
aus (lt. INTERFACE.md). Doctolibs Praxis ist aber: liefert 200 + leere
Liste; das fangen wir ab, indem wir im ersten Schritt prüfen, ob es
überhaupt ein buchbares Tupel gibt.
"""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone, timedelta
from typing import Any
from urllib.parse import quote

from .http import HttpError, get_json
from .show import _slug_from_input

LOG = logging.getLogger("doctolib_cli.slots")

DEFAULT_INSURANCE = "public"
INSURANCE_BY_ALIAS = {"gesetzlich": "public", "privat": "private",
                      "public": "public", "private": "private",
                      "pkv": "private", "gkv": "public"}


def _resolve_local_tz() -> Any:
    """Lokale TZ aus dem System (Fallback +02:00 wie Berlin)."""
    import time as _t
    offset = -(_t.altzone if _t.daylight else _t.timezone)
    # ``time``-Modul liefert Sekunden östlich von UTC als negative Zahl,
    # timedelta erwartet das aber genau so.
    return timezone(timedelta(seconds=offset))


def _now_iso(tz: Any | None = None) -> str:
    tz = tz or _resolve_local_tz()
    return datetime.now(tz).replace(microsecond=0).isoformat()


def _practice_id_from_url(url: str) -> int | None:
    m = re.search(r"pid=practice-(\d+)", url or "")
    return int(m.group(1)) if m else None


def _load_info(slug: str, *, base_url: str = "https://www.doctolib.de"
               ) -> dict[str, Any] | None:
    short = slug.rsplit("/", 1)[-1]
    info_url = (
        f"{base_url.rstrip('/')}/online_booking/api/slot_selection_funnel/v1/info.json"
        f"?profile_slug={short}&locale=de"
    )
    try:
        _, payload = get_json(info_url,
                              referer=f"{base_url.rstrip('/')}/{slug}")
    except HttpError as exc:
        LOG.debug("info.json: %s", exc)
        return None
    if isinstance(payload, dict) and isinstance(payload.get("data"), dict):
        return payload["data"]
    return None


def _bookable_configs(info: dict[str, Any]) -> list[dict[str, Any]]:
    """Liste aller enabled (visit_motive_id, agenda_id, practice_id, insurance)-4-Tupel."""
    out: list[dict[str, Any]] = []
    visits = {v["id"]: v for v in (info.get("visit_motives") or [])
              if isinstance(v, dict) and isinstance(v.get("id"), int)}
    agendas = info.get("agendas") or []
    for ag in agendas:
        if not isinstance(ag, dict):
            continue
        aid = ag.get("id")
        pid = ag.get("practice_id")
        if not isinstance(aid, int) or not isinstance(pid, int):
            continue
        if ag.get("booking_temporary_disabled"):
            continue
        if ag.get("hide_practitioner"):
            # Reine Practitioner-Slots sind für externe Buchung selten ok;
            # wir lassen sie aber durch, Doctolib entscheidet.
            pass
        for vid in (ag.get("visit_motive_ids") or []):
            v = visits.get(vid)
            if not v:
                continue
            for cfg in (v.get("configurations") or []):
                if not isinstance(cfg, dict):
                    continue
                ins = cfg.get("insurance")
                cfg_agenda = cfg.get("agenda_id")
                # Standardkonfiguration ohne agenda_id bindet sich an die
                # Agenda des Tupels (siehe Kosar-Hedayat: configurations ohne
                # agenda_id, online_booking_status=enabled_for_all).
                cfg_aid = cfg_agenda if isinstance(cfg_agenda, int) else aid
                cfg_pid = pid
                if cfg.get("disabled"):
                    continue
                status = cfg.get("online_booking_status")
                if status not in ("enabled_for_all",
                                  "enabled_for_existing_only"):
                    continue
                if ins not in ("public", "private"):
                    continue
                out.append({
                    "visit_motive_id": vid,
                    "visit_motive_name": v.get("name"),
                    "agenda_id": cfg_aid,
                    "practice_id": cfg_pid,
                    "insurance": ins,
                    "online_booking_status": status,
                })
    return out


def _match_motive(motive_input: str | None,
                  configs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Filtert Configs nach ``--motive ID|TEXT``."""
    if not motive_input:
        return configs
    s = motive_input.strip()
    # 1) Versuch: ID (numerisch)
    if s.isdigit():
        wanted = int(s)
        matched = [c for c in configs if c["visit_motive_id"] == wanted]
        if matched:
            return matched
        # ID nicht im Profil → leere Liste; Aufrufer behandelt das.
        return []
    # 2) Substring auf Name (case-insensitive)
    needle = s.casefold()
    matched = [c for c in configs if c["visit_motive_name"]
               and needle in c["visit_motive_name"].casefold()]
    return matched


def _pick_default(configs: list[dict[str, Any]],
                  insurance: str = DEFAULT_INSURANCE) -> list[dict[str, Any]]:
    """Wählt eine Default-Konfiguration (erstes Tupel der gewünschten
    Insurance, sonst erstes überhaupt)."""
    if not configs:
        return []
    prefer = [c for c in configs if c["insurance"] == insurance]
    if not prefer:
        prefer = configs
    return [prefer[0]]


def _call_availabilities(visit_motive_id: int, agenda_id: int,
                         practice_id: int, insurance: str, *,
                         start_date_time: str, limit: int,
                         base_url: str = "https://www.doctolib.de"
                         ) -> dict[str, Any]:
    """Ein availabilities.json-Call. Wirft HttpError."""
    params = {
        "start_date_time": start_date_time,
        "visit_motive_id": str(visit_motive_id),
        "agenda_ids": str(agenda_id),
        "practice_ids": str(practice_id),
        "insurance_sector": insurance,
        "telehealth": "false",
        "limit": str(max(1, int(limit))),
    }
    url = f"{base_url.rstrip('/')}/search/availabilities.json"
    _, data = get_json(url, params=params)
    if not isinstance(data, dict):
        raise HttpError(4, "parse", "availabilities.json: kein Objekt",
                        url=url)
    return data


def _reason_text(data: dict[str, Any]) -> str | None:
    r = data.get("reason")
    return r if isinstance(r, str) and r else None


def _flatten_to_records(data: dict[str, Any], config: dict[str, Any],
                        places_index: dict[int, dict[str, Any]]
                        ) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    practice_id = config["practice_id"]
    place = places_index.get(practice_id, {})
    practice_name = place.get("name")
    practice_address = place.get("address")
    visit_motive = {
        "id": config["visit_motive_id"],
        "name": config["visit_motive_name"],
        "insurance": config["insurance"],
    }
    for day in data.get("availabilities") or []:
        if not isinstance(day, dict):
            continue
        date = day.get("date")
        slots = day.get("slots") or []
        if not date or not slots:
            continue
        for slot in slots:
            records.append({
                "date": date,
                "slot": slot,
                "datetime": slot,  # ISO8601
                "place": {
                    "name": practice_name,
                    "address": practice_address,
                    "practice_id": practice_id,
                },
                "motive": visit_motive,
            })
    return records


def _build_places_index(info: dict[str, Any]) -> dict[int, dict[str, Any]]:
    idx: dict[int, dict[str, Any]] = {}
    for p in info.get("places") or []:
        if not isinstance(p, dict):
            continue
        for pid in p.get("practice_ids") or []:
            if isinstance(pid, int):
                idx[pid] = p
    return idx


def list_motives(info: dict[str, Any]) -> list[dict[str, Any]]:
    """Liste der verfügbaren Motive (für Fehlerausgabe)."""
    seen: set[int] = set()
    out: list[dict[str, Any]] = []
    for v in info.get("visit_motives") or []:
        if not isinstance(v, dict):
            continue
        vid = v.get("id")
        if not isinstance(vid, int) or vid in seen:
            continue
        seen.add(vid)
        out.append({"id": vid, "name": v.get("name")})
    out.sort(key=lambda m: m["id"])
    return out


def _normalize_days(value: int | None) -> int:
    if not isinstance(value, int) or value < 1 or value > 30:
        return 7
    return value


def slots_for_profile(slug_or_url: str, *,
                      motive: str | None = None,
                      days: int | None = 7,
                      insurance: str = DEFAULT_INSURANCE,
                      base_url: str = "https://www.doctolib.de"
                      ) -> tuple[int, dict[str, Any]]:
    """Liefert (exit_code, payload)."""
    if not slug_or_url or not slug_or_url.strip():
        return 1, {"error": {"kind": "usage", "code": 1,
                             "message": "Slug oder URL fehlt"}}
    slug = _slug_from_input(slug_or_url)
    if not slug:
        return 1, {"error": {"kind": "usage", "code": 1,
                             "message": f"Slug/URL nicht parsebar: {slug_or_url!r}"}}
    n_days = _normalize_days(days)
    ins = INSURANCE_BY_ALIAS.get((insurance or "").strip().lower(),
                                 DEFAULT_INSURANCE)

    info = _load_info(slug, base_url=base_url)
    if not info:
        return 4, {"error": {"kind": "parse", "code": 4,
                             "message": (f"info.json nicht abrufbar für {slug} "
                                         "(kein Online-Booking oder Doctolib-Blockade)")}}

    configs = _bookable_configs(info)
    if not configs:
        motives_all = list_motives(info)
        return 4, {"error": {
            "kind": "parse", "code": 4,
            "message": "keine online-buchbaren (visit_motive, agenda)-Tupel in diesem Profil",
            "available_motives": motives_all,
        }}

    if motive:
        chosen = _match_motive(motive, configs)
        if not chosen:
            return 1, {"error": {
                "kind": "usage", "code": 1,
                "message": (f"--motive {motive!r} passt zu keinem "
                            "online-buchbaren Motiv dieses Profils"),
                "available_motives": list_motives(info),
            }}
    else:
        chosen = _pick_default(configs, insurance=ins)

    start_dt = _now_iso()
    places_index = _build_places_index(info)
    all_slots: list[dict[str, Any]] = []
    last: dict[str, Any] | None = None
    next_slot: str | None = None
    for cfg in chosen:
        try:
            data = _call_availabilities(
                cfg["visit_motive_id"], cfg["agenda_id"],
                cfg["practice_id"], cfg["insurance"],
                start_date_time=start_dt, limit=n_days, base_url=base_url,
            )
        except HttpError as exc:
            return exc.code, {"error": {"kind": exc.kind, "code": exc.code,
                                        "message": str(exc)}}
        last = data
        nxt = data.get("next_slot")
        if isinstance(nxt, str) and nxt and not next_slot:
            next_slot = nxt
        all_slots.extend(_flatten_to_records(data, cfg, places_index))

    all_slots.sort(key=lambda s: (s["date"], s["slot"]))

    # Tages-Aggregation (für INTERFACE-Ausgabe)
    by_date: dict[str, list[str]] = {}
    for s in all_slots:
        by_date.setdefault(s["date"], []).append(s["slot"])
    # Praxis-/Motiv-Info vom ersten Treffer übernehmen
    practice_id = chosen[0]["practice_id"]
    practice_meta = places_index.get(practice_id, {})
    motive_first = {
        "id": chosen[0]["visit_motive_id"],
        "name": chosen[0]["visit_motive_name"],
        "insurance": chosen[0]["insurance"],
    }
    payload: dict[str, Any] = {
        "profile": {
            "slug": slug,
            "practice_id": practice_id,
            "practice_ids": sorted({c["practice_id"] for c in chosen}),
            "url": f"{base_url.rstrip('/')}/{slug}",
            "practice_name": practice_meta.get("name"),
            "practice_address": practice_meta.get("address"),
        },
        "motive": motive_first,
        "availabilities": [
            {"date": d, "slots": sorted(set(sl))} for d, sl in
            sorted(by_date.items())
        ],
        "slots": all_slots,
        "total": len(all_slots),
        "next_slot": next_slot,
        "reason": _reason_text(last) if last else None,
    }
    return 0, payload


__all__ = ["slots_for_profile", "list_motives"]
