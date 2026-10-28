import re


def is_valid_pnr(pnr: str) -> bool:
    return re.fullmatch(r"[0-9]{10}", pnr) is not None
