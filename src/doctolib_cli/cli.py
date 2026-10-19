"""CLI-Entry – argparse-Definition, Handler, zentraler Error-Pfad."""

from __future__ import annotations

import argparse
import json
import logging
import sys
from typing import Any, Callable

from . import __version__

LOG = logging.getLogger("doctolib_cli")

USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36"
)


# ---------- Helpers ----------

def emit(data: dict[str, Any], as_json: bool) -> int:
    """Zentrale Ausgabe: bei --json genau ein JSON-Objekt auf stdout."""
    sys.stdout.write(json.dumps(data, ensure_ascii=False, indent=2) + "\n")
    return 0


def fail(code: int, msg: str, *, as_json: bool, kind: str = "error",
         extra: dict[str, Any] | None = None) -> int:
    """Saubere Fehlerausgabe: bei --json ein Error-Objekt auf stdout."""
    payload: dict[str, Any] = {"error": {"kind": kind, "code": code, "message": msg}}
    if extra:
        payload["error"].update(extra)
    if as_json:
        sys.stdout.write(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    else:
        sys.stderr.write(f"[{kind}] exit {code}: {msg}\n")
    return code


def _add_json_flag(p: argparse.ArgumentParser) -> None:
    p.add_argument("--json", action="store_true",
                   help="Genau ein JSON-Objekt auf stdout ausgeben.")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="doctolib",
        description=("Agent-CLI für doctolib.de: Suche (Fach+Ort), Profil, "
                     "Verfügbarkeiten, Watch. Buchen nicht unterstützt."),
    )
    p.add_argument("--version", action="version",
                   version=f"doctolib {__version__}")
    sub = p.add_subparsers(dest="cmd", required=True)

    p_s = sub.add_parser("search", help="Ärzte/Praxen suchen (Fachrichtung + Ort).")
    p_s.add_argument("speciality", help="Fachrichtung (Slug oder Name).")
    p_s.add_argument("location", help="Ort (Slug oder Name).")
    p_s.add_argument("--limit", type=int, default=20,
                     help="1..50 (default 20).")
    _add_json_flag(p_s)

    p_sh = sub.add_parser("show", help="Profil/Detail zu einem Slug oder URL.")
    p_sh.add_argument("slug_or_url")
    _add_json_flag(p_sh)

    p_sl = sub.add_parser("slots", help="Freie Termine für ein Profil.")
    p_sl.add_argument("slug_or_url")
    p_sl.add_argument("--motive", default=None,
                      help="Visit-Motive-ID oder -Text (optional).")
    p_sl.add_argument("--days", type=int, default=7, help="1..30 (default 7).")
    _add_json_flag(p_sl)

    p_sp = sub.add_parser("specialities", help="Bekannte Fachrichtungs-Slugs.")
    _add_json_flag(p_sp)

    p_b = sub.add_parser("book", help="Termin buchen (NICHT UNTERSTÜTZT).")
    p_b.add_argument("rest", nargs=argparse.REMAINDER,
                     help="Argumente werden ignoriert.")
    p_b.add_argument("--confirm", action="store_true",
                     help="Wird trotzdem abgelehnt (Doku).")
    _add_json_flag(p_b)

    pw = sub.add_parser("watch", help="Lokal auf freie Termine warten.")
    pw_sub = pw.add_subparsers(dest="watch_cmd", required=True)
    pw_a = pw_sub.add_parser("add")
    pw_a.add_argument("profile")
    pw_a.add_argument("--motive", default=None)
    pw_a.add_argument("--before", default=None, help="YYYY-MM-DD")
    _add_json_flag(pw_a)
    pw_l = pw_sub.add_parser("list")
    _add_json_flag(pw_l)
    pw_r = pw_sub.add_parser("remove")
    pw_r.add_argument("id")
    _add_json_flag(pw_r)
    pw_c = pw_sub.add_parser("check")
    _add_json_flag(pw_c)

    return p


# ---------- Handler (Stubs in Gerüst; werden in späteren Commits befüllt) ----------

def _not_implemented(cmd: str, as_json: bool) -> int:
    return fail(1, f"{cmd}: noch nicht implementiert (geplant in Lauf B/C).",
                as_json=as_json, kind="usage")


def cmd_search(args: argparse.Namespace) -> int:
    return _not_implemented("search", args.json)


def cmd_show(args: argparse.Namespace) -> int:
    return _not_implemented("show", args.json)


def cmd_slots(args: argparse.Namespace) -> int:
    return _not_implemented("slots", args.json)


def cmd_specialities(args: argparse.Namespace) -> int:
    return _not_implemented("specialities", args.json)


def cmd_book(args: argparse.Namespace) -> int:
    """Buchen ist explizit verboten – immer exit 5, mit oder ohne --confirm."""
    return fail(
        5,
        "Buchen wird nicht unterstützt (doctolib-cli liefert nur Suche/Watch).",
        as_json=args.json,
        kind="unsupported",
    )


def cmd_watch_add(args: argparse.Namespace) -> int:
    return _not_implemented("watch add", args.json)


def cmd_watch_list(args: argparse.Namespace) -> int:
    return _not_implemented("watch list", args.json)


def cmd_watch_remove(args: argparse.Namespace) -> int:
    return _not_implemented("watch remove", args.json)


def cmd_watch_check(args: argparse.Namespace) -> int:
    return _not_implemented("watch check", args.json)


HANDLERS: dict[str, Callable] = {
    "search": cmd_search,
    "show": cmd_show,
    "slots": cmd_slots,
    "specialities": cmd_specialities,
    "book": cmd_book,
}

WATCH_HANDLERS: dict[str, Callable] = {
    "add": cmd_watch_add,
    "list": cmd_watch_list,
    "remove": cmd_watch_remove,
    "check": cmd_watch_check,
}


def _wants_json(argv: list[str] | None) -> bool:
    """Schneller Scan: ist --json in argv (ohne nach 'book' o.ä.)?"""
    if not argv:
        return False
    return any(a == "--json" for a in argv)


def main(argv: list[str] | None = None) -> int:
    """Subprozess-Eintritt: parst argv und ruft den passenden Handler.

    Wenn `--json` in argv steht, fangen wir argparse-Fehler ab und geben
    ein JSON-Objekt statt `usage:`-Text + exit 2 zurück (sonst landet
    nichts auf stdout und der Parser schreibt auf stderr, was Agenten
    schwer parsen lässt).
    """
    argv = list(argv) if argv is not None else sys.argv[1:]
    as_json = _wants_json(argv)
    parser = build_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        code = int(exc.code) if isinstance(exc.code, int) else 1
        # Erfolg (exit 0) und --help/--version: argparse regelt das selbst.
        if code == 0:
            return 0
        return fail(1, msg="Argumente ungültig (siehe --help).",
                    as_json=as_json, kind="usage")

    if args.cmd == "watch":
        handler = WATCH_HANDLERS[args.watch_cmd]
    else:
        handler = HANDLERS[args.cmd]
    try:
        return handler(args)
    except Exception as exc:  # pragma: no cover – Schutznetz
        LOG.exception("Unerwarteter Fehler")
        return fail(1, f"interner Fehler: {exc.__class__.__name__}",
                    as_json=getattr(args, "json", False), kind="error")


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))