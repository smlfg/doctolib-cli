# Akzeptanztests – doctolib-cli

Quelle: `INTERFACE.md`, geprüft gegen die `agent-learnings/tests/harness`
Sandbox (loopback-only). Echte Live-Calls (gegen doctolib.de) nur in den
Smoke-Tests, die das ausdrücklich wollen, und nur wenn Doctolib nicht
captcha-geschützt ist.

Alle Tests rufen `doctolib` als Subprozess, mit `ACCEPTANCE_SANDBOX=1`,
damit aus Versehen live gehende Netz-Calls sofort auffliegen.

## Befehls-Ebene

1. `--help` → exit 0, stdout enthält "Suche" oder "search".
2. `--version` → exit 0, stdout beginnt mit "doctolib ".
3. `search` ohne Argumente → exit 1, **mit** `--json` JSON-Fehler
   `{"error": {"kind": "usage", ...}}`.
4. `search hautarzt berlin --limit 0 --json` → exit 1.
5. `search hautarzt berlin --limit 51 --json` → exit 1.
6. `search hautarzt berlin --limit abc --json` → exit 1.
7. `book` (ohne Argumente, ohne `--confirm`) → exit 5, JSON
   `{"error": {"kind": "unsupported", "code": 5, ...}}`.
8. `book foo bar --confirm` → exit 5 (auch mit `--confirm`).
9. `watch add foo` ohne `DOCTOLIB_CONFIG` ⇒ wird gesetzt, exit 0,
   JSON enthält `id`.
10. `watch list` ohne `--json` → exit 0, Tabelle.
11. `watch remove <id>` einmalig und zweimal → beide exit 0,
    zweiter Aufruf JSON `{"noop": true}`.
12. `specialities --json` → exit 0, JSON enthält `specialities` mit
    ≥ 10 Einträgen.

## Such-Schutz (live, akzeptabel wenn Doctolib liefert)

- `search hautarzt berlin --limit 3 --json`: HTTP 200 oder Exit 3.
  Wenn 200: jeder Treffer enthält "Berlin" (PLZ `1`) und der
  `speciality_slug` aus dem Treffer-Slug-Pfad beginnt mit `hautarzt`.
- `search allgemeinmedizin heilbronn --limit 3 --json`: gleiches mit
  PLZ `74…` und Slug `allgemeinmedizin`.
- Bei HTTP-Status 200 aber `ItemList` leer: exit 4 (parse).
- Bei HTTP-Status 404 (Stadt/Fach unbekannt): exit 3 oder 4, **nicht** 0.

## Sandbox-Verhalten

- `ACCEPTANCE_SANDBOX=1` aktiviert die `sitecustomize.py` aus
  `agent-learnings/tests/harness/`, die jeden DNS-/Connect-Versuch zu
  Nicht-Loopback blockt und in `$ACCEPTANCE_NET_LOG` protokolliert.
- Damit ist garantiert: ein Test, der Doctolib live ruft, **muss
  vorher** `ACCEPTANCE_SANDBOX` explizit deaktivieren
  (`env=ACCEPTANCE_SANDBOX=0 doctolib …`).