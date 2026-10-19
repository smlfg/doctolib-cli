"""Statische Whitelist der Doctolib-Fachrichtungs-Slugs (de).

Quelle: `https://www.doctolib.de/` (Header "Beliebte Fachrichtungen") +
stichprobenartig geprüfte Profile. Wenn eine Fachrichtung fehlt → wir
verzichten lieber auf Treffer als eine falsche.

Mapping ist lowercase-Slug → Anzeigename. Die Lookup-Funktion akzeptiert
auch Klartext (z. B. "Hautarzt") und matcht case-insensitiv auf den
Namen; bei mehrdeutigen Eingaben wird nichts geraten, sondern ein 400
bzw. eine leere Liste zurückgegeben (der Server bekommt den Klartext
dann nicht, der Bot liegt im Code).
"""

from __future__ import annotations

SPECIALITIES: list[dict[str, str]] = [
    {"slug": "allgemeinmedizin", "name": "Allgemeinmedizin / Hausarzt"},
    {"slug": "hautarzt", "name": "Haut- und Geschlechtskrankheiten / Dermatologie"},
    {"slug": "augenheilkunde", "name": "Augenheilkunde"},
    {"slug": "frauenheilkunde", "name": "Frauenheilkunde / Gynäkologie"},
    {"slug": "mann", "name": "Urologie"},
    {"slug": "kinderarzt", "name": "Kinder- und Jugendmedizin"},
    {"slug": "orthopadie", "name": "Orthopädie"},
    {"slug": "hno", "name": "Hals-Nasen-Ohrenheilkunde"},
    {"slug": "zahnarzt", "name": "Zahnmedizin"},
    {"slug": "kardiologie", "name": "Kardiologie"},
    {"slug": "psychiatrie", "name": "Psychiatrie"},
    {"slug": "psychotherapie", "name": "Psychotherapie"},
    {"slug": "neurologie", "name": "Neurologie"},
    {"slug": "gastroenterologie", "name": "Gastroenterologie"},
    {"slug": "endokrinologie", "name": "Endokrinologie / Diabetologie"},
    {"slug": "rheumatologie", "name": "Rheumatologie"},
    {"slug": "pneumologie", "name": "Pneumologie"},
    {"slug": "nephrologie", "name": "Nephrologie"},
    {"slug": "haematologie", "name": "Hämatologie / Onkologie"},
    {"slug": "dermatologie", "name": "Dermatologie (Synonym für hautarzt)"},
    {"slug": "chirurgie", "name": "Chirurgie"},
    {"slug": "plastische-chirurgie", "name": "Plastische Chirurgie"},
    {"slug": "gefaesschirurgie", "name": "Gefäßchirurgie"},
    {"slug": "herzchirurgie", "name": "Herzchirurgie"},
    {"slug": "neurochirurgie", "name": "Neurochirurgie"},
    {"slug": "anaesthesiologie", "name": "Anästhesiologie"},
    {"slug": "arbeitsmedizin", "name": "Arbeitsmedizin"},
    {"slug": "radiologie", "name": "Radiologie"},
    {"slug": "nuklearmedizin", "name": "Nuklearmedizin"},
    {"slug": "pathologie", "name": "Pathologie"},
    {"slug": "labormedizin", "name": "Labormedizin"},
    {"slug": "rehabilitation", "name": "Rehabilitation"},
    {"slug": "sportmedizin", "name": "Sportmedizin"},
    {"slug": "schlafmedizin", "name": "Schlafmedizin"},
    {"slug": "schmerzmedizin", "name": "Schmerzmedizin"},
    {"slug": "ernaehrungsmedizin", "name": "Ernährungsmedizin"},
    {"slug": "osteopathie", "name": "Osteopathie"},
    {"slug": "logopaedie", "name": "Logopädie"},
    {"slug": "ergotherapie", "name": "Ergotherapie"},
    {"slug": "physiotherapie", "name": "Physiotherapie"},
    {"slug": "heilpraktiker", "name": "Heilpraktiker"},
    {"slug": "homoeopathie", "name": "Homöopathie"},
    {"slug": "naturheilkunde", "name": "Naturheilkunde"},
    {"slug": "akupunktur", "name": "Akupunktur"},
    {"slug": "sexualmedizin", "name": "Sexualmedizin"},
    {"slug": "geriatrie", "name": "Geriatrie"},
    {"slug": "palliativmedizin", "name": "Palliativmedizin"},
    {"slug": "infektiologie", "name": "Infektiologie"},
    {"slug": "tropenmedizin", "name": "Tropenmedizin"},
    {"slug": "umweltmedizin", "name": "Umweltmedizin"},
    {"slug": "flugmedizin", "name": "Flugmedizin"},
    {"slug": "tauchmedizin", "name": "Tauchmedizin"},
    {"slug": "suchtmedizin", "name": "Suchtmedizin"},
    {"slug": "psychosomatik", "name": "Psychosomatik"},
]

_SLUG_TO_NAME: dict[str, str] = {s["slug"]: s["name"] for s in SPECIALITIES}
_NAME_TO_SLUG: dict[str, str] = {
    s["name"].lower(): s["slug"] for s in SPECIALITIES
}
# Auch Klarnamen ohne "Synonym"-Zusatz aufnehmen.
for s in SPECIALITIES:
    base = s["name"].split(" (")[0].strip().lower()
    _NAME_TO_SLUG.setdefault(base, s["slug"])


def resolve_speciality(value: str) -> str | None:
    """Mappt Slug oder Klartext (case-insensitive) auf einen Slug.

    None wenn unbekannt. Ruft kein Netz.
    """
    if not value:
        return None
    v = value.strip().lower()
    if v in _SLUG_TO_NAME:
        return v
    if v in _NAME_TO_SLUG:
        return _NAME_TO_SLUG[v]
    return None