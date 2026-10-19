# INTERFACE – doctolib-cli

CLI: `doctolib` (Paket `doctolib-cli`, v0.1.0).

## Allgemein

- `--help` / `--version` (auf stdout, exit 0).
- Globale Option `--json`: genau ein JSON-Objekt auf stdout, Logs/Stderr
  auf stderr.
- Ausgaben-Sprache: Deutsch (Texte für Menschen), JSON-Felder englisch.
- Keine erfundenen Daten. Profile/Termine sind live oder gar nicht.

## Exit-Codes

| Code | Bedeutung |
| ---- | -------- |
| 0    | OK |
| 1    | Usage / Validierung (Args, Config, Env) |
| 2    | Auth / Session (Login fehlt/ungültig/abgelaufen) |
| 3    | Netzwerk / HTTP (Timeout, 5xx, Verbindungsfehler, Bot-Wall) |
| 4    | Parse / unerwartete Antwort |
| 5    | Forbidden / Aktion ohne `--confirm` (auch `book`) |

Bei `--json` liefert jeder Fehler ein Objekt der Form:

    {"error": {"code": N, "kind": "...", "message": "..."}}

mit `kind` ∈ {`usage`, `auth`, `network`, `parse`, `confirm_required`,
`forbidden`, `unsupported`}. Niemals Traceback auf stdout.

## Befehle

### `doctolib search SPECIALITY LOCATION [--limit N] [--json]`

- Live gegen `https://www.doctolib.de/<speciality-slug>/<city-slug>`.
- Erwartet Slug (kleingeschrieben) oder Klartext, der zu einem Slug
  aufgelöst wird (statische Whitelist, hartkodiert).
- `--limit N`: 1 ≤ N ≤ 50, default 20. Ungültig → Exit 1.
- Output:
  - Textmodus: Tabelle `name | adresse | slug`.
  - `--json`: `{"query": {"speciality":..., "location":...},
    "results": [{"name", "type", "address": {...}, "motive",
    "slug", "url"}], "count": N}`.

### `doctolib show PROFILE_SLUG_OR_URL [--json]`

- Detail-Profil per Slug (`hautarzt/berlin/kosar-hedayat`) oder voller URL
  (`https://www.doctolib.de/...`).
- Felder: `name`, `type` (`Physician`/`MedicalOrganization`), `address`,
  `image`, `motive` (`availableService`), `opening_hours`, `slug`, `practice_id`.

### `doctolib slots PROFILE_SLUG_OR_URL [--motive ID|TEXT] [--days N] [--json]`

- Live freie Termine über
  `GET https://www.doctolib.de/search/availabilities.json?...`
- Default `--days 7`.
- `--motive` ist optional; sonst wählt der Server das erste verfügbare
  Motiv. Wird es weggelassen und der Server antwortet nicht (400), →
  `exit 1` mit Hinweis "Motiv angeben mit --motive".
- Output `--json`: `{"profile": {"slug", "practice_id"},
  "motive": {"id", "name"}, "availabilities": [{"date",
  "slots": [ISO8601]}]}`.
- (Voll in Lauf B/C – in A noch Platzhalter.)

### `doctolib specialities [--json]`

- Liste bekannter Fachrichtungs-Slugs mit deutscher Bezeichnung.
- Output `--json`: `{"specialities": [{"slug", "name"}]}`.

### `doctolib watch add PROFILE [--motive ..] [--before YYYY-MM-DD]`

- Trägt Profil in `$XDG_CONFIG_HOME/doctolib-cli/watch.json` ein.
- `id` ist sha1(slug+optional-motive)[:8].
- Ausgabe: `{"id", "profile", "motive?", "before?", "created_at"}`.

### `doctolib watch list`

- Listet Watch-Einträge (Text oder `--json`).

### `doctolib watch remove ID`

- Idempotent (unbekannte ID → exit 0, Feld `noop: true`).

### `doctolib watch check [--json]`

- Pollt alle Watch-Einträge und vergleicht Slots. Nur Cache, keine
  Buchung. (Stub in Lauf A; echter Vergleich in B/C.)

### `doctolib book ...`

- **Immer** `exit 5` mit `kind=unsupported` und message "Buchen wird
  nicht unterstützt" – unabhängig von `--confirm`. Wird explizit so
  dokumentiert, damit Agenten nicht versehentlich buchen.

## Konfiguration / Pfade

- `DOCTOLIB_BASE_URL` (optional, default `https://www.doctolib.de`).
- `DOCTOLIB_EMAIL`, `DOCTOLIB_PASSWORD` (geplant, Lauf B+): nur Env.
- `XDG_CONFIG_HOME` oder Default `$HOME/.config` →
  `…/doctolib-cli/{watch.json, session.json}`.

## Tests (akzeptiert; in `docs/ACCEPTANCE.md`)

- `--help` / `--version`: exit 0.
- `search` ohne Argumente: exit 1.
- `search` mit `--limit 0` oder `--limit 51`: exit 1.
- `book` (mit oder ohne `--confirm`): exit 5.
- `search hautarzt berlin --limit 3 --json`: HTTP 200 oder Exit 3
  (Netzwerkfehler), **niemals** Traceback. Wenn HTTP 200, müssen die
  Treffer Berliner Hautärzte sein (Fachrichtung, Stadtname).