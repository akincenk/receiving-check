import pytest

from receiving_check import sscc


def test_check_digit_matches_published_examples():
    # SSCC example from the GS1 General Specifications: (00) 1 0614141 123456789 7
    assert sscc.check_digit("10614141123456789") == 7
    # The same mod-10 rule gives the check digit of a GTIN-13, here 400638133393 -> 1
    assert sscc.check_digit("400638133393") == 1


@pytest.mark.parametrize(
    "code,expected",
    [
        ("106141411234567897", "106141411234567897"),
        ("(00)106141411234567897", "106141411234567897"),
        ("00106141411234567897", "106141411234567897"),
        ("1061 4141 1234 5678 97", "106141411234567897"),
        ("LPN-0042", None),
        ("12345", None),
        ("１０６１４１４１１２３４５６７８９７", None),  # full-width digits are not ASCII
    ],
)
def test_normalize(code, expected):
    assert sscc.normalize(code) == expected


def test_is_valid():
    assert sscc.is_valid("106141411234567897")
    assert not sscc.is_valid("106141411234567898")
    assert not sscc.is_valid("LPN-0042")


def test_make_round_trip():
    code = sscc.make(0, "0614141", 42)
    assert len(code) == 18 and code.startswith("00614141") and sscc.is_valid(code)


@pytest.mark.parametrize("args", [(10, "0614141", 1), (0, "12345", 1), (0, "0614141", "1" * 10), (0, "0614141", -1)])
def test_make_rejects(args):
    with pytest.raises(ValueError):
        sscc.make(*args)


def test_check_digit_rejects_non_digits():
    with pytest.raises(ValueError):
        sscc.check_digit("12a")
