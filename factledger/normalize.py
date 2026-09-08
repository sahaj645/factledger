"""Bring raw values, periods and scope into a canonical form so that figures written
in different units or fiscal notations can be compared.

All domain vocabulary — unit multipliers, currency symbols, fiscal-year patterns,
scope words — is loaded from factledger/lexicon/ at runtime. None of it is written
into the logic here.
"""

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

_LEXICON = Path(__file__).resolve().parent / "lexicon"
_UNITS = json.loads((_LEXICON / "units.json").read_text(encoding="utf-8"))
_PERIODS = json.loads((_LEXICON / "periods.json").read_text(encoding="utf-8"))
_SCOPE = json.loads((_LEXICON / "scope.json").read_text(encoding="utf-8"))

_NUMBER = re.compile(r"-?\d[\d,]*(?:\.\d+)?")


@dataclass(frozen=True)
class NormalizedValue:
    number: float       # in base units (magnitude applied)
    unit: Optional[str]  # currency code, if one was present
    magnitude: Optional[str]  # the magnitude word that was applied, if any


def normalize_value(raw: str) -> Optional[NormalizedValue]:
    if not raw:
        return None
    match = _NUMBER.search(raw)
    if match is None:
        return None
    number = float(match.group(0).replace(",", ""))

    lowered = raw.lower()
    magnitude, factor = _find_magnitude(lowered)
    unit = _find_currency(lowered)
    return NormalizedValue(number=number * factor, unit=unit, magnitude=magnitude)


def _find_magnitude(lowered: str) -> tuple[Optional[str], float]:
    for word, factor in _UNITS["multipliers"].items():
        if re.search(rf"\b{re.escape(word)}\b", lowered):
            return word, factor
    return None, 1.0


def _find_currency(lowered: str) -> Optional[str]:
    for symbol, code in _UNITS["currencies"].items():
        if symbol.isalpha():
            if re.search(rf"\b{re.escape(symbol)}\b", lowered):
                return code
        elif symbol in lowered:
            return code
    return None


def normalize_period(text: Optional[str]) -> Optional[str]:
    if not text:
        return None
    for entry in _PERIODS:
        match = re.search(entry["regex"], text)
        if match:
            return entry["template"].format(*match.groups())
    return None


def unit_context(text: Optional[str]) -> tuple[Optional[str], Optional[str]]:
    """Find a magnitude word and a currency symbol in surrounding text, such as a
    units legend in a table header or a corner cell. Returns the tokens as written so
    a bare cell value can be reunited with the scale stated in its header."""
    if not text:
        return None, None
    lowered = text.lower()
    magnitude = next((w for w in _UNITS["multipliers"]
                      if re.search(rf"\b{re.escape(w)}\b", lowered)), None)
    currency = None
    for symbol in _UNITS["currencies"]:
        if symbol.isalpha():
            if re.search(rf"\b{re.escape(symbol)}\b", lowered):
                currency = symbol
                break
        elif symbol in lowered:
            currency = symbol
            break
    return magnitude, currency


def normalize_scope(text: Optional[str]) -> Optional[str]:
    if not text:
        return None
    lowered = text.lower()
    for word, canonical in _SCOPE.items():
        if re.search(rf"\b{re.escape(word)}\b", lowered):
            return canonical
    return None
