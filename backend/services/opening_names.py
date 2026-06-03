from __future__ import annotations


def extract_opening_family(opening_name: str | None) -> str:
    if not opening_name:
        return "Unknown"
    family = opening_name.split(":", 1)[0].strip()
    return family or "Unknown"


def extract_variation(opening_name: str | None) -> str | None:
    if not opening_name or ":" not in opening_name:
        return None
    variation = opening_name.split(":", 1)[1].strip()
    return variation or None
