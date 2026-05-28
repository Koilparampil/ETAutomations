"""Carrier pattern definitions and booking-number → carrier lookup."""

import re


CARRIER_PATTERNS = [
    (r"EBKG\d{8}",        "MSC"),
    (r"2\d{8}",         "Maersk"),
    (r"NAM\d{7}",         "CMA"),
    # (r"S3\d{8}",          "Grimaldi"),
]

# Characters that can appear in any booking number — used as EasyOCR allowlist
ALLOWLIST = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"


def carrierID(booking_num: str) -> str:
    """Identify carrier from a booking number string."""
    for pattern, carrier in CARRIER_PATTERNS:
        if carrier == "Maersk":
            if re.fullmatch(pattern, booking_num.upper()):
                return carrier
        else:
            if re.search(pattern, booking_num.upper()):
                return carrier
    return "Error"
