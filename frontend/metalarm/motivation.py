"""The line that follows a personal record.

Picked from the record's own id rather than at random: the line must not change
as the page re-renders, and the iPhone app picks from the same list by the same
rule, so a record reads the same in both apps.

Keep LINES and the rule in step with ios/MetalARM/API/Motivation.swift.
"""

LINES = [
    "That lift was as solid as a lion.",
    "That bar moved like it owed you money.",
    "Steady as a rack bolted to bedrock.",
    "Smooth as chalk on a cold bar.",
    "Those plates went up like they were foam.",
    "Braced like a bridge in a storm.",
    "That pull came off the floor like it was late for work.",
    "Locked out like a vault door.",
    "That set moved like gravity took the day off.",
    "Tight as a belt on the third notch.",
    "You drove through the floor like it owed you a push.",
    "Bar path straight as a plumb line.",
    "Quiet bar. Loud result.",
    "That rep looked easy. It wasn't.",
]


def line_for(key: str) -> str:
    """Sum of the key's unicode scalars, modulo the list - the same arithmetic
    as Swift's `key.unicodeScalars.reduce(0) { $0 + Int($1.value) }`."""
    if not key or not LINES:
        return LINES[0] if LINES else ""
    return LINES[sum(ord(c) for c in key) % len(LINES)]
