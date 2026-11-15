import pytest

from receiving_check import InputError, load_cartons, load_po


def test_load_examples(examples):
    po = load_po(examples / "po.csv")
    assert [(line.sku, line.qty) for line in po][:2] == [("WIDGET-0042", 48), ("BOLT-M6-30", 500)]
    assert po[0].po_number == "PO-4471"
    receipts = load_cartons(examples / "receipts.csv")
    assert receipts[3].condition == "damaged"


def test_headers_are_case_insensitive(write):
    path = write("po.csv", "SKU,Qty\nA,1\n")
    assert load_po(path)[0].qty == 1


def test_po_errors_list_every_line(write):
    path = write("po.csv", "sku,qty\nA,1\n,2\nB,zero\nC,0\nD,1.5\n")
    with pytest.raises(InputError) as info:
        load_po(path)
    assert [e.split(": ", 1)[0].split()[-1] for e in info.value.errors] == ["3", "4", "5", "6"]


def test_several_pos_need_a_choice(write):
    path = write("po.csv", "po_number,sku,qty\nPO-1,A,1\nPO-2,B,2\n")
    with pytest.raises(InputError, match="choose one with --po-number"):
        load_po(path)
    assert [line.sku for line in load_po(path, "PO-2")] == ["B"]
    with pytest.raises(InputError, match="no purchase order 'PO-3'"):
        load_po(path, "PO-3")


def test_missing_columns(write):
    with pytest.raises(InputError, match="missing column"):
        load_cartons(write("r.csv", "carton,qty\nX,1\n"))


def test_carton_errors(write):
    path = write("r.csv", "carton,sku,qty,condition\n,A,1,ok\nC1,,1,ok\nC1,A,-1,ok\nC1,A,1,wet\n")
    with pytest.raises(InputError) as info:
        load_cartons(path)
    text = "\n".join(info.value.errors)
    for expected in ["empty carton", "empty sku", "not a whole number", "condition 'wet'"]:
        assert expected in text


def test_empty_file(write):
    with pytest.raises(InputError, match="empty"):
        load_po(write("po.csv", ""))
