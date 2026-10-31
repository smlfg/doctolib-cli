# QA – doctolib-cli

Stand: 31.10.2026, frische `pipx install git+https://github.com/smlfg/doctolib-cli`
(eigenes PIPX_HOME), Aufrufe live gegen doctolib.de im Terminal (TTY).

## UX-Gate (agent-learnings/tests/harness)

UX00–UX08 PASS, UX09 SKIP (keine schreibende Sitzung – die CLI ist read-only).
Die drei Sitzungen aus docs/UX.md laufen gegen den Fake-Server grün.
pytest: 105 passed.

## Live-Aufrufe

| Aufruf | Erwartung | Ergebnis |
|---|---|---|
| `doctolib --version` / `--help` | Exit 0 | OK |
| `doctolib search hautarzt heilbronn` | nummerierte Liste, Adressen in Heilbronn | OK, echte Praxen mit PLZ 74072 |
| `doctolib slots hautarzt heilbronn` + Auswahl `1` | Termine des gewählten Treffers | OK, identisch mit `slots <slug>` |
| `doctolib show hautarzt heilbronn --pick 1` | Profil mit Fach, Adresse, Link | OK, Daten passen zur Suche |
| `doctolib specialities haut` | dermatologie, hautarzt | OK |
| `doctolib slots <slug> --json` | JSON mit profile/slots/next_slot | OK |
| `doctolib search` (ohne Argumente) | Usage, Exit 1 | OK |
| `doctolib search hautarzt heilbronn --limit 0` | Exit 1, klare Meldung | OK |
| `doctolib show hautarzt/nirgendwo/gibtsnicht-xyz` | Exit 4, „Profil unbekannt“ | OK |
| `doctolib specialities qqqq` | Exit 1, Hinweis | OK |
| `doctolib slots <slug> --days 0` | Exit 1 | OK |
| `doctolib book x` | Exit 5, nicht unterstützt | OK |

## Befunde und Fixes

- Namen kamen als „Dr.. Name“ / „Dr. med.. Name“ (doppelter Punkt aus Doctolib-Daten) → bereinigt.
- Frische pipx-Installation: Chromium fehlte, `search` brach mit Playwright-Kasten ab und der
  README-Tipp `playwright install chromium` funktioniert unter pipx nicht (Befehl nicht im PATH)
  → Chromium wird beim ersten `search` automatisch nachinstalliert, live geprüft.
- Bot-Schutz: Nach mehreren schnellen Suchen in Folge meldet Doctolib Captcha
  (`[network] exit 3: Doctolib Bot-Schutz/Captcha`). Sauberer Exit, kein Traceback; nach
  kurzer Pause funktioniert die Suche wieder. `show`/`slots` per Slug waren nicht betroffen.
- Keine Buchung (bewusst nicht unterstützt).
