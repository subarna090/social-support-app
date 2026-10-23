"""Non-guessable application reference numbers (FR-004, research R4)."""

import secrets

# Crockford base32: no I, L, O or U, so references are easy to read aloud and type.
ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
LENGTH = 10  # 50 bits of randomness


def generate_reference() -> str:
    value = int.from_bytes(secrets.token_bytes(7), "big")
    chars = []
    for _ in range(LENGTH):
        value, index = divmod(value, 32)
        chars.append(ALPHABET[index])
    return "SSA-" + "".join(chars)
