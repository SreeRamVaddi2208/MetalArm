//
//  Motivation.swift
//  MetalARM
//
//  The line that follows a personal record. Picked from the record's own id
//  rather than at random, for two reasons: the line must not change while the
//  screen re-renders (the summary, the banner and the share card all read it),
//  and the web app picks from the same list by the same rule, so a record shows
//  the same words wherever it is looked at.
//
//  Keep LINES and the rule in step with frontend/metalarm/motivation.py.
//

import Foundation

enum Motivation {
    static let lines = [
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

    /// Sum of the key's unicode scalars, modulo the list. Deliberately simple:
    /// Python's `sum(ord(c) for c in key) % len(LINES)` gives the same answer,
    /// which is what keeps the two apps in agreement.
    static func line(for key: String) -> String {
        guard !lines.isEmpty else { return "" }
        let total = key.unicodeScalars.reduce(0) { $0 + Int($1.value) }
        return lines[total % lines.count]
    }
}
