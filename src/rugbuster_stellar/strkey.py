"""Minimal Stellar StrKey validation for account (G...) public keys."""

from __future__ import annotations

import base64
import binascii

_ACCOUNT_ID_VERSION_BYTE = 6 << 3


def is_valid_account_id(value: str) -> bool:
    """Validate version byte, payload length, and CRC16-XModem checksum."""

    if len(value) != 56 or not value.startswith("G"):
        return False
    try:
        decoded = base64.b32decode(value, casefold=False)
    except (binascii.Error, ValueError):
        return False
    if len(decoded) != 35 or decoded[0] != _ACCOUNT_ID_VERSION_BYTE:
        return False
    payload, checksum = decoded[:-2], decoded[-2:]
    expected = binascii.crc_hqx(payload, 0).to_bytes(2, "little")
    return checksum == expected

