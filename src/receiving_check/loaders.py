"""Reading purchase orders, ship notices and receipt scans from CSV."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

MAX_ERRORS_SHOWN = 10
CONDITIONS = ("ok", "damaged")


class InputError(ValueError):
    """An input file cannot be used. ``errors`` holds one message per problem."""

    def __init__(self, errors: list[str]):
        self.errors = errors
        shown = errors[:MAX_ERRORS_SHOWN]
        more = len(errors) - len(shown)
        super().__init__("\n".join(shown) + (f"\n... and {more} more" if more else ""))


@dataclass(frozen=True)
class OrderLine:
    """A line of the purchase order: what was bought."""

    sku: str
    qty: int
    po_number: str = ""
    line: int = 0


@dataclass(frozen=True)
class CartonLine:
    """A SKU and quantity in a carton, from the ship notice (ASN) or from scanning at the dock."""

    carton: str
    sku: str
    qty: int
    condition: str = "ok"
    line: int = 0


def _rows(path: str | Path, required: list[str]):
    with open(path, newline="", encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        if reader.fieldnames is None:
            raise InputError([f"{path}: file is empty"])
        names = [n.strip().lower() for n in reader.fieldnames]
        missing = [c for c in required if c not in names]
        if missing:
            raise InputError([f"{path}: missing column(s) {', '.join(missing)} (found: {', '.join(names)})"])
        reader.fieldnames = names
        for row in reader:
            yield reader.line_num, {k: (v or "").strip() for k, v in row.items() if k}


def _qty(text: str, allow_zero: bool) -> int:
    if not text.isdigit() or not text.isascii():
        raise ValueError(f"quantity {text!r} is not a whole number")
    value = int(text)
    if value == 0 and not allow_zero:
        raise ValueError("quantity must be greater than 0")
    return value


def load_po(path: str | Path, po_number: str | None = None) -> list[OrderLine]:
    """Read a purchase order CSV with columns ``sku`` and ``qty`` (``po_number`` optional).

    If the file holds several purchase orders, ``po_number`` picks one.
    """
    lines: list[OrderLine] = []
    errors: list[str] = []
    for num, row in _rows(path, ["sku", "qty"]):
        po = row.get("po_number", "")
        if po_number is not None and po != po_number:
            continue
        if not row["sku"]:
            errors.append(f"{path} line {num}: empty sku")
            continue
        try:
            lines.append(OrderLine(row["sku"], _qty(row["qty"], allow_zero=False), po, num))
        except ValueError as exc:
            errors.append(f"{path} line {num}: {exc}")
    if errors:
        raise InputError(errors)
    if not lines:
        what = f"purchase order {po_number!r}" if po_number is not None else "order lines"
        raise InputError([f"{path}: no {what} found"])
    numbers = sorted({line.po_number for line in lines})
    if len(numbers) > 1:
        raise InputError([f"{path}: several purchase orders ({', '.join(numbers)}); choose one with --po-number"])
    return lines


def load_cartons(path: str | Path, allow_zero: bool = False) -> list[CartonLine]:
    """Read an ASN or receipt CSV with columns ``carton``, ``sku``, ``qty`` (``condition`` optional)."""
    lines: list[CartonLine] = []
    errors: list[str] = []
    for num, row in _rows(path, ["carton", "sku", "qty"]):
        condition = (row.get("condition") or "ok").lower()
        problems = []
        if not row["carton"]:
            problems.append("empty carton")
        if not row["sku"]:
            problems.append("empty sku")
        if condition not in CONDITIONS:
            problems.append(f"condition {condition!r} is not one of {', '.join(CONDITIONS)}")
        try:
            qty = _qty(row["qty"], allow_zero)
        except ValueError as exc:
            problems.append(str(exc))
        if problems:
            errors.extend(f"{path} line {num}: {p}" for p in problems)
            continue
        lines.append(CartonLine(row["carton"], row["sku"], qty, condition, num))
    if errors:
        raise InputError(errors)
    return lines
