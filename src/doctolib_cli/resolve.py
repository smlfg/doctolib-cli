"""Profil-Eingabe auflösen: Slug/URL direkt oder Suche per Fach + Ort.

Die Auflösung ist bewusst konservativ: ein Argument mit ``/`` (oder eine
Doctolib-URL) wird immer als Profil-Slug behandelt. Alles andere gilt als
Suchbegriff ``FACH ORT``. Damit bleiben bestehende Slug-Aufrufe stabil.
"""

from __future__ import annotations

import sys
from typing import Any

from .output import format_search
from .search import search_speciality_location
from .show import _slug_from_input
from .specialities import resolve_speciality

DEFAULT_SEARCH_LIMIT = 10


def _search_proxy(*args: Any, **kwargs: Any) -> tuple[int, dict[str, Any]]:
    """Monkeypatch-freundlicher Einstiegspunkt für Tests."""
    return search_speciality_location(*args, **kwargs)


def _stdin_is_tty() -> bool:
    try:
        return bool(sys.stdin.isatty())
    except (AttributeError, ValueError):
        return False


def _parse_search_query(raw: str) -> tuple[str, str] | None:
    """Findet die längste Fachrichtungs-Präfix und den Rest als Ort."""
    words = raw.split()
    if len(words) < 2:
        return None
    for i in range(len(words) - 1, 0, -1):
        speciality = " ".join(words[:i])
        location = " ".join(words[i:])
        if resolve_speciality(speciality):
            return speciality, location
    return None


def _candidates(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for rec in results:
        if not isinstance(rec, dict):
            continue
        out.append({
            "name": rec.get("name"),
            "slug": rec.get("slug"),
            "address": rec.get("address"),
        })
    return out


def _usage(message: str, *, hint: str | None = None,
           candidates: list[dict[str, Any]] | None = None
           ) -> tuple[int, dict[str, Any]]:
    err: dict[str, Any] = {"kind": "usage", "code": 1, "message": message}
    if hint:
        err["hint"] = hint
    if candidates is not None:
        err["candidates"] = candidates
    return 1, {"error": err}


def resolve_profile(words: list[str] | tuple[str, ...], *,
                    search: str | None = None,
                    pick: int | None = None,
                    command: str = "slots",
                    interactive: bool = False,
                    limit: int = DEFAULT_SEARCH_LIMIT
                    ) -> tuple[int, dict[str, Any]]:
    """Liefert ``(0, {"slug": ...})`` oder ``(code, {"error": ...})``.

    ``interactive`` darf nur True sein, wenn stdin+stdout TTY sind und
    kein ``--json`` gesetzt ist. Sonst wird nie ein Prompt ausgegeben.
    """
    parts = [str(w) for w in (words or []) if str(w).strip()]
    raw = " ".join(parts).strip()
    explicit_search = (search or "").strip()

    if not explicit_search:
        if not raw:
            return _usage(
                "Profil-Slug/URL oder Suchbegriff fehlt.",
                hint=f'doctolib {command} hautarzt heilbronn',
            )
        slug = _slug_from_input(raw)
        # Nur echte Slugs/URLs (mit "/") direkt nehmen; kurze Namen sind
        # Suchbegriffe und keine Profile.
        if slug and ("/" in raw or raw.startswith(("http://", "https://"))):
            return 0, {"slug": slug, "from_search": False}

    query_text = explicit_search or raw
    parsed = _parse_search_query(query_text)
    if not parsed:
        return _usage(
            (f"Kein Profil-Slug/URL und keine auflösbare Suche: {query_text!r}. "
             "Erwartet z. B. 'hautarzt heilbronn'."),
            hint=(f'doctolib {command} --search "hautarzt heilbronn" --pick 1'),
        )
    speciality, location = parsed
    code, payload = _search_proxy(speciality, location, limit=limit)
    if code != 0:
        return code, payload

    results = [r for r in (payload.get("results") or []) if isinstance(r, dict)]
    if not results:
        return 4, {"error": {"kind": "parse", "code": 4,
                             "message": "Suche lieferte keine Treffer."}}
    candidates = _candidates(results)
    pick_hint = f'doctolib {command} --search "{query_text}" --pick 1'

    if pick is not None:
        if pick < 1 or pick > len(results):
            return _usage(
                f"--pick {pick} liegt außerhalb von 1..{len(results)}.",
                hint=pick_hint, candidates=candidates,
            )
        return _selected(results[pick - 1], payload)

    if interactive:
        sys.stdout.write(format_search(payload) + "\n\n")
        sys.stdout.write(f"Nummer wählen [1-{len(results)}]: ")
        try:
            sys.stdout.flush()
        except (AttributeError, OSError):
            pass
        try:
            line = sys.stdin.readline()
        except KeyboardInterrupt:
            return _usage("Auswahl abgebrochen.", hint=pick_hint,
                          candidates=candidates)
        except (EOFError, OSError):
            return _usage("Eingabe beendet (EOF).", hint=pick_hint,
                          candidates=candidates)
        choice = (line or "").strip()
        if not choice.isdigit() or not (1 <= int(choice) <= len(results)):
            return _usage(
                "Ungültige Auswahl. Bitte eine Nummer aus der Liste eingeben.",
                hint=pick_hint, candidates=candidates,
            )
        return _selected(results[int(choice) - 1], payload)

    return _usage(
        ("Kein interaktives Terminal für die Auswahl. "
         "Nutze --pick N oder rufe direkt mit einem Slug auf."),
        hint=pick_hint, candidates=candidates,
    )


def _selected(result: dict[str, Any], payload: dict[str, Any]
              ) -> tuple[int, dict[str, Any]]:
    slug = result.get("slug")
    if not slug:
        return 4, {"error": {"kind": "parse", "code": 4,
                             "message": "Treffer ohne Slug (nicht aufrufbar)."}}
    return 0, {
        "slug": slug,
        "from_search": True,
        "result": result,
        "query": payload.get("query"),
        "count": payload.get("count"),
    }


__all__ = ["resolve_profile", "_parse_search_query"]
