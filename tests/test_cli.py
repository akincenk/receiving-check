import csv
import io
import json

from receiving_check.cli import main


def run(examples, *extra):
    return main(
        [
            "reconcile",
            "--po",
            str(examples / "po.csv"),
            "--asn",
            str(examples / "asn.csv"),
            "--receipts",
            str(examples / "receipts.csv"),
            "--rules",
            str(examples / "rules.toml"),
            *extra,
        ]
    )


def test_text_report_and_hold_exit_code(examples, capsys):
    assert run(examples) == 3
    out = capsys.readouterr().out
    assert out.startswith("PO-4471: HOLD (not-on-po, damaged, missing-carton)")
    assert "missing-carton" in out and "006141410000000050" in out


def test_csv_report(examples, capsys):
    run(examples, "--format", "csv")
    rows = list(csv.DictReader(io.StringIO(capsys.readouterr().out)))
    assert rows[0] == {
        "sku": "WIDGET-0042",
        "ordered": "48",
        "shipped": "48",
        "received": "46",
        "damaged": "2",
        "variance": "-2",
        "status": "short",
        "flags": "damaged",
    }


def test_json_report_to_file(examples, tmp_path, capsys):
    out = tmp_path / "r.json"
    assert run(examples, "--format", "json", "-o", str(out)) == 3
    data = json.loads(out.read_text())
    assert data["decision"] == "hold" and data["lines"][0]["variance"] == -2
    assert "missing-carton" in data["issues"]
    assert "report written to" in capsys.readouterr().out


def test_accept_and_variance_exit_codes(write):
    po = write("po.csv", "sku,qty\nA,2\n")
    assert main(["reconcile", "--po", str(po), "--receipts", str(write("r.csv", "carton,sku,qty\nC,A,2\n"))]) == 0
    assert main(["reconcile", "--po", str(po), "--receipts", str(write("r2.csv", "carton,sku,qty\nC,A,1\n"))]) == 1


def test_bad_input_exit_2(write, capsys):
    po = write("po.csv", "sku,qty\nA,x\n")
    assert main(["reconcile", "--po", str(po), "--receipts", str(po)]) == 2
    assert "not a whole number" in capsys.readouterr().err


def test_sscc_command(capsys):
    assert main(["sscc", "106141411234567897"]) == 0
    assert main(["sscc", "106141411234567890", "LPN-1"]) == 1
    out = capsys.readouterr().out
    assert "expected 7" in out and "not an SSCC" in out


def test_sscc_make_output_is_valid(capsys):
    from receiving_check import sscc

    main(["sscc", "--make", "0614141", "42", "--extension", "3"])
    code = capsys.readouterr().out.strip()
    assert code.startswith("3") and sscc.is_valid(code)
    assert main(["sscc"]) == 2
