import pytest

from receiving_check import CartonLine, OrderLine, Rules, RulesError, load_rules, reconcile, sscc


def po(**lines):
    return [OrderLine(sku, qty, "PO-1") for sku, qty in lines.items()]


def carton(name, sku, qty, condition="ok"):
    return CartonLine(name, sku, qty, condition)


def by_sku(result):
    return {line.sku: line for line in result.lines}


def test_clean_delivery_is_accepted():
    result = reconcile(po(A=10, B=5), [carton("C1", "A", 10), carton("C1", "B", 5)])
    assert result.decision == "accept" and result.issues == [] and result.hold_reasons == []
    assert all(line.shipped is None for line in result.lines)


def test_short_is_a_variance_by_default():
    result = reconcile(po(A=10), [carton("C1", "A", 7)])
    line = by_sku(result)["A"]
    assert (line.status, line.variance) == ("short", -3)
    assert result.decision == "variance"


def test_over_holds_unless_within_tolerance():
    receipts = [carton("C1", "A", 104)]
    assert reconcile(po(A=100), receipts).decision == "hold"
    result = reconcile(po(A=100), receipts, rules=Rules(over_tolerance_pct=5))
    assert by_sku(result)["A"].status == "over-ok" and result.decision == "variance"
    assert (
        by_sku(reconcile(po(A=100), [carton("C1", "A", 106)], rules=Rules(over_tolerance_pct=5)))["A"].status == "over"
    )


def test_short_tolerance():
    result = reconcile(po(A=100), [carton("C1", "A", 98)], rules=Rules(short_tolerance_pct=2))
    assert by_sku(result)["A"].status == "short-ok"


def test_not_on_po_and_unordered_extra_line_order():
    result = reconcile(po(B=1), [carton("C1", "B", 1), carton("C1", "Z", 2), carton("C1", "A", 1)])
    assert [line.sku for line in result.lines] == ["B", "A", "Z"]
    assert by_sku(result)["Z"].status == "not-on-po"
    assert result.decision == "hold" and result.hold_reasons == ["not-on-po"]


def test_damaged_units():
    receipts = [carton("C1", "A", 8), carton("C1", "A", 2, "damaged")]
    line = by_sku(reconcile(po(A=10), receipts))["A"]
    assert (line.received, line.damaged, line.status, line.flags) == (8, 2, "short", ["damaged"])
    line = by_sku(reconcile(po(A=10), receipts, rules=Rules(damaged_counts_as_received=True)))["A"]
    assert (line.received, line.status) == (10, "match")


def test_asn_comparison_and_cartons():
    asn = [carton("C1", "A", 6), carton("C1", "B", 4), carton("C2", "A", 4), carton("C3", "C", 5)]
    receipts = [carton("C1", "A", 6), carton("C1", "B", 3), carton("C2", "A", 4), carton("C9", "B", 1)]
    result = reconcile(po(A=10, B=4, C=5, D=2), receipts, asn)
    lines = by_sku(result)
    assert (lines["A"].shipped, lines["A"].status, lines["A"].flags) == (10, "match", [])
    assert lines["B"].status == "match" and lines["B"].flags == []  # 3 + 1 from an unexpected carton
    assert lines["C"].flags == ["asn-short"]
    assert lines["D"].flags == ["not-shipped"]
    issues = {(i.code, i.carton) for i in result.cartons}
    assert issues == {("carton-mismatch", "C1"), ("missing-carton", "C3"), ("unexpected-carton", "C9")}
    assert result.decision == "hold" and "missing-carton" in result.hold_reasons


def test_sscc_written_differently_is_the_same_carton():
    code = sscc.make(0, "0614141", 7)
    asn = [carton(code, "A", 5)]
    receipts = [carton(f"(00){code}", "A", 5)]
    result = reconcile(po(A=5), receipts, asn)
    assert result.cartons == [] and result.decision == "accept"


def test_invalid_sscc_and_require_sscc():
    bad = sscc.make(0, "0614141", 7)[:-1] + "0"
    if sscc.is_valid(bad):  # pragma: no cover - the generated check digit happened to be 0
        bad = bad[:-1] + "1"
    result = reconcile(po(A=1), [carton(bad, "A", 1)])
    assert [i.code for i in result.cartons] == ["invalid-sscc"] and result.decision == "hold"
    assert reconcile(po(A=1), [carton("LPN-1", "A", 1)]).decision == "accept"
    strict = reconcile(po(A=1), [carton("LPN-1", "A", 1)], rules=Rules(require_sscc=True))
    assert strict.cartons[0].detail == "not an 18-digit SSCC"


def test_hold_on_can_be_changed():
    receipts = [carton("C1", "A", 10), carton("C1", "A", 1, "damaged")]
    assert reconcile(po(A=10), receipts, rules=Rules(hold_on=())).decision == "variance"
    assert reconcile(po(A=12), [carton("C1", "A", 10)], rules=Rules(hold_on=("short",))).decision == "hold"


def test_duplicate_po_lines_add_up():
    result = reconcile([OrderLine("A", 4), OrderLine("A", 6)], [carton("C1", "A", 10)])
    assert by_sku(result)["A"].ordered == 10 and result.decision == "accept"


@pytest.mark.parametrize(
    "kwargs",
    [{"over_tolerance_pct": -1}, {"short_tolerance_pct": 101}, {"require_sscc": "yes"}, {"hold_on": ("late",)}],
)
def test_invalid_rules(kwargs):
    with pytest.raises(RulesError):
        Rules(**kwargs)


def test_load_rules(examples, write):
    rules = load_rules(examples / "rules.toml")
    assert rules.over_tolerance_pct == 5 and rules.require_sscc
    with pytest.raises(RulesError, match="unknown keys"):
        load_rules(write("r.toml", "speed = 1\n"))
    with pytest.raises(RulesError, match="list of strings"):
        load_rules(write("r.toml", "hold_on = 'over'\n"))
    with pytest.raises(RulesError):
        load_rules(write("r.toml", "over_tolerance_pct = \n"))


def test_example_delivery(examples):
    from receiving_check import load_cartons, load_po

    result = reconcile(
        load_po(examples / "po.csv"),
        load_cartons(examples / "receipts.csv"),
        load_cartons(examples / "asn.csv"),
        load_rules(examples / "rules.toml"),
    )
    assert result.decision == "hold"
    assert result.hold_reasons == ["not-on-po", "damaged", "missing-carton"]
    statuses = {line.sku: line.status for line in result.lines}
    assert statuses == {
        "WIDGET-0042": "short",
        "BOLT-M6-30": "over-ok",
        "TAPE-48MM": "match",
        "BOX-SMALL": "match",
        "GLOVE-L": "short",
        "MARKER-BLK": "not-on-po",
    }
