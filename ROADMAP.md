# Roadmap

Planned work after the first version, roughly in order. Estimates are for one person and include tests and docs. Each item has a GitHub issue. Total: about 30 hours.

## 1. Read X12 856 ship notices (6 h)

Many suppliers send the ASN as an EDI X12 856 file, not CSV. Parse the hierarchical levels (shipment, order, pack, item: `HL`, `PRF`, `MAN`, `LIN`, `SN1`) into `CartonLine`s, with the element and segment separators read from the `ISA` header. Ship with made-up sample files, test malformed envelopes, and keep the parser free of dependencies.

## 2. Case packs and units of measure (3 h)

Suppliers ship in cases, the PO may be in cases or eaches, and scanners count eaches. Add an item file (`sku`, `uom`, `units_per_case`) and a `uom` column on each input, convert everything to eaches before comparing, and report the original units too.

## 3. Supplier part numbers (2.5 h)

Map the supplier's SKU or part number to yours with a cross-reference CSV. Unknown supplier SKUs are reported as such, not as `not-on-po`. A one-to-many mapping is an error.

## 4. ASN covering several POs (3 h)

Read `po_number` on ASN and receipt lines, reconcile each PO separately in one run and print one decision per PO plus an overall one. Lines without a PO number are matched by SKU if there is only one candidate PO.

## 5. Lots and expiry dates (3 h)

Optional `lot` and `expiry` columns. Report lots received but not on the ASN, and hold on expiry dates closer than a minimum shelf life from the rules file (`min_shelf_life_days`).

## 6. Duplicate scan detection (2 h)

A carton scanned twice doubles its count. With a `scan_id` or `scanned_at` column, flag the same carton and SKU scanned more than once within a short time, and show what the totals would be without the repeats.

## 7. Value of the variances (2 h)

With `unit_cost` on the PO, show the money value of each short, over and damaged line and the total, so the claim to the supplier is ready. Use `Decimal`, not float.

## 8. Claim summary for the supplier (2.5 h)

`receiving-check claim` writes a plain text or Markdown summary of shorts, damages and missing cartons with carton IDs, ready to paste into an email. No sending from the tool.

## 9. Per-supplier rules (2 h)

Allow `[supplier.NAME]` tables in the rules file that override the defaults, chosen with `--supplier` or a `supplier` column on the PO.

## 10. HTML report (2 h)

A single self-contained HTML file (no scripts, no external assets) with the same content as the text report and colours for hold and variance lines, for printing at the dock.

## 11. Watch a folder (2 h)

`receiving-check watch DIR` reconciles each new set of PO, ASN and receipt files matched by PO number and writes the reports next to them. Polling only, no extra dependencies, and files are processed only once they stop changing.
