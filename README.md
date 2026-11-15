# receiving-check

Check a delivery at the receiving dock. It compares three things: what you ordered (the purchase order), what the supplier says it shipped (the advance ship notice, ASN), and what your team actually scanned off the truck. The result is a line-by-line report and one decision: accept, accept with variances, or hold for review.

## Who it is for

Receiving teams, inventory controllers and buyers in small and mid-size warehouses, stores and stockrooms. A common receiving routine is to count the cartons, compare against the packing slip, and sort out the differences later with the supplier, which is when shorts, overages and wrong items get expensive. A short or damaged line that is caught at the dock becomes a claim against the supplier. If nobody catches it there, it turns up later as a stock loss. This tool does the comparison as soon as the scans are in, and it marks exactly which cartons and SKUs are off.

## What it checks

Per SKU:

| Status or flag | Meaning |
| --- | --- |
| `match` | received what was ordered |
| `short`, `short-ok` | received less than ordered (`-ok`: within the short tolerance) |
| `over`, `over-ok` | received more than ordered (`-ok`: within the over tolerance) |
| `not-on-po` | received or shipped, but not on the purchase order |
| `damaged` | some units were scanned as damaged |
| `asn-short`, `asn-over` | scanned less or more than the ASN says was shipped |
| `not-shipped` | on the PO but not on the ASN (likely a backorder) |

Per carton (when there is an ASN):

| Issue | Meaning |
| --- | --- |
| `missing-carton` | on the ASN, never scanned |
| `unexpected-carton` | scanned, not on the ASN |
| `carton-mismatch` | scanned, but the content differs from the ASN |
| `invalid-sscc` | the carton's SSCC has a wrong GS1 check digit (or is not an SSCC when `require_sscc` is on) |

A rules file decides the tolerances and which problems put the receipt on hold. Everything else that is not clean is a variance.

## Install

Python 3.11 or newer. No runtime dependencies.

```sh
git clone https://github.com/akincenk/receiving-check
cd receiving-check
python3 -m venv .venv && . .venv/bin/activate
pip install -e .            # add '.[dev]' to run the tests
```

## Use

```sh
receiving-check reconcile --po examples/po.csv --asn examples/asn.csv \
    --receipts examples/receipts.csv --rules examples/rules.toml
```

```text
PO-4471: HOLD (not-on-po, damaged, missing-carton)

sku          ordered  shipped  received  damaged  variance  status     flags
WIDGET-0042       48       48        46        2        -2  short      damaged
BOLT-M6-30       500      500       510        0       +10  over-ok    asn-over
TAPE-48MM         72       72        72        0         0  match
BOX-SMALL        200      200       200        0         0  match
GLOVE-L           24       24         0        0       -24  short      asn-short
MARKER-BLK         0        0        12        0       +12  not-on-po  asn-over

Cartons:
  carton-mismatch  006141410000000036  BOLT-M6-30 asn 500 scanned 510
  carton-mismatch  006141410000000043  MARKER-BLK asn 0 scanned 12
  missing-carton   006141410000000050  on the ASN with 24 units, not scanned

6 SKUs, 2 clean, 3 carton issues
```

`--format csv` gives one row per SKU, for a spreadsheet or a claim. `--format json` gives everything, including carton issues. `-o FILE` writes the report to a file.

The exit code tells a script what happened: `0` accept, `1` variances, `3` hold, `2` bad input.

The ASN is optional. Without it, the tool compares the PO with the scans only and skips the carton checks.

### Input files

All CSV with a header row. Column names are not case sensitive; extra columns are ignored.

| File | Columns |
| --- | --- |
| purchase order | `sku`, `qty`, optional `po_number` (use `--po-number` if the file holds several POs) |
| ASN | `carton`, `sku`, `qty` |
| receipt scans | `carton`, `sku`, `qty`, optional `condition` (`ok` or `damaged`) |

Quantities are whole units. Several rows for the same SKU or carton are added up, so a scan log with one row per scan works as well as a summary. A carton can be an SSCC (with or without `(00)` in front) or any internal licence plate number. Every bad line is reported with its file and line number before anything is compared.

### Rules file

```toml
over_tolerance_pct = 5             # accept up to 5% over on a line
short_tolerance_pct = 0
damaged_counts_as_received = false # damaged units go to a claim, not to stock
require_sscc = true                # every carton must carry a valid SSCC
hold_on = ["over", "not-on-po", "damaged", "missing-carton", "invalid-sscc"]
```

Without a rules file there is no tolerance, SSCCs are optional, and the `hold_on` list above is used.

### SSCC helper

```sh
receiving-check sscc 106141411234567897 '(00)006141410000000013'
receiving-check sscc --make 0614141 42      # extension 0, company prefix, serial
```

The sample data uses the company prefix `0614141`, which GS1 uses in its own documentation examples.

## How it works

| File | Role |
| --- | --- |
| `src/receiving_check/loaders.py` | CSV reading and validation (`OrderLine`, `CartonLine`) |
| `src/receiving_check/rules.py` | `Rules`, issue codes, TOML loading |
| `src/receiving_check/sscc.py` | GS1 mod-10 check digit, SSCC normalising and building |
| `src/receiving_check/reconcile.py` | the comparison, `Result` and the decision |
| `src/receiving_check/report.py` | text, CSV and JSON output |
| `src/receiving_check/cli.py` | the `receiving-check` command |

`reconcile()` is a pure function: lists in, a `Result` out, no files or network. The SSCC check digit is tested against the published GS1 example, and the same carton written as `(00)...`, `00...` or bare digits is treated as one carton.

```python
from receiving_check import load_cartons, load_po, reconcile

result = reconcile(load_po("po.csv"), load_cartons("receipts.csv"), load_cartons("asn.csv"))
print(result.decision, result.hold_reasons)
```

## Limits

- One PO per run. An ASN that covers several POs is not split yet.
- Units only: no case-to-each conversion, lot numbers or expiry dates yet.
- SKUs must match exactly between files. Supplier part numbers are not mapped yet.

These are the first items in [ROADMAP.md](ROADMAP.md).

## Development

```sh
pip install -e '.[dev]'
ruff check . && ruff format --check . && pytest -q
```

See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

MIT, see [LICENSE](LICENSE).
