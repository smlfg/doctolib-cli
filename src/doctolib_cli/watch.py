"""watch-Handler: lokale Watchliste, ohne Buchung.

Datei: ``$XDG_CONFIG_HOME/doctolib-cli/watch.json``.
Atomar schreiben (write-temp + rename), kaputte JSON → Exit 4 (sauberer
Fehler statt Traceback). ``watch remove`` auf unbekannte ID → Exit 1
(siehe Auftrag; INTERFACE sagt idempotent, Auftrag sagt 1 – wir nehmen
1 für klares Signal an Agenten und dokumentieren es).

Format::

    {
      "version": 1,
      "watches": [
              {"id": "abc12345", "profile": "hautarzt/berlin/kosar-hedayat",
               "motive": null, "insurance": "any", "before": "2026-12-01",
               "created_at": "2026-10-19T12:34:56+00:00",
               "last_checked": null}
          ]
    }
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

LOG = logging.getLogger("doctolib_cli.watch")

WATCH_VERSION = 1
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def config_dir() -> Path:
    """Gibt das Doctolib-CLI-Config-Verzeichnis zurück (anlegend)."""
    base = os.environ.get("XDG_CONFIG_HOME") or os.path.join(
        os.environ.get("HOME", "~"), ".config")
    p = Path(base).expanduser() / "doctolib-cli"
    p.mkdir(parents=True, exist_ok=True)
    return p


def watch_file() -> Path:
    return config_dir() / "watch.json"


def _make_id(profile: str, motive: str | None) -> str:
    """Deterministische, kurze ID aus (Profil + Motiv)."""
    key = f"{profile}|{motive or ''}".encode("utf-8")
    return hashlib.sha1(key).hexdigest()[:8]


def _now_iso() -> str:
    return datetime.now().replace(microsecond=0).isoformat()


def _validate_date(value: str | None) -> str | None:
    """YYYY-MM-DD → ISO-String. None oder leer → None.

    Wirft ValueError bei offensichtlich falschem Format.
    """
    if value is None:
        return None
    v = value.strip()
    if not v:
        return None
    if not DATE_RE.match(v):
        raise ValueError(f"--before muss YYYY-MM-DD sein, nicht {value!r}")
    try:
        datetime.strptime(v, "%Y-%m-%d")
    except ValueError as exc:
        raise ValueError(f"--before nicht parsebar: {exc}") from exc
    return v


def _read_watch_file(path: Path) -> dict[str, Any]:
    """Liest die Watch-Datei.

    Existiert nicht → leere Default-Struktur.
    Korruptes JSON → Exit 4 (sauberer Fehler).
    """
    if not path.exists():
        return {"version": WATCH_VERSION, "watches": []}
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise RuntimeError(f"watch.json nicht lesbar: {exc}") from exc
    if not raw.strip():
        return {"version": WATCH_VERSION, "watches": []}
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise _CorruptWatchFile(str(exc)) from exc
    if not isinstance(data, dict):
        raise _CorruptWatchFile("Wurzel ist kein Objekt")
    if "watches" not in data or not isinstance(data["watches"], list):
        raise _CorruptWatchFile("Feld 'watches' fehlt oder ist keine Liste")
    return data


class _CorruptWatchFile(Exception):
    """Signalisiert eine nicht parsebare watch.json."""


def _atomic_write(path: Path, payload: dict[str, Any]) -> None:
    """Atomar schreiben: tempfile + os.replace (POSIX-rename)."""
    parent = path.parent
    parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".watch.json.", dir=str(parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, ensure_ascii=False, indent=2)
            fh.write("\n")
        os.replace(tmp, path)
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def add_watch(profile: str, *, motive: str | None = None,
              insurance: str = "any",
              before: str | None = None,
              path: Path | None = None) -> tuple[int, dict[str, Any]]:
    """Fügt einen Watch hinzu. (exit_code, payload)."""
    if not profile or not profile.strip():
        return 1, {"error": {"kind": "usage", "code": 1,
                             "message": "PROFILE fehlt"}}
    try:
        before_iso = _validate_date(before)
    except ValueError as exc:
        return 1, {"error": {"kind": "usage", "code": 1, "message": str(exc)}}

    path = path or watch_file()
    try:
        data = _read_watch_file(path)
    except _CorruptWatchFile as exc:
        return 4, {"error": {"kind": "parse", "code": 4,
                             "message": (f"watch.json korrupt: {exc}. "
                                         "Datei reparieren oder löschen.")}}
    except RuntimeError as exc:
        return 4, {"error": {"kind": "parse", "code": 4,
                             "message": str(exc)}}

    wid = _make_id(profile.strip(), motive)
    # Wenn (Profile, Motive) schon existiert → Update (kein Duplikat).
    for w in data["watches"]:
        if isinstance(w, dict) and w.get("id") == wid:
            if before_iso is not None:
                w["before"] = before_iso
            if insurance:
                w["insurance"] = insurance
            w["updated_at"] = _now_iso()
            try:
                _atomic_write(path, data)
            except OSError as exc:
                return 4, {"error": {"kind": "parse", "code": 4,
                                     "message": f"watch.json schreiben: {exc}"}}
            return 0, {"id": wid, "profile": profile, "motive": motive,
                       "insurance": w.get("insurance", insurance),
                       "before": w.get("before"), "updated": True,
                       "created_at": w.get("created_at"),
                       "last_checked": w.get("last_checked")}

    entry = {
        "id": wid,
        "profile": profile.strip(),
        "motive": motive,
        "insurance": insurance,
        "before": before_iso,
        "created_at": _now_iso(),
        "last_checked": None,
    }
    data["watches"].append(entry)
    try:
        _atomic_write(path, data)
    except OSError as exc:
        return 4, {"error": {"kind": "parse", "code": 4,
                             "message": f"watch.json schreiben: {exc}"}}
    return 0, {"id": wid, "profile": profile, "motive": motive,
               "insurance": insurance, "before": before_iso,
               "created_at": entry["created_at"], "last_checked": None}


def list_watches(*, path: Path | None = None
                 ) -> tuple[int, dict[str, Any]]:
    """Listet alle Watches. (exit_code, payload)."""
    path = path or watch_file()
    try:
        data = _read_watch_file(path)
    except _CorruptWatchFile as exc:
        return 4, {"error": {"kind": "parse", "code": 4,
                             "message": (f"watch.json korrupt: {exc}. "
                                         "Datei reparieren oder löschen.")}}
    except RuntimeError as exc:
        return 4, {"error": {"kind": "parse", "code": 4,
                             "message": str(exc)}}
    items = [w for w in data["watches"] if isinstance(w, dict)]
    return 0, {"watches": items, "count": len(items)}


def remove_watch(wid: str, *, path: Path | None = None
                 ) -> tuple[int, dict[str, Any]]:
    """Entfernt einen Watch. Unbekannte ID → Exit 1 (kein noop).

    (Auftrag: remove unbekannte ID → Exit 1. INTERFACE sagt idempotent;
    der Auftrag ist hier explizit.)
    """
    if not wid or not wid.strip():
        return 1, {"error": {"kind": "usage", "code": 1,
                             "message": "ID fehlt"}}
    path = path or watch_file()
    try:
        data = _read_watch_file(path)
    except _CorruptWatchFile as exc:
        return 4, {"error": {"kind": "parse", "code": 4,
                             "message": (f"watch.json korrupt: {exc}. "
                                         "Datei reparieren oder löschen.")}}
    except RuntimeError as exc:
        return 4, {"error": {"kind": "parse", "code": 4,
                             "message": str(exc)}}

    before = list(data["watches"])
    data["watches"] = [w for w in before
                       if isinstance(w, dict) and w.get("id") != wid]
    removed = len(before) - len(data["watches"])
    if removed == 0:
        return 1, {"error": {"kind": "usage", "code": 1,
                             "message": f"kein Watch mit ID {wid!r}"}}
    try:
        _atomic_write(path, data)
    except OSError as exc:
        return 4, {"error": {"kind": "parse", "code": 4,
                             "message": f"watch.json schreiben: {exc}"}}
    return 0, {"id": wid, "removed": removed}


def check_watches(*, days: int = 14, json_only: bool = False,
                  path: Path | None = None
                  ) -> tuple[int, dict[str, Any]]:
    """Prüft alle Watches gegen Live-Slots.

    Strategie: pro Watch ``slots.slots_for_profile(...)`` mit
    ``days=days`` und ``insurance`` des Watches aufrufen. Treffer
    (=``total > 0``) werden im JSON-Output als Liste gemeldet, mit
    ``first_slot`` (Datum + Zeit). ``last_checked`` wird pro Watch in
    watch.json aktualisiert.

    Live-Fehler (Netzwerk / Parse) pro Watch werden als einzelner
    Fehler gemeldet; das Gesamtergebnis ist exit 0 wenn mindestens ein
    Watch geprüft wurde, sonst 4 (z.B. wenn keine Watches existieren).
    """
    from .slots import slots_for_profile, _resolve_insurance  # lokaler Import

    path = path or watch_file()
    try:
        data = _read_watch_file(path)
    except _CorruptWatchFile as exc:
        return 4, {"error": {"kind": "parse", "code": 4,
                             "message": (f"watch.json korrupt: {exc}.")}}
    except RuntimeError as exc:
        return 4, {"error": {"kind": "parse", "code": 4,
                             "message": str(exc)}}

    items = [w for w in data["watches"] if isinstance(w, dict)]
    if not items:
        return 0, {"checked": [], "count": 0, "hits": []}

    results: list[dict[str, Any]] = []
    hits: list[dict[str, Any]] = []
    now = _now_iso()
    for w in items:
        wid = w.get("id")
        profile = w.get("profile") or ""
        motive = w.get("motive")
        ins = _resolve_insurance(w.get("insurance") or "any")
        before_iso = w.get("before")
        try:
            code, payload = slots_for_profile(
                str(profile), motive=motive, days=days, insurance=ins)
        except Exception as exc:  # noqa: BLE001
            results.append({"id": wid, "profile": profile,
                            "ok": False,
                            "error": f"{exc.__class__.__name__}: {exc}"})
            continue
        if code != 0:
            results.append({"id": wid, "profile": profile, "ok": False,
                            "error": payload.get("error", {})})
            continue
        avail = payload.get("availabilities") or []
        total = payload.get("total", 0)
        first_slot = None
        # Vor before-Datum filtern
        if before_iso and avail:
            try:
                before_d = datetime.strptime(before_iso, "%Y-%m-%d").date()
                avail = [d for d in avail
                         if datetime.strptime(d["date"], "%Y-%m-%d").date()
                         <= before_d]
            except ValueError:
                pass
        if avail:
            d = avail[0]
            first_slot = {"date": d["date"],
                          "time": (d.get("slots") or [None])[0]}
        results.append({"id": wid, "profile": profile,
                        "motive": motive, "insurance": ins,
                        "before": before_iso,
                        "ok": True, "total": total,
                        "first_slot": first_slot})
        if first_slot:
            hits.append({"id": wid, "profile": profile, **first_slot,
                         "motive": motive, "insurance": ins})
        w["last_checked"] = now

    # Persistiere last_checked
    try:
        _atomic_write(path, data)
    except OSError:
        # Wir ignorieren Schreibfehler beim Persistieren – der eigentliche
        # check-Output soll nicht daran scheitern.
        LOG.warning("last_checked konnte nicht persistiert werden")

    return 0, {"checked": results, "count": len(results),
               "hits": hits, "last_checked": now}


__all__ = [
    "add_watch", "list_watches", "remove_watch", "check_watches",
    "watch_file", "config_dir",
]