"""Command line: receiving-check reconcile | sscc."""

from __future__ import annotations

import argparse
import sys

from . import sscc
from .loaders import InputError, load_cartons, load_po
from .reconcile import reconcile
from .report import FORMATS
from .rules import Rules, RulesError, load_rules

EXIT = {"accept": 0, "variance": 1, "hold": 3}  # 2 is used for bad input, like argparse


def cmd_reconcile(args: argparse.Namespace) -> int:
    po = load_po(args.po, args.po_number)
    receipts = load_cartons(args.receipts)
    asn = load_cartons(args.asn) if args.asn else None
    rules = load_rules(args.rules) if args.rules else Rules()
    result = reconcile(po, receipts, asn, rules)
    text = FORMATS[args.format](result)
    if args.output:
        with open(args.output, "w", encoding="utf-8", newline="") as fh:
            fh.write(text)
        print(f"{result.po_number or 'delivery'}: {result.decision}, report written to {args.output}")
    else:
        sys.stdout.write(text)
    return EXIT[result.decision]


def cmd_sscc(args: argparse.Namespace) -> int:
    if args.make:
        prefix, serial = args.make
        print(sscc.make(args.extension, prefix, serial))
        return 0
    if not args.codes:
        raise InputError(["give one or more SSCCs to check, or --make PREFIX SERIAL"])
    bad = 0
    for code in args.codes:
        normal = sscc.normalize(code)
        if normal is None:
            print(f"{code}: not an SSCC (18 digits, optionally with (00) in front)")
            bad += 1
        elif sscc.is_valid(normal):
            print(f"{code}: valid")
        else:
            print(f"{code}: wrong check digit, expected {sscc.check_digit(normal[:17])}")
            bad += 1
    return 1 if bad else 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="receiving-check",
        description="Reconcile a delivery: purchase order vs ship notice (ASN) vs what was scanned at the dock.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    rec = sub.add_parser("reconcile", help="compare PO, ASN and receipt scans")
    rec.add_argument("--po", required=True, help="purchase order CSV (sku, qty, optional po_number)")
    rec.add_argument("--receipts", required=True, help="receipt scans CSV (carton, sku, qty, optional condition)")
    rec.add_argument("--asn", help="advance ship notice CSV (carton, sku, qty)")
    rec.add_argument("--po-number", help="pick one purchase order from a file that holds several")
    rec.add_argument("--rules", help="TOML file with tolerances and hold rules")
    rec.add_argument("--format", choices=list(FORMATS), default="text")
    rec.add_argument("-o", "--output", help="write the report to a file")
    rec.set_defaults(func=cmd_reconcile)

    sc = sub.add_parser("sscc", help="check SSCC check digits, or make one")
    sc.add_argument("codes", nargs="*")
    sc.add_argument("--make", nargs=2, metavar=("PREFIX", "SERIAL"), help="build an SSCC")
    sc.add_argument("--extension", type=int, default=0, help="extension digit for --make (default 0)")
    sc.set_defaults(func=cmd_sscc)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except (InputError, RulesError, ValueError, OSError) as exc:
        print(f"receiving-check: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
