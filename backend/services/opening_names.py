from __future__ import annotations

import re


OPENING_FAMILY_PREFIXES = (
    "Nimzo-Indian Defense",
    "Queen's Gambit Accepted",
    "Queen's Gambit Declined",
    "King's Indian Defense",
    "Queen's Indian Defense",
    "Bogo-Indian Defense",
    "Caro-Kann Defense",
    "Sicilian Defense",
    "French Defense",
    "Italian Game",
    "Ruy Lopez",
    "English Opening",
    "Scandinavian Defense",
    "Alekhine Defense",
    "Modern Defense",
    "Pirc Defense",
    "Philidor Defense",
    "Petrov's Defense",
    "Ponziani Opening",
    "Scotch Game",
    "Four Knights Game",
    "Vienna Game",
    "Bishop's Opening",
    "King's Gambit",
    "Center Game",
    "Queen's Pawn Game",
    "London System",
    "Trompowsky Attack",
    "Dutch Defense",
    "Polish Opening",
    "Nimzowitsch-Larsen Attack",
    "Bird Opening",
    "Reti Opening",
    "Semi-Slav Defense",
    "Grunfeld Defense",
    "Blumenfeld Countergambit",
)

OPENING_FAMILY_ALIASES = (
    ("Kings Pawn Opening", "King's Pawn Game"),
    ("King Pawn Opening", "King's Pawn Game"),
    ("Closed Sicilian Defense", "Sicilian Defense"),
    ("Open Sicilian Defense", "Sicilian Defense"),
    ("Sicilian Defence", "Sicilian Defense"),
    ("Closed Sicilian Defence", "Sicilian Defense"),
)


def extract_opening_family(opening_name: str | None) -> str:
    if not opening_name:
        return "Unknown"
    name = _normalize_opening_name(opening_name)
    family, _variation = _split_opening_name(name)
    return family or "Unknown"


def extract_variation(opening_name: str | None) -> str | None:
    if not opening_name:
        return None
    name = _normalize_opening_name(opening_name)
    _family, variation = _split_opening_name(name)
    return variation or None


def _normalize_opening_name(opening_name: str) -> str:
    return re.sub(r"\s+", " ", opening_name.replace(";", ",")).strip()


def _split_opening_name(opening_name: str) -> tuple[str, str | None]:
    delimiter_match = re.search(r"\s*[:,]\s*", opening_name, flags=re.ASCII)
    if delimiter_match:
        family = opening_name[: delimiter_match.start()].strip()
        variation = opening_name[delimiter_match.end() :].strip()
        family, prefix_variation = _match_known_family(family)
        combined_variation = _join_variations(prefix_variation, variation)
        return family, combined_variation

    return _match_known_family(opening_name)


def _match_known_family(opening_name: str) -> tuple[str, str | None]:
    folded = opening_name.casefold()
    compact = _compact_opening_name(opening_name)

    for alias, family in OPENING_FAMILY_ALIASES:
        alias_compact = _compact_opening_name(alias)
        if compact == alias_compact:
            return family, None
        if compact.startswith(f"{alias_compact} "):
            variation = opening_name[len(alias) :].strip(" ,-:")
            return family, variation or None

    for family in OPENING_FAMILY_PREFIXES:
        family_folded = family.casefold()
        family_compact = _compact_opening_name(family)
        if folded == family_folded or compact == family_compact:
            return family, None
        if folded.startswith(f"{family_folded} ") or compact.startswith(f"{family_compact} "):
            variation = opening_name[len(family) :].strip(" ,-:")
            return family, variation or None

    return opening_name, None


def _compact_opening_name(opening_name: str) -> str:
    compact = opening_name.casefold().replace("'", "")
    compact = re.sub(r"[^a-z0-9]+", " ", compact)
    return re.sub(r"\s+", " ", compact).strip()


def _join_variations(first: str | None, second: str | None) -> str | None:
    parts = [part for part in (first, second) if part]
    return ", ".join(parts) if parts else None
