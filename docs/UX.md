# doctolib – Nutzererlebnis

`doctolib` ist eine read-only CLI für die Arztsuche. Sie sucht Ärztinnen und
Ärzte nach Fachrichtung und Ort, zeigt Profile und freie Termine an. Es gibt
keinen Login und keine Buchung.

```ux-meta
{"tool": "doctolib",
 "install": "pipx install git+https://github.com/smlfg/doctolib-cli",
 "base_url_env": "DOCTOLIB_BASE_URL",
 "credential_env": []}
```

## Ärzte suchen

Eine Nutzerin sucht Hautärzte in Heilbronn und bekommt eine nummerierte
Liste mit Name und Adresse.

```ux-session
$ pipx install git+https://github.com/smlfg/doctolib-cli
$ doctolib search hautarzt heilbronn
< Suche: hautarzt in heilbronn
< [1] Dr. med. Sabine Weber – Hautkrebsvorsorge | Hauptstraße 12, 74072 Heilbronn
< [2] Dr. med. Jonas Keller – Akne-Behandlung | Neckarstraße 45, 74076 Heilbronn
< [3] Praxis Dr. med. Elif Yilmaz – Hautkrebsvorsorge | Marktplatz 3, 74072 Heilbronn
< 3 Treffer.
! exit 0
```

## Freie Termine per Name

Die Nutzerin sucht freie Termine über „Fachrichtung Ort“, wählt den ersten
Treffer im Terminal und sieht die Termine mit Datum und Uhrzeit.

```ux-session
$ pipx install git+https://github.com/smlfg/doctolib-cli
$ doctolib slots hautarzt heilbronn
< Nummer wählen [1-3]:
> 1
< Gewählt: Dr. med. Sabine Weber (hautarzt/heilbronn/dr-sabine-weber)
< Freie Termine – Praxis Dr. Sabine Weber
< Hauptstraße 12
< Motiv: Hautkrebsvorsorge (public)
< Di 03.11.2026: 09:00, 10:30
< Mi 04.11.2026: 14:15
< 3 Termin(e).
! exit 0
```

## Profil ansehen und Fachrichtungen

Die Nutzerin lässt sich das erste Suchergebnis als lesbares Profil anzeigen
und listet danach die bekannten Fachrichtungen auf.

```ux-session
$ pipx install git+https://github.com/smlfg/doctolib-cli
$ doctolib show hautarzt heilbronn --pick 1
< Gewählt: Dr. med. Sabine Weber (hautarzt/heilbronn/dr-sabine-weber)
< Dr. med. Sabine Weber (Physician)
< Fachrichtung: Haut- und Geschlechtskrankheiten
< Adresse: Hauptstraße 12, 74072 Heilbronn
< 4711 Hautkrebsvorsorge
< Slug: hautarzt/heilbronn/dr-sabine-weber
$ doctolib specialities
< hautarzt
< Haut- und Geschlechtskrankheiten / Dermatologie
< Fachrichtungen.
! exit 0
```

```ux-routes
[
  {"method": "GET", "path": "/hautarzt/heilbronn", "response": "tests/fixtures/ux/search_hautarzt_heilbronn.html", "status": 200, "content_type": "text/html; charset=utf-8"},
  {"method": "GET", "path": "/hautarzt/heilbronn/dr-sabine-weber", "response": "tests/fixtures/ux/profile_dr_sabine_weber.html", "status": 200, "content_type": "text/html; charset=utf-8"},
  {"method": "GET", "path": "/online_booking/api/slot_selection_funnel/v1/info.json", "response": "tests/fixtures/ux/info_dr_sabine_weber.json", "status": 200, "content_type": "application/json; charset=utf-8", "query_contains": "profile_slug=dr-sabine-weber"},
  {"method": "GET", "path": "/search/availabilities.json", "response": "tests/fixtures/ux/availabilities_dr_sabine_weber.json", "status": 200, "content_type": "application/json; charset=utf-8"}
]
```
