"""Party invite codes.

Codes get read aloud, retyped from a screenshot, and pasted into chat, so the
alphabet deliberately excludes every character that is ambiguous in common
fonts: 0/O and 1/I/L. That leaves 31 symbols, and an 8-character code gives
31^8 ~= 8.5e11 possibilities - far too sparse to guess, which matters because
the code is the only thing between a stranger and a private party board.
"""

import secrets

ALPHABET = "23456789ABCDEFGHJKMNPQRSTUVWXYZ"
CODE_LENGTH = 8


def generate_invite_code() -> str:
    """A single candidate code.

    `secrets`, not `random`: an invite code is a capability, and a predictable
    PRNG would let someone enumerate live parties.
    """
    return "".join(secrets.choice(ALPHABET) for _ in range(CODE_LENGTH))


def normalize_invite_code(raw: str) -> str:
    """Canonicalize what a human actually types.

    Upper-cases and strips the separators people add when reading a code back
    ("abcd-2345", "ABCD 2345"). Deliberately does NOT try to "correct" O to 0
    or I to 1: neither character is in the alphabet, so a code containing one
    is a typo with no single right interpretation, and silently rewriting it
    could map a wrong code onto a real party.
    """
    return raw.strip().upper().replace("-", "").replace(" ", "")


def is_well_formed(code: str) -> bool:
    """Cheap shape check, used to reject obvious garbage before hitting the DB."""
    return len(code) == CODE_LENGTH and all(ch in ALPHABET for ch in code)
