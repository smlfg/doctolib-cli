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


def _add_verbose_flag(p: argparse.ArgumentParser) -> None:
    p.add_argument("-v", "--verbose", action="store_true",
                   help="Slug in der Terminal-Ausgabe zeigen (nur TTY-Modus).")


def _is_tty() -> bool:
    """True nur bei echtem Terminal auf stdout (Tests patchen das)."""
    try:
        return bool(sys.stdout.isatty())
    except (AttributeError, ValueError):
        return False


def _stdin_tty() -> bool:
    try:
        return bool(sys.stdin.isatty())
    except (AttributeError, ValueError):
        return False


def _human_mode(args: argparse.Namespace) -> bool:
    """Lesbare Textausgabe: nur TTY und kein --json."""
    return not getattr(args, "json", False) and _is_tty()


def _candidates_to_stderr(candidates: Any) -> None:
    if not isinstance(candidates, list) or not candidates:
        return
    sys.stderr.write("Treffer für die Auswahl:\n")
    for i, rec in enumerate(candidates, 1):
        if not isinstance(rec, dict):
            continue
        name = rec.get("name") or "?"
        slug = rec.get("slug") or ""
        sys.stderr.write(f"[{i}] {name}"
                         + (f" | slug: {slug}" if slug else "") + "\n")


def _fail_payload(payload: dict[str, Any], *, as_json: bool) -> int:
    """Fehlerobjekt einheitlich ausgeben (inkl. hint/candidates)."""
    err = payload.get("error") or {}
    extra = {k: v for k, v in err.items()
             if k not in ("code", "kind", "message")}
    if not as_json:
        _candidates_to_stderr(extra.get("candidates"))
        if extra.get("hint"):
            sys.stderr.write(f"Hinweis: {extra['hint']}\n")
    return fail(int(err.get("code", 1)), str(err.get("message", "Fehler")),
                as_json=as_json, kind=str(err.get("kind", "error")),
                extra=extra or None)


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
    _add_verbose_flag(p_s)
    _add_json_flag(p_s)

    p_sh = sub.add_parser(
        "show", help="Profil/Detail zu Slug, URL oder Suchbegriff.",
        description=("Profil per Slug/URL laden. Ohne \"/\" wird das "
                     "Argument als Suche \"FACH ORT\" verstanden; im "
                     "Terminal folgt eine nummerierte Auswahl, sonst "
                     "--pick N nutzen."),
    )
    p_sh.add_argument("query", nargs="*",
                      help="Slug/URL oder Suchbegriff (z. B. hautarzt heilbronn).")
    p_sh.add_argument("--search", default=None, metavar="FACH ORT",
                      help="Suche erzwingen, z. B. --search \"hautarzt heilbronn\".")
    p_sh.add_argument("--pick", type=int, default=None, metavar="N",
                      help="Treffer N aus der Suche ohne Prompt wählen.")
    _add_json_flag(p_sh)

    p_sl = sub.add_parser(
        "slots", help="Freie Termine per Slug, URL oder Suchbegriff.",
        description=("Freie Termine für ein Profil. Ein Argument mit \"/\" "
                     "oder eine Doctolib-URL wird direkt genutzt. Alles "
                     "andere ist eine Suche \"FACH ORT\": im Terminal "
                     "erscheint eine nummerierte Auswahl, in Pipes/Agenten "
                     "bitte --pick N verwenden."),
    )
    p_sl.add_argument("query", nargs="*",
                      help="Slug/URL oder Suchbegriff (z. B. hautarzt heilbronn).")
    p_sl.add_argument("--search", default=None, metavar="FACH ORT",
                      help="Suche erzwingen, z. B. --search \"hautarzt heilbronn\".")
    p_sl.add_argument("--pick", type=int, default=None, metavar="N",
                      help="Treffer N aus der Suche ohne Prompt wählen.")
    p_sl.add_argument("--motive", default=None,
                      help="Visit-Motive-ID oder -Text (optional).")
    p_sl.add_argument("--days", type=int, default=7, help="1..30 (default 7).")
    p_sl.add_argument("--insurance", default="any",
                      help="public|private|any (Default any). Aliasse: "
                           "gesetzlich=public, privat/pkv=private.")
    _add_json_flag(p_sl)

    p_sp = sub.add_parser("specialities", help="Bekannte Fachrichtungs-Slugs.")
    _add_json_flag(p_sp)

    p_b = sub.add_parser("book", help="Termin buchen (NICHT UNTERSTÜTZT).")
    p_b.add_argument("--confirm", action="store_true",
                     help="Wird trotzdem abgelehnt (Doku).")
    _add_json_flag(p_b)
    # nargs='*' (nicht REMAINDER): sonst landen --json/--confirm in rest[].
    p_b.add_argument("rest", nargs="*", help="Argumente werden ignoriert.")

    pw = sub.add_parser("watch", help="Lokal auf freie Termine warten.")
    pw_sub = pw.add_subparsers(dest="watch_cmd", required=True)
    pw_a = pw_sub.add_parser("add")
    pw_a.add_argument("profile")
    pw_a.add_argument("--motive", default=None)
    pw_a.add_argument("--insurance", default="any",
                      help="public|private|any (Default any).")
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
    from . import search as search_mod
    from .output import format_search
    code, payload = search_mod.search_speciality_location(
        args.speciality, args.location, limit=args.limit,
    )
    if code != 0:
        return _fail_payload(payload, as_json=args.json)
    if _human_mode(args):
        sys.stdout.write(format_search(payload,
                                       verbose=getattr(args, "verbose", False)) + "\n")
        return 0
    return emit(payload, args.json)


def cmd_show(args: argparse.Namespace) -> int:
    from . import resolve as resolve_mod
    from . import show as show_mod
    from .output import format_show

    code, resolved = resolve_mod.resolve_profile(
        args.query, search=args.search, pick=args.pick,
        command="show", interactive=_human_mode(args) and _stdin_tty(),
    )
    if code != 0:
        return _fail_payload(resolved, as_json=args.json)
    slug = resolved["slug"]
    code, payload = show_mod.show_profile(slug)
    if code != 0:
        return _fail_payload(payload, as_json=args.json)
    if _human_mode(args):
        chosen = resolved.get("result")
        if chosen:
            sys.stdout.write(f"Gewählt: {chosen.get('name')} "
                             f"({slug})\n\n")
        sys.stdout.write(format_show(payload) + "\n")
        return 0
    return emit(payload, args.json)


def cmd_slots(args: argparse.Namespace) -> int:
    from . import resolve as resolve_mod
    from . import slots as slots_mod
    from .output import format_slots

    code, resolved = resolve_mod.resolve_profile(
        args.query, search=args.search, pick=args.pick,
        command="slots", interactive=_human_mode(args) and _stdin_tty(),
    )
    if code != 0:
        return _fail_payload(resolved, as_json=args.json)
    slug = resolved["slug"]
    code, payload = slots_mod.slots_for_profile(
        slug,
        motive=args.motive,
        days=args.days,
        insurance=args.insurance,
    )
    if code != 0:
        return _fail_payload(payload, as_json=args.json)
    if _human_mode(args):
        chosen = resolved.get("result")
        if chosen:
            sys.stdout.write(f"Gewählt: {chosen.get('name')} "
                             f"({slug})\n\n")
        sys.stdout.write(format_slots(payload) + "\n")
        return 0
    return emit(payload, args.json)


def cmd_specialities(args: argparse.Namespace) -> int:
    from . import specialities as sp_mod
    items = sp_mod.list_specialities()
    if args.json:
        payload = {"specialities": items, "count": len(items)}
        return emit(payload, True)
    # Textmodus: zwei Spalten (Slug | Name)
    name_w = max((len(s["name"]) for s in items), default=0)
    for s in items:
        sys.stdout.write(f"{s['slug']:<24} {s['name']}\n")
    sys.stdout.write(f"\n{len(items)} Fachrichtungen.\n")
    return 0


def cmd_book(args: argparse.Namespace) -> int:
    """Buchen ist explizit verboten – immer exit 5, mit oder ohne --confirm."""
    return fail(
        5,
        "Buchen wird nicht unterstützt (doctolib-cli liefert nur Suche/Watch).",
        as_json=args.json,
        kind="unsupported",
    )


def cmd_watch_add(args: argparse.Namespace) -> int:
    from . import watch as watch_mod
    code, payload = watch_mod.add_watch(
        args.profile, motive=args.motive,
        insurance=args.insurance, before=args.before)
    if code != 0:
        err = payload["error"]
        return fail(err["code"], err["message"],
                    as_json=args.json, kind=err["kind"])
    return emit(payload, args.json)


def cmd_watch_list(args: argparse.Namespace) -> int:
    from . import watch as watch_mod
    code, payload = watch_mod.list_watches()
    if code != 0:
        err = payload["error"]
        return fail(err["code"], err["message"],
                    as_json=args.json, kind=err["kind"])
    if args.json:
        return emit(payload, True)
    items = payload.get("watches") or []
    if not items:
        sys.stdout.write("(keine Watches)\n")
        return 0
    sys.stdout.write(f"{'ID':<10} {'PROFIL':<40} {'MOTIV':<20} "
                     f"{'VERSICH.':<10} {'BEFORE':<12} LETZTE PRÜFUNG\n")
    for w in items:
        sys.stdout.write(
            f"{w.get('id',''):<10} "
            f"{(w.get('profile') or ''):<40} "
            f"{str(w.get('motive') or ''):<20} "
            f"{str(w.get('insurance') or ''):<10} "
            f"{str(w.get('before') or '-'):<12} "
            f"{str(w.get('last_checked') or '-')}\n"
        )
    sys.stdout.write(f"\n{payload.get('count', len(items))} Watches.\n")
    return 0


def cmd_watch_remove(args: argparse.Namespace) -> int:
    from . import watch as watch_mod
    code, payload = watch_mod.remove_watch(args.id)
    if code != 0:
        err = payload["error"]
        return fail(err["code"], err["message"],
                    as_json=args.json, kind=err["kind"])
    return emit(payload, args.json)


def cmd_watch_check(args: argparse.Namespace) -> int:
    from . import watch as watch_mod
    code, payload = watch_mod.check_watches()
    if code != 0:
        err = payload["error"]
        return fail(err["code"], err["message"],
                    as_json=args.json, kind=err["kind"])
    return emit(payload, args.json)


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
    except KeyboardInterrupt:
        return fail(1, "Abgebrochen (Strg+C).",
                    as_json=getattr(args, "json", False), kind="usage")
    except Exception as exc:  # pragma: no cover – Schutznetz
        LOG.exception("Unerwarteter Fehler")
        return fail(1, f"interner Fehler: {exc.__class__.__name__}",
                    as_json=getattr(args, "json", False), kind="error")


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))