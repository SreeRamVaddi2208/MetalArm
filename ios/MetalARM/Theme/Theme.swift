//
//  Theme.swift
//  MetalARM
//
//  Design tokens: the minimal design system, the same values as the web app's
//  frontend/metalarm/theme.py (see frontend/DESIGN_SYSTEM.md). Near-black
//  neutrals and ONE accent, Forge orange; danger red for destructive actions
//  only; rank-tier colours only inside RankBadge and the rank-up overlay.
//
//  Views use these tokens and the primitives in Components.swift - never a
//  raw colour, size or radius (scripts/check_ios_tokens.py enforces it).
//

import SwiftUI

extension Color {
    init(hex: UInt32, opacity: Double = 1) {
        self.init(
            red: Double((hex >> 16) & 0xFF) / 255,
            green: Double((hex >> 8) & 0xFF) / 255,
            blue: Double(hex & 0xFF) / 255,
            opacity: opacity)
    }
}

enum Theme {
    // MARK: Colour

    static let bg = Color(hex: 0x0E0E10)
    static let surface = Color(hex: 0x17171A)
    static let surface2 = Color(hex: 0x202024)
    /// 1 pt hairlines and input outlines only.
    static let border = Color(hex: 0x2A2A2F)
    static let text = Color(hex: 0xF4F4F2)
    static let text2 = Color(hex: 0xA1A1A8)
    /// Placeholders, "last time" ghosts, disabled.
    static let text3 = Color(hex: 0x6E6E76)
    /// The one accent: the primary button, the active tab, progress fills,
    /// the PR highlight, selected chips.
    static let accent = Color(hex: 0xFF6B2C)
    static let accentSoft = Color(hex: 0xFF6B2C, opacity: 0.14)
    static let onAccent = Color(hex: 0x0E0E10)
    static let danger = Color(hex: 0xE5484D)
    static let scrim = Color(hex: 0x000000, opacity: 0.6)

    /// Rank tiers, E to S. Read only by RankBadge and LevelUpView.
    static let tierColors: [String: Color] = [
        "E": Color(hex: 0x8A6B4E), "D": Color(hex: 0x9AA4AE), "C": Color(hex: 0xD4A93C),
        "B": Color(hex: 0x3FB6B0), "A": Color(hex: 0x5BA8FF), "S": Color(hex: 0xC77DFF),
    ]

    static func tier(_ rank: String) -> Color {
        tierColors[rank.uppercased()] ?? text2
    }

    // MARK: Type

    // Bundled under Fonts/ (SIL Open Font License) and registered through
    // UIAppFonts: Space Grotesk for titles and numbers, Manrope for the rest.
    static let fontNames = [
        "SpaceGrotesk-Regular", "SpaceGrotesk-Medium", "SpaceGrotesk-SemiBold", "SpaceGrotesk-Bold",
        "Manrope-Regular", "Manrope-Medium", "Manrope-SemiBold", "Manrope-Bold",
    ]

    /// The hero number: the timer, the set being entered, the points total.
    static let display = Font.custom("SpaceGrotesk-SemiBold", size: 48, relativeTo: .largeTitle).monospacedDigit()
    /// A screen's title.
    static let titleLG = Font.custom("SpaceGrotesk-SemiBold", size: 28, relativeTo: .title).monospacedDigit()
    /// Section and card titles.
    static let title = Font.custom("SpaceGrotesk-SemiBold", size: 20, relativeTo: .title3).monospacedDigit()
    static let body = Font.custom("Manrope-Medium", size: 16, relativeTo: .body).monospacedDigit()
    /// Buttons and row labels.
    static let label = Font.custom("Manrope-SemiBold", size: 14, relativeTo: .subheadline).monospacedDigit()
    /// Meta, units, timestamps.
    static let caption = Font.custom("Manrope-Medium", size: 12, relativeTo: .caption).monospacedDigit()

    /// Reward moments only (the rank-up overlay): a size outside the scale.
    static func hero(_ size: CGFloat) -> Font {
        .custom("SpaceGrotesk-Bold", size: size, relativeTo: .largeTitle)
    }

    // MARK: Space, size, shape, motion

    enum Space {
        static let s4: CGFloat = 4
        static let s8: CGFloat = 8
        static let s12: CGFloat = 12
        static let s16: CGFloat = 16
        static let s24: CGFloat = 24
        static let s32: CGFloat = 32
        static let s48: CGFloat = 48
    }

    /// Screen side padding.
    static let gutter: CGFloat = 20
    static let cardPadding: CGFloat = 16
    /// Minimum tap target; an icon button is 44.
    static let touch: CGFloat = 48
    static let iconHit: CGFloat = 44
    static let rowMin: CGFloat = 56
    static let buttonHeight: CGFloat = 52

    /// Cards and inputs.
    static let radius: CGFloat = 12
    /// Sheets (top corners).
    static let radiusSheet: CGFloat = 16

    static let fast: Double = 0.15
    static let base: Double = 0.25
}
