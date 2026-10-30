# doctolib-cli

## Schnellstart

```bash
pipx install git+https://github.com/smlfg/doctolib-cli   # empfohlen, landet im PATH
# Alternative: pip install --user git+https://github.com/smlfg/doctolib-cli
playwright install chromium
doctolib search hautarzt heilbronn
doctolib slots hautarzt heilbronn
doctolib slots hautarzt/berlin/kosar-hedayat --days 14
```

Wenn der Befehl danach nicht gefunden wird: `pipx` nutzen oder das
`bin`-Verzeichnis des venv in den `PATH` aufnehmen.

CLI für Agenten: Doctolib-Ärzte, Profile und **live freie Termine**
suchen – komplett **read-only**, ohne Login, ohne Buchen.

* Lizenz: **MIT**
* Sprache: Python ≥ 3.10
* Doctolib-Land: **Deutschland** (`country=de`, `https://www.doctolib.de`)
* Status: stabil für `search`, `show`, `slots`, `specialities`, `watch`; `book` ist explizit verboten (Exit 5).

## Installation

```bash
pip install git+https://github.com/smlfg/doctolib-cli
playwright install chromium    # nötig für `search`
```

Das CLI heißt nach der Installation `doctolib` (Konsolen-Skript aus dem
Paket `doctolib-cli`). Python-Abhängigkeiten (`requests`,
`beautifulsoup4`, `playwright`) werden mitinstalliert.

## Befehle

### `doctolib search FACH ORT [--limit N] [--json]`

Live-Suche auf `https://www.doctolib.de/<speciality>/<ort>`. Doctolib
rendert die Treffer erst nach Microfrontend-Hydration, daher geht `search`
über Playwright headless.

```bash
doctolib search hautarzt berlin --limit 3
doctolib search zahnarzt heilbronn --limit 3 --json
```

`--limit` ist 1..50, Default 20. Im Terminal erscheint eine nummerierte
Liste mit Adresse und Slug; bei Pipe/Agent (oder mit `--json`) bleibt
das JSON-Objekt (`results[]`, `count`, `query`) unverändert.

### `doctolib show SLUG|URL|FACH ORT [--search ...] [--pick N] [--json]`

Profilseite (HTML) + Online-Booking-Info (`info.json`) zu einem
Slug wie `hautarzt/berlin/kosar-hedayat` oder einer vollen Doctolib-URL.

```bash
doctolib show hautarzt/berlin/kosar-hedayat
doctolib show hautarzt heilbronn --pick 1        # Suche + Auswahl
```

Im Terminal erscheint eine lesbare Zusammenfassung; bei Pipe/Agent
(oder mit `--json`) bleibt das JSON-Objekt unverändert.

Felder: `name`, `type` (`Physician` / `MedicalOrganization`), `address`,
`addresses[]`, `image`, `motive[]` (aus info.json), `speciality`,
`opening_hours[]`, `slug`, `practice_id`, `practice_ids[]`, `url`.

### `doctolib slots SLUG|URL|FACH ORT [--search ...] [--pick N] [--motive ID|TEXT] [--days N] [--insurance X] [--json]`

Freie Termine live aus
`https://www.doctolib.de/search/availabilities.json`.

```bash
doctolib slots hautarzt/berlin/kosar-hedayat --days 14 --insurance public
doctolib slots hautarzt heilbronn              # Suche + Auswahl im Terminal
doctolib slots hautarzt heilbronn --pick 1      # ohne Prompt (Pipe/Agent)
doctolib slots --search "hautarzt heilbronn" --pick 2 --json
doctolib slots hautarzt/berlin/kosar-hedayat --motive "Hautkrebsvorsorge"
```

* Ein Argument mit `/` (oder eine Doctolib-URL) ist immer ein Profil-Slug.
  Alles andere wird als Suche `FACH ORT` verstanden. Im Terminal kommt
  eine nummerierte Trefferliste mit „Nummer wählen“; ohne TTY (Pipe/Agent)
  endet der Aufruf mit Exit 1 und der Trefferliste im Fehlerobjekt – dann
  `--pick N` oder direkt einen Slug verwenden.
* `--days`: 1..30, Default 7. Doctolib liefert pro Call max. 7 Tage,
  bei `--days > 7` paginieren wir mit fortlaufendem `start_date_time`.
* `--insurance`: `public` / `private` / `any` (Default `any`).
  Aliasse: `gesetzlich`/`gkv` → `public`, `privat`/`pkv` → `private`.
  Bei `any` werden sowohl Kassen- als auch Privat-Tupel abgefragt
  (gedeckelt auf 8 Tupel pro Aufruf, bei Mehrpraxen-Profilen).
* `--motive`: visit_motive-ID (numerisch) oder Substring auf den
  visit_motive-Namen (case-insensitive).

Mehrpraxen-Truncation: Wenn ein Profil mehrere Standorte/Tupel hat,
begrenzen wir die Anzahl der `availabilities.json`-Calls pro Invocation
auf **8** und melden `truncated: true` im JSON, wenn das Limit greift.
Die vollständige Praxis-/Adressliste steht in `doctolib show PROFILE`.

### `doctolib specialities [--json]`

Statische Whitelist bekannter Doctolib-Fachrichtungs-Slugs (58 Einträge,
stichprobenartig live verifiziert). Inkludiert Synonyme
(`augenarzt`/`augenheilkunde`, `hausarzt`/`allgemeinmedizin`,
`orthopaede`/`orthopadie`, …).

```bash
doctolib specialities
doctolib specialities --json | jq '.count'
```

### `doctolib watch …`

Lokale Watchliste auf `slots`, ohne Buchung. Persistiert unter
`$XDG_CONFIG_HOME/doctolib-cli/watch.json` (atomar geschrieben).
`check` ruft `slots.slots_for_profile` pro Watch live auf und meldet
Treffer **vor `--before`** als `hits[]`; `last_checked` wird nach
jedem `check` persistiert.

```bash
doctolib watch add hautarzt/berlin/kosar-hedayat \
    --motive 4711 --insurance public --before 2026-12-01 --json
doctolib watch list
doctolib watch check --json
doctolib watch remove 1d94bd77
```

* `add` mit gleicher `(profile, motive)`-Kombination **updated**
  (idempotent auf IDs, neue Optionen werden übernommen) statt zu duplizieren.
* `remove` auf unbekannte ID → Exit 1 (klares Signal für Agenten,
  kein stilles No-op).
* `check` auf leere Liste → Exit 0, leere `hits`.

### `doctolib book …`

**Immer Exit 5** (`kind: unsupported`), mit oder ohne `--confirm`.
Dokumentation der Grenze: das Tool **kann und darf nicht buchen**.
Ein `--confirm` macht keinen Unterschied – das ist Absicht, damit
Agenten nicht versehentlich buchen.

```bash
doctolib book "foo" "bar" --confirm --json
# {"error": {"kind": "unsupported", "code": 5, ...}}
```

## Exit-Codes

| Code | Bedeutung |
| ---- | -------- |
| 0    | OK |
| 1    | Usage / Validierung (Args, Config, Env) |
| 2    | Auth / Session (Login fehlt/ungültig/abgelaufen) |
| 3    | Netzwerk / HTTP (Timeout, 5xx, Verbindungsfehler, Bot-Wall) |
| 4    | Parse / unerwartete Antwort |
| 5    | Forbidden / Aktion ohne `--confirm` (auch `book`) |

Bei `--json` liefert jeder Fehler genau ein Objekt der Form
`{"error": {"kind": "usage"|"network"|"parse"|"unsupported"|…, "code": N, "message": "..."}}`.

## Konfiguration / Pfade

* `DOCTOLIB_BASE_URL` (optional, default `https://www.doctolib.de`)
* `XDG_CONFIG_HOME` oder `$HOME/.config` →
  `…/doctolib-cli/{watch.json, …}`
* `ACCEPTANCE_SANDBOX=1` aktiviert in Tests die `sitecustomize.py` aus
  `agent-learnings/tests/harness/` (blockt Nicht-Loopback-Netz).

## Grenzen / Was das Tool NICHT tut

* **Buchen** (`book`): verboten, Exit 5. Wir machen hier bewusst
  keine Ausnahme.
* **Login** / eigene Termine: out of scope, das Doctolib-Login ist
  CAPTCHA-/2FA-geschützt.
* **Mehrpraxen-Truncation**: bei Profilen mit sehr vielen
  (visit_motive × agenda × practice × insurance)-Tupeln fragen wir
  maximal 8 Tupel pro `slots`-Invocation ab. `doctolib show` listet die
  vollständige Praxis-/Adressliste.
* **Kein CAPTCHA-Bypass**: Doctolib captcha-geschützte Suchen
  (Telefon/IP-Suche) sind ausgeschlossen.
* **Keine Garantie auf Doctolib-Verfügbarkeit**: Doctolib kann Bot-Walls
  einziehen; dann liefern wir Exit 3 (`network`), nie einen Traceback.

## Tests

```bash
pip install -e .[dev]
pytest -q    # 59 Tests, kein Netz (Fixtures + HttpRecorder-Stub)
```

Die Tests monkeypatchen `doctolib_cli.http._do_get` auf einen
`HttpRecorder`, der mit JSON/HTML-Fixtures aus
`tests/fixtures/builders.py` antwortet. Doctolib wird in Tests nie live
kontaktiert.

## Lizenz

MIT – siehe `LICENSE`. Kein Login, keine Session, keine Credentials im
Repo, keine erfundenen Patientendaten.