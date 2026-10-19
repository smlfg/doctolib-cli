# Doctolib Endpunkte (Recherche 2026-10-19)

Alle Aufrufe mit `User-Agent: Mozilla/5.0 ... Chrome/129.0.0.0 Safari/537.36` und `Accept-Language: de-DE,de;q=0.9`. Doctolib liefert **ohne Playwright** valides HTML + JSON (kein harter Cloudflare-JS-Wall für die getesteten URLs). Wenn ein Endpoint 302/403/410 liefert: Bot-Schutz oder totes Asset.

Base: `https://www.doctolib.de` (Land: `country=de`).

## 1. Suchseite (Trefferliste)

- `GET https://www.doctolib.de/<speciality-slug>/<city-slug>` → HTML (HTTP 200, ~1.6 MB)
- Slug-Form: kleingeschrieben, Umlaute aufgelöst (`hautarzt`, `allgemeinmedizin`, `augenheilkunde`, …).
- Stadt-Slug kleingeschrieben, Bindestriche statt Leerzeichen (`heilbronn`, `berlin`, `bad-homburg-07458`).
- HTML enthält zwei `application/ld+json` Blöcke:
  - `BreadcrumbList` (für Kontext)
  - **`CollectionPage` mit `mainEntity: ItemList` – das ist die Quelle.** Jedes Element ist `Physician`/`MedicalOrganization` mit `name`, `address.{streetAddress,postalCode,addressLocality}`, `availableService`, `url` (Profil-Slug).
- Anzahl Treffer pro Seite: Doctolib paginiert über `?page=N`, die ld+json zeigt die sichtbare Seite (20–30 Treffer, je nach Layout).

Beispiel (verifiziert):
```
curl -sS -A "Mozilla/5.0 ..." https://www.doctolib.de/hautarzt/berlin | grep -oE 'application/ld\+json[^<]{0,4000}'
```

## 2. Profile / Detailseite

- `GET https://www.doctolib.de/<speciality-slug>/<city-slug>/<slug>` → HTML (HTTP 200)
- HTML enthält `application/ld+json` `Physician` mit `name`, `legalName`, `image`, `address.{streetAddress,postalCode,addressLocality,name (Praxisname)}`, `availableService[]` (Besuchsgründe/visit motives), `telephone`, `openingHours`.
- Ebenfalls `BreadcrumbList`.

## 3. Verfügbarkeiten (Slots)

- `GET https://www.doctolib.de/search/availabilities.json?...` → JSON `{availabilities:[{date, slots:[ISO8601]}]}` (HTTP 200)
- Query-Parameter (alle Pflicht, sonst 400):
  - `start_date_time`: ISO8601 mit Offset (`2026-10-19T09:36:31+02:00`)
  - `visit_motive_id`: numerisch (aus Profile verfügbar, Doctolib-interne ID)
  - `agenda_ids`: numerisch (kommagetrennt erlaubt? Doctolib nutzt es meist einzeln)
  - `practice_ids`: numerisch (aus Profile-URL `?pid=practice-635395` → 635395)
  - `insurance_sector`: `public` oder `private`
  - `telehealth=false`, `limit=5` (mehr ist ok)
- Die IDs (`visit_miat-id`, `agenda-ids`, `practice-ids`) müssen aus dem Profile-JSON-Bundle kommen, das Doctolib per microfrontend-Loader nachlädt (siehe Schritt 4). **In Lauf A noch nicht hart gelöst** – Vorbereitung in Lauf B.

## 4. Patient-Health-Search API (für search/filter)

- `GET https://www.doctolib.de/patient-health-search/api/v1/filters?keyword=hautarzt&country=de` → Liste der möglichen Filter (availabilitiesBefore, insuranceSector, telehealth, languages). Liefert **keine** speciality/place-ID-Mappings.
- `GET https://www.doctolib.de/patient-health-search/api/v1/hcp/search?page=0` → Status 206 (Partial Content), wird vom Microfrontend gefetcht. Body ist binär codiert und nicht trivial parsbar.
- **Empfehlung: HTML der Suchseite parsen (ld+json). Das deckt unseren `search`-Befehl vollständig.**

## 5. Slug-Lookup (Sonderfall)

- Doctolib kennt ca. 50 Fachrichtungs-Slugs (`/hautarzt`, `/allgemeinmedizin`, `/augenheilkunde`, …) und ca. 8.000 Stadt-Slugs.
- `specialities` (statisch) liefern wir in Lauf A/B als bekannte Liste.
- Für die `search`-Validierung reicht es, Eingabe (z.B. `hautarzt berlin`) anhand einer Whitelist/Heuristik zu mappen (Klartext→Slug) und Doctolib die harte Validierung machen zu lassen (404 = klares Signal).

## 7. Profile-JSON, Profil (für slots)

- Profilseite triggert zusätzlich `https://www.doctolib.de/search/availabilities.json?…&practice_ids=<ID>` direkt im HTML. Die `practice_ids` stammen aus dem `?pid=practice-635395` in der Profil-URL.
- Für `slots` in Lauf B/C brauchen wir: `practice_id` (aus URL), `visit_motive_id`s (aus ld+json `availableService` – Doctolib-ID ist nicht der Service-Name). Workaround: Profile-HTML nach `data-visit-motive-id` o.ä. scannen, oder den Microfrontend-Manifest-JSON parsen.

## 6. Was wir NICHT tun

- Login (eigene Termine) – out-of-scope, nur Stub mit Env-Variablen.
- **Buchen** – verbieten wir hart (`exit 5 + JSON-Hinweis "book nicht unterstützt"`), egal ob mit oder ohne `--confirm`.
- IP-, Telefon- oder Adress-Suche – Doctolib captcha-geschützt, auslassen.