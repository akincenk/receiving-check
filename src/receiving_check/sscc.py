"""GS1 SSCC (Serial Shipping Container Code) check digits.

An SSCC is 18 digits: an extension digit, the company prefix and a serial number, then a mod-10
check digit. On labels it is often printed with its application identifier ``(00)`` in front.
"""

from __future__ import annotations


def check_digit(digits: str) -> int:
    """GS1 mod-10 check digit for a string of digits (without the check digit)."""
    if not digits.isdigit() or not digits.isascii():
        raise ValueError("only digits 0-9 are allowed")
    # Weights 3 and 1 alternate, starting with 3 on the rightmost digit.
    total = sum(int(d) * (3 if i % 2 == 0 else 1) for i, d in enumerate(reversed(digits)))
    return (10 - total % 10) % 10


def normalize(code: str) -> str | None:
    """Return the 18-digit SSCC if ``code`` looks like one, else None.

    Accepts ``(00)`` + 18 digits, ``00`` + 18 digits, and 18 digits, with spaces ignored. Anything
    else (for example an internal licence plate like ``LPN-0042``) is not treated as an SSCC.
    """
    text = code.replace(" ", "")
    if text.startswith("(00)"):
        text = text[4:]
    elif len(text) == 20 and text.startswith("00"):
        text = text[2:]
    if len(text) == 18 and text.isdigit() and text.isascii():
        return text
    return None


def is_valid(code: str) -> bool:
    sscc = normalize(code)
    return sscc is not None and check_digit(sscc[:17]) == int(sscc[17])


def make(extension: int, company_prefix: str, serial: int | str) -> str:
    """Build a valid SSCC from its parts, padding the serial with zeros."""
    if not 0 <= extension <= 9:
        raise ValueError("extension digit must be 0-9")
    if not company_prefix.isdigit() or not 6 <= len(company_prefix) <= 12:
        raise ValueError("company prefix must be 6 to 12 digits")
    serial_text = str(serial)
    room = 16 - len(company_prefix)
    if not serial_text.isdigit() or len(serial_text) > room:
        raise ValueError(f"serial must be at most {room} digits for this company prefix")
    body = f"{extension}{company_prefix}{serial_text.zfill(room)}"
    return body + str(check_digit(body))
