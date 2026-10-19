# ANFORDERUNGEN – doctolib-cli

CLI `doctolib` (Paket `doctolib-cli`, MIT). Ziel: Agenten Live-Aktionen auf
doctolib.de ausführen lassen, ohne Selenium und ohne Login.

## Funktionale Anforderungen

1. **Suche** (`doctolib search SPECIALITY LOCATION`) – Live-Trefferliste
   (Name, Fachrichtung, Adresse, Profil-Slug) für eine Fachrichtung in einer
   Stadt. Quelle: HTML der Doctolib-Suchseite, Parsen des
   `application/ld+json` `CollectionPage`/`ItemList`-Blocks (siehe
   `docs/ENDPOINTS.md`).
3. **Specialities** (`doctolib specialities`) – bekannte Fachrichtungs-Slugs
   als statische Liste (hartkodiert, klein).

## Nicht-funktionale Anforderungen

- Nur `requests` + `beautifulsoup4`, **kein** Playwright/Selenium.
- HTTP-Status prüfen **vor** dem Parsen.
- `--json`: genau ein JSON-Objekt auf stdout, Fehler ebenfalls als JSON.
- Exit-Codes siehe INTERFACE.
- Keine erfundenen Daten. Keine Mailadressen/Telefone/Adressen erfinden.
- `DOCTOLIB_EMAIL`/`DOCTOLIB_PASSWORD` (optional für spätere Schritte):
  nur Env, nie CLI-Flags, nie in Logs/JSON.
- Sessions (für später): `$XDG_CONFIG_HOME/doctolib-cli/session.json`,
  Mode 0600, nur Doctolib-Cookies (Origin `www.doctolib.de`).
- Tests dürfen nie echte Server erreichen (siehe `agent-learnings/tests/harness/sitecustomize.py`).