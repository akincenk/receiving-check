"""Compare what was ordered, what the supplier says it shipped, and what was scanned at the dock."""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field

from . import sscc
from .loaders import CartonLine, OrderLine
from .rules import ISSUES, Rules


@dataclass
class LineResult:
    sku: str
    ordered: int
    shipped: int | None  # None when there is no ship notice
    received: int  # units that count as received (damaged only if the rules say so)
    damaged: int
    status: str  # match, short, short-ok, over, over-ok or not-on-po
    flags: list[str] = field(default_factory=list)

    @property
    def variance(self) -> int:
        return self.received - self.ordered


@dataclass
class CartonIssue:
    code: str  # missing-carton, unexpected-carton, carton-mismatch or invalid-sscc
    carton: str
    detail: str


@dataclass
class Result:
    po_number: str
    lines: list[LineResult]
    cartons: list[CartonIssue]
    decision: str  # accept, variance or hold
    hold_reasons: list[str]

    @property
    def issues(self) -> list[str]:
        found = {line.status for line in self.lines if line.status != "match"}
        found.update(flag for line in self.lines for flag in line.flags)
        found.update(issue.code for issue in self.cartons)
        return [code for code in ISSUES if code in found]


def _status(ordered: int, received: int, rules: Rules) -> str:
    diff = received - ordered
    if diff == 0:
        return "match"
    pct = abs(diff) / ordered * 100
    if diff > 0:
        return "over-ok" if pct <= rules.over_tolerance_pct else "over"
    return "short-ok" if pct <= rules.short_tolerance_pct else "short"


def _carton_key(carton: str) -> str:
    # The same SSCC can be written as (00)..., 00... or the bare 18 digits.
    return sscc.normalize(carton) or carton


def _by_carton(lines: list[CartonLine]) -> dict[str, Counter[str]]:
    out: dict[str, Counter[str]] = defaultdict(Counter)
    for line in lines:
        out[_carton_key(line.carton)][line.sku] += line.qty
    return out


def _carton_issues(asn: list[CartonLine] | None, receipts: list[CartonLine], rules: Rules) -> list[CartonIssue]:
    issues: list[CartonIssue] = []
    seen: set[str] = set()
    for line in [*(asn or []), *receipts]:
        key = _carton_key(line.carton)
        if key in seen:
            continue
        seen.add(key)
        normal = sscc.normalize(line.carton)
        if normal is not None and not sscc.is_valid(normal):
            issues.append(CartonIssue("invalid-sscc", key, f"check digit should be {sscc.check_digit(normal[:17])}"))
        elif normal is None and rules.require_sscc:
            issues.append(CartonIssue("invalid-sscc", key, "not an 18-digit SSCC"))
    if asn is None:
        return issues
    shipped, scanned = _by_carton(asn), _by_carton(receipts)
    for carton, content in shipped.items():
        if carton not in scanned:
            units = sum(content.values())
            issues.append(CartonIssue("missing-carton", carton, f"on the ASN with {units} units, not scanned"))
        elif content != scanned[carton]:
            diffs = [
                f"{sku} asn {content.get(sku, 0)} scanned {scanned[carton].get(sku, 0)}"
                for sku in sorted(set(content) | set(scanned[carton]))
                if content.get(sku, 0) != scanned[carton].get(sku, 0)
            ]
            issues.append(CartonIssue("carton-mismatch", carton, "; ".join(diffs)))
    for carton, content in scanned.items():
        if carton not in shipped:
            issues.append(CartonIssue("unexpected-carton", carton, f"scanned with {sum(content.values())} units"))
    return issues


def reconcile(
    po: list[OrderLine],
    receipts: list[CartonLine],
    asn: list[CartonLine] | None = None,
    rules: Rules | None = None,
) -> Result:
    """Reconcile one delivery against its purchase order and, if there is one, its ship notice."""
    rules = rules or Rules()
    ordered: Counter[str] = Counter()
    for line in po:
        ordered[line.sku] += line.qty
    shipped: Counter[str] = Counter()
    for line in asn or []:
        shipped[line.sku] += line.qty
    good: Counter[str] = Counter()
    damaged: Counter[str] = Counter()
    for line in receipts:
        (damaged if line.condition == "damaged" else good)[line.sku] += line.qty

    extra = sorted((set(shipped) | set(good) | set(damaged)) - set(ordered))
    lines: list[LineResult] = []
    for sku in [*ordered, *extra]:
        received = good[sku] + (damaged[sku] if rules.damaged_counts_as_received else 0)
        status = _status(ordered[sku], received, rules) if sku in ordered else "not-on-po"
        flags = ["damaged"] if damaged[sku] else []
        if asn is not None:
            scanned = good[sku] + damaged[sku]
            if scanned < shipped[sku]:
                flags.append("asn-short")
            elif scanned > shipped[sku]:
                flags.append("asn-over")
            if sku in ordered and shipped[sku] == 0:
                flags.append("not-shipped")
        lines.append(
            LineResult(
                sku, ordered[sku], shipped[sku] if asn is not None else None, received, damaged[sku], status, flags
            )
        )

    result = Result(po[0].po_number if po else "", lines, _carton_issues(asn, receipts, rules), "accept", [])
    issues = result.issues
    result.hold_reasons = [code for code in issues if code in rules.hold_on]
    result.decision = "hold" if result.hold_reasons else "variance" if issues else "accept"
    return result
