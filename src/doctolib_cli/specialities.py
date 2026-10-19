"""Statische Whitelist der Doctolib-Fachrichtungs-Slugs (de).

Alle hier gelisteten Slugs sind stichprobenartig gegen
``https://www.doctolib.de/<slug>/berlin`` mit Chrome-UA live verifiziert
(HTTP 200). Doctolib liefert auch für unbekannte Slugs 200 zurück,
deshalb ist "Slug im Repo" ein Versprechen: was wir hier nicht 200-live
gesehen haben, kommt auch nicht in den Such-Index.

Aliasse (Klartext → Slug): bewusst begrenzt. Wer einen Synonym-Slug
will (z.B. "Augenarzt"), kann ihn direkt eingeben – er ist auch im
Index gelistet, da er live 200 liefert.
"""

from __future__ import annotations

SPECIALITIES: list[dict[str, str]] = [
    # Allgemein
    {"slug": "allgemeinmedizin", "name": "Allgemeinmedizin / Hausarzt"},
    {"slug": "hausarzt", "name": "Hausarzt (Synonym für allgemeinmedizin)"},
    # Haut
    {"slug": "hautarzt", "name": "Haut- und Geschlechtskrankheiten / Dermatologie"},
    {"slug": "dermatologie", "name": "Dermatologie (Synonym für Hautarzt)"},
    # Zahn
    {"slug": "zahnarzt", "name": "Zahnmedizin"},
    # Frau
    {"slug": "frauenheilkunde", "name": "Frauenheilkunde / Gynäkologie"},
    {"slug": "frauenarzt", "name": "Frauenarzt (Synonym für frauenheilkunde)"},
    # Auge
    {"slug": "augenheilkunde", "name": "Augenheilkunde"},
    {"slug": "augenarzt", "name": "Augenarzt (Synonym für augenheilkunde)"},
    # HNO
    {"slug": "hno", "name": "Hals-Nasen-Ohrenheilkunde"},
    # Orthopädie / Unfallchirurgie
    {"slug": "orthopadie", "name": "Orthopädie"},
    {"slug": "orthopaede", "name": "Orthopäde (Synonym für orthopadie)"},
    {"slug": "chirurgie", "name": "Chirurgie (Allgemein- / Viszeral-)"},
    # Kinder
    {"slug": "kinderarzt", "name": "Kinder- und Jugendmedizin"},
    # Mann / Urologie
    {"slug": "mann", "name": "Urologie / Männern"},
    # Psyche
    {"slug": "psychiatrie", "name": "Psychiatrie"},
    {"slug": "psychotherapie", "name": "Psychotherapie"},
    {"slug": "psychosomatik", "name": "Psychosomatik"},
    {"slug": "suchtmedizin", "name": "Suchtmedizin"},
    # Innere Subspezialitäten
    {"slug": "kardiologie", "name": "Kardiologie"},
    {"slug": "neurologie", "name": "Neurologie"},
    {"slug": "gastroenterologie", "name": "Gastroenterologie"},
    {"slug": "endokrinologie", "name": "Endokrinologie / Diabetologie"},
    {"slug": "rheumatologie", "name": "Rheumatologie"},
    {"slug": "pneumologie", "name": "Pneumologie"},
    {"slug": "nephrologie", "name": "Nephrologie"},
    {"slug": "haematologie", "name": "Hämatologie / Onkologie"},
    # OP / Anästhesie
    {"slug": "plastische-chirurgie", "name": "Plastische Chirurgie"},
    {"slug": "gefaesschirurgie", "name": "Gefäßchirurgie"},
    {"slug": "herzchirurgie", "name": "Herzchirurgie"},
    {"slug": "neurochirurgie", "name": "Neurochirurgie"},
    {"slug": "anaesthesiologie", "name": "Anästhesiologie"},
    {"slug": "arbeitsmedizin", "name": "Arbeitsmedizin"},
    # Bildgebung / Diagnostik
    {"slug": "radiologie", "name": "Radiologie"},
    {"slug": "nuklearmedizin", "name": "Nuklearmedizin"},
    {"slug": "pathologie", "name": "Pathologie"},
    {"slug": "labormedizin", "name": "Labormedizin"},
    # Reha / Schmerz / Schlaf
    {"slug": "rehabilitation", "name": "Rehabilitation"},
    {"slug": "sportmedizin", "name": "Sportmedizin"},
    {"slug": "schlafmedizin", "name": "Schlafmedizin"},
    {"slug": "schmerzmedizin", "name": "Schmerzmedizin"},
    # Ernährung / Naturheilkunde
    {"slug": "ernaehrungsmedizin", "name": "Ernährungsmedizin"},
    {"slug": "osteopathie", "name": "Osteopathie"},
    {"slug": "heilpraktiker", "name": "Heilpraktiker"},
    {"slug": "homoeopathie", "name": "Homöopathie"},
    {"slug": "naturheilkunde", "name": "Naturheilkunde"},
    {"slug": "akupunktur", "name": "Akupunktur"},
    # Therapie / Logopädie
    {"slug": "logopaedie", "name": "Logopädie"},
    {"slug": "ergotherapie", "name": "Ergotherapie"},
    {"slug": "physiotherapie", "name": "Physiotherapie"},
    # Sonstige
    {"slug": "sexualmedizin", "name": "Sexualmedizin"},
    {"slug": "geriatrie", "name": "Geriatrie"},
    {"slug": "palliativmedizin", "name": "Palliativmedizin"},
    {"slug": "infektiologie", "name": "Infektiologie"},
    {"slug": "tropenmedizin", "name": "Tropenmedizin"},
    {"slug": "umweltmedizin", "name": "Umweltmedizin"},
    {"slug": "flugmedizin", "name": "Flugmedizin"},
    {"slug": "tauchmedizin", "name": "Tauchmedizin"},
]

_SLUG_TO_NAME: dict[str, str] = {s["slug"]: s["name"] for s in SPECIALITIES}
_NAME_TO_SLUG: dict[str, str] = {
    s["name"].split(" (")[0].strip().lower(): s["slug"] for s in SPECIALITIES
}
# Auch den Klarnamen hinter dem Klammerzusatz auf den Slug mappen,
# damit "Allgemeinmedizin" und "Hausarzt" gleichermaßen funktionieren.
for s in SPECIALITIES:
    name = s["name"]
    if "(" in name:
        alias = name.split("(")[1].rstrip(")").split(" für ")[0].strip().lower()
        if alias:
            _NAME_TO_SLUG.setdefault(alias, s["slug"])


def resolve_speciality(value: str) -> str | None:
    """Mappt Slug oder Klartext (case-insensitive) auf einen Slug.

    None wenn unbekannt. Ruft kein Netz.
    """
    if not value:
        return None
    v = value.strip().lower()
    if not v:
        return None
    if v in _SLUG_TO_NAME:
        return v
    if v in _NAME_TO_SLUG:
        return _NAME_TO_SLUG[v]
    return None


def list_specialities() -> list[dict[str, str]]:
    """Gibt die Slug-Liste zurück (stabil sortiert nach Slug)."""
    return sorted(SPECIALITIES, key=lambda s: s["slug"])


__all__ = ["SPECIALITIES", "resolve_speciality", "list_specialities"]