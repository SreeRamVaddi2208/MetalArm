//
//  Rank.swift
//  MetalARM
//
//  Rank letters are what the server stores (and what trials_passed records, as
//  a string like "BA"), so the ladder stays E-D-C-B-A-S in the database and the
//  API. The app never shows a letter: it shows the lifting tier the letter
//  stands for, which is also how the rank trials are framed (a bench at 1x
//  bodyweight, a squat at 1.5x, a deadlift at 2x).
//

import Foundation

enum RankTitle {
    /// Ascending, so a UI that needs the ladder can read it here.
    static let ladder: [(letter: String, title: String)] = [
        ("E", "Untrained"),
        ("D", "Novice"),
        ("C", "Intermediate"),
        ("B", "Advanced"),
        ("A", "Elite"),
        ("S", "World Class"),
    ]

    private static let titles = Dictionary(uniqueKeysWithValues: ladder.map { ($0.letter, $0.title) })

    /// The tier for a rank letter. An unknown letter is shown as it came, so a
    /// future rank added server-side is never rendered as an empty label.
    static func of(_ letter: String) -> String {
        titles[letter.uppercased()] ?? letter
    }

    /// For the celebration, where the tier is set in display type.
    static func shout(_ letter: String) -> String {
        of(letter).uppercased()
    }

    /// "Advanced, Elite and World Class" - the trials sentence in Profile.
    static func list(_ letters: [String]) -> String {
        let names = letters.map(of)
        guard names.count > 1, let last = names.last else { return names.first ?? "" }
        return names.dropLast().joined(separator: ", ") + " and " + last
    }
}
