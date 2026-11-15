"""Receiving rules: tolerances and which problems put a delivery on hold."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field, fields
from pathlib import Path

# Every problem code the reconciler can raise. Line statuses first, then line flags, then carton issues.
ISSUES = (
    "short",
    "short-ok",
    "over",
    "over-ok",
    "not-on-po",
    "damaged",
    "asn-short",
    "asn-over",
    "not-shipped",
    "missing-carton",
    "unexpected-carton",
    "carton-mismatch",
    "invalid-sscc",
)

DEFAULT_HOLD_ON = ("over", "not-on-po", "damaged", "missing-carton", "invalid-sscc")


class RulesError(ValueError):
    """The rules file is not valid."""


@dataclass(frozen=True)
class Rules:
    over_tolerance_pct: float = 0.0
    short_tolerance_pct: float = 0.0
    damaged_counts_as_received: bool = False
    require_sscc: bool = False
    hold_on: tuple[str, ...] = field(default=DEFAULT_HOLD_ON)

    def __post_init__(self) -> None:
        for name in ("over_tolerance_pct", "short_tolerance_pct"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int | float) or not 0 <= value <= 100:
                raise RulesError(f"{name} must be a number from 0 to 100")
        for name in ("damaged_counts_as_received", "require_sscc"):
            if not isinstance(getattr(self, name), bool):
                raise RulesError(f"{name} must be true or false")
        unknown = [code for code in self.hold_on if code not in ISSUES]
        if unknown:
            raise RulesError(f"hold_on has unknown codes {', '.join(unknown)}; known: {', '.join(ISSUES)}")


def load_rules(path: str | Path) -> Rules:
    try:
        with open(path, "rb") as fh:
            data = tomllib.load(fh)
    except tomllib.TOMLDecodeError as exc:
        raise RulesError(f"{path}: {exc}") from exc
    known = {f.name for f in fields(Rules)}
    unknown = sorted(set(data) - known)
    if unknown:
        raise RulesError(f"{path}: unknown keys {', '.join(unknown)}")
    if "hold_on" in data:
        if not isinstance(data["hold_on"], list) or not all(isinstance(x, str) for x in data["hold_on"]):
            raise RulesError(f"{path}: hold_on must be a list of strings")
        data["hold_on"] = tuple(data["hold_on"])
    try:
        return Rules(**data)
    except RulesError as exc:
        raise RulesError(f"{path}: {exc}") from exc
