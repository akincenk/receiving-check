"""Rendering a reconciliation as text, CSV or JSON."""

from __future__ import annotations

import csv
import io
import json
from dataclasses import asdict

from .reconcile import Result

COLUMNS = ["sku", "ordered", "shipped", "received", "damaged", "variance", "status", "flags"]


def _cells(result: Result) -> list[list[str]]:
    rows = []
    for line in result.lines:
        shipped = "" if line.shipped is None else str(line.shipped)
        variance = f"{line.variance:+d}" if line.variance else "0"
        rows.append(
            [line.sku, str(line.ordered), shipped, str(line.received), str(line.damaged), variance, line.status]
            + [" ".join(line.flags)]
        )
    return rows


def to_text(result: Result) -> str:
    title = result.po_number or "Delivery"
    reasons = f" ({', '.join(result.hold_reasons)})" if result.hold_reasons else ""
    out = [f"{title}: {result.decision.upper()}{reasons}", ""]
    rows = [COLUMNS, *_cells(result)]
    widths = [max(len(r[c]) for r in rows) for c in range(len(COLUMNS))]
    numeric = {1, 2, 3, 4, 5}
    for row in rows:
        cells = [
            cell.rjust(w) if i in numeric else cell.ljust(w)
            for i, (cell, w) in enumerate(zip(row, widths, strict=True))
        ]
        out.append("  ".join(cells).rstrip())
    if result.cartons:
        out += ["", "Cartons:"]
        code_w = max(len(i.code) for i in result.cartons)
        carton_w = max(len(i.carton) for i in result.cartons)
        out += [f"  {i.code:<{code_w}}  {i.carton:<{carton_w}}  {i.detail}" for i in result.cartons]
    matched = sum(1 for line in result.lines if line.status == "match" and not line.flags)
    out += ["", f"{len(result.lines)} SKUs, {matched} clean, {len(result.cartons)} carton issues"]
    return "\n".join(out) + "\n"


def to_csv(result: Result) -> str:
    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator="\n")
    writer.writerow(COLUMNS)
    writer.writerows(_cells(result))
    return buf.getvalue()


def to_json(result: Result) -> str:
    data = asdict(result)
    for line, raw in zip(data["lines"], result.lines, strict=True):
        line["variance"] = raw.variance
    data["issues"] = result.issues
    return json.dumps(data, indent=2) + "\n"


FORMATS = {"text": to_text, "csv": to_csv, "json": to_json}
