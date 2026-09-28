//
//  RankTier.swift
//  MetalARM
//
//  What a promotion looks like, per tier - the same table as the web's
//  frontend/metalarm/rank_tiers.py, and it must be kept in step with it, the
//  way RankTitle is kept in step with frontend/metalarm/ranks.py.
//
//  The ladder is E-D-C-B-A-S. Untrained is where everyone starts, so there are
//  five promotions to celebrate and each is louder than the last: Novice is a
//  flourish, World Class is an event. Every tier plays the SAME sequence and
//  differs only in the numbers here, so a sixth tier is a row rather than a
//  second celebration.
//

import SwiftUI

struct RankTier: Equatable {
    /// The rank being entered.
    let rank: String
    let base: Color
    let glow: Color
    let jewel: Color
    /// plain -> laurel -> gems -> crown -> regalia
    let ornament: Ornament
    let rings: Int
    let sparks: Int
    let duration: Double
    /// navigator.vibrate on the web; a pattern of impacts here.
    let haptics: [Double]
    let line: String

    enum Ornament: String, Equatable {
        case plain, laurel, gems, crown, regalia

        var hasLaurel: Bool { self != .plain }
        var hasGems: Bool { self == .gems || self == .crown || self == .regalia }
        var hasCrown: Bool { self == .crown || self == .regalia }
        var hasFiligree: Bool { self == .regalia }
    }

    // The palette, from rank_tiers.py. Steel through white is MetalArm's own;
    // gold and a jewel tone are held back for the top two tiers, which is what
    // makes them read as rarer.
    private static let steel = Color(red: 0x9a / 255, green: 0x9a / 255, blue: 0xa2 / 255)
    private static let bright = Color(red: 0xc0 / 255, green: 0xc0 / 255, blue: 0xc8 / 255)
    private static let pale = Color(red: 0xe0 / 255, green: 0xe0 / 255, blue: 0xe6 / 255)
    private static let white = Color.white
    private static let gold = Color(red: 0xd9 / 255, green: 0xb0 / 255, blue: 0x6a / 255)
    private static let sapphire = Color(red: 0x6f / 255, green: 0x8f / 255, blue: 0xd6 / 255)
    private static let ruby = Color(red: 0xc0 / 255, green: 0x5a / 255, blue: 0x6a / 255)

    /// Ascending, keyed by the rank ENTERED.
    static let all: [String: RankTier] = [
        "D": RankTier(rank: "D", base: steel, glow: steel, jewel: steel,
                      ornament: .plain, rings: 1, sparks: 16, duration: 1.7,
                      haptics: [0], line: "First rung. The bar goes up from here."),
        "C": RankTier(rank: "C", base: bright, glow: bright, jewel: steel,
                      ornament: .laurel, rings: 2, sparks: 18, duration: 2.3,
                      haptics: [0, 0.32], line: "No longer new to this."),
        "B": RankTier(rank: "B", base: pale, glow: pale, jewel: gold,
                      ornament: .gems, rings: 3, sparks: 20, duration: 2.9,
                      haptics: [0, 0.28, 0.56], line: "Advanced. Most people never get here."),
        "A": RankTier(rank: "A", base: white, glow: gold, jewel: sapphire,
                      ornament: .crown, rings: 3, sparks: 22, duration: 3.6,
                      haptics: [0, 0.24, 0.48, 0.72], line: "Elite. The numbers speak for themselves."),
        "S": RankTier(rank: "S", base: white, glow: gold, jewel: ruby,
                      ornament: .regalia, rings: 4, sparks: 18, duration: 4.4,
                      haptics: [0, 0.22, 0.44, 0.66, 0.88, 1.1],
                      line: "World Class. Nothing above this."),
    ]

    /// What a level-up borrows: the shared sequence at its quietest, so the two
    /// beats cannot be confused with each other.
    static let levelUp = RankTier(
        rank: "", base: steel, glow: steel, jewel: steel,
        ornament: .plain, rings: 1, sparks: 16, duration: 1.5,
        haptics: [0], line: "Keep going.")

    /// An unknown or missing rank falls back to the quietest tier rather than
    /// rendering nothing: a celebration that silently does not happen is worse
    /// than a plain one.
    static func of(_ rank: String) -> RankTier {
        all[rank.uppercased()] ?? levelUp
    }

    /// The tier below this one, for the "Elite -> World Class" line.
    static func previous(of rank: String) -> String {
        let ladder = ["E", "D", "C", "B", "A", "S"]
        guard let index = ladder.firstIndex(of: rank.uppercased()), index > 0 else { return "E" }
        return ladder[index - 1]
    }
}
