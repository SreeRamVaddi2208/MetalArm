//
//  Theme.swift
//  MetalARM
//
//  Design tokens from frontend/frontend/styles.py (the MetalArm design canvas:
//  dark, molten fire + violet accents). oklch values converted to sRGB.
//

import SwiftUI

enum Theme {
    static let bg = Color(red: 0.020, green: 0.036, blue: 0.068)
    static let bg2 = Color(red: 0.048, green: 0.077, blue: 0.130)
    static let card = Color(red: 0.077, green: 0.103, blue: 0.159)
    static let cardBorder = Color(red: 0.146, green: 0.179, blue: 0.250)
    static let text = Color(red: 0.946, green: 0.962, blue: 0.988)
    static let dim = Color(red: 0.573, green: 0.598, blue: 0.647)
    static let faint = Color(red: 0.345, green: 0.367, blue: 0.413)
    static let fire = Color(red: 0.988, green: 0.420, blue: 0.200)
    static let fireDeep = Color(red: 0.800, green: 0.143, blue: 0.240)
    static let violet = Color(red: 0.638, green: 0.429, blue: 0.940)
    static let violetDeep = Color(red: 0.413, green: 0.156, blue: 0.692)
    static let green = Color(red: 0.295, green: 0.796, blue: 0.444)
    static let gold = Color(red: 0.891, green: 0.723, blue: 0.192)
    static let goldDeep = Color(red: 0.719, green: 0.424, blue: 0.000)

    // The design's typefaces, bundled under Fonts/ (SIL Open Font License) and
    // registered through UIAppFonts: Space Grotesk for headings and numbers,
    // Manrope for everything else - the same pair the web app uses.
    static let fontNames = [
        "SpaceGrotesk-Regular", "SpaceGrotesk-Medium", "SpaceGrotesk-SemiBold", "SpaceGrotesk-Bold",
        "Manrope-Regular", "Manrope-Medium", "Manrope-SemiBold", "Manrope-Bold",
    ]

    /// Headings, numbers and buttons (Space Grotesk).
    static func display(_ size: CGFloat, _ weight: Font.Weight = .bold) -> Font {
        .custom(face("SpaceGrotesk", weight), fixedSize: size)
    }

    /// Body text, labels and captions (Manrope).
    static func body(_ size: CGFloat, _ weight: Font.Weight = .regular) -> Font {
        .custom(face("Manrope", weight), fixedSize: size)
    }

    /// The bundled static weights are 400-700, so heavier requests use Bold.
    private static func face(_ family: String, _ weight: Font.Weight) -> String {
        switch weight {
        case .bold, .heavy, .black: "\(family)-Bold"
        case .semibold: "\(family)-SemiBold"
        case .medium: "\(family)-Medium"
        default: "\(family)-Regular"
        }
    }
}

struct PrimaryButtonStyle: ButtonStyle {
    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .font(Theme.display(16))
            .foregroundStyle(Theme.bg)
            .frame(maxWidth: .infinity)
            .padding(15)
            .background(Theme.fire.opacity(configuration.isPressed ? 0.8 : 1), in: RoundedRectangle(cornerRadius: 14))
    }
}

struct SecondaryButtonStyle: ButtonStyle {
    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .font(Theme.body(15, .semibold))
            .foregroundStyle(Theme.text.opacity(configuration.isPressed ? 0.7 : 1))
            .frame(maxWidth: .infinity)
            .padding(16)
            .overlay(RoundedRectangle(cornerRadius: 16).stroke(Theme.cardBorder))
            .contentShape(RoundedRectangle(cornerRadius: 16))
    }
}

extension View {
    /// The web app's CARD_STYLE: card fill with a 1px border.
    func cardStyle(cornerRadius: CGFloat = 20) -> some View {
        background(Theme.card, in: RoundedRectangle(cornerRadius: cornerRadius))
            .overlay(RoundedRectangle(cornerRadius: cornerRadius).stroke(Theme.cardBorder))
    }
}

/// Fire-to-violet XP progress bar.
struct XPBar: View {
    let progress: Double
    var track: Color = Theme.bg

    var body: some View {
        GeometryReader { geometry in
            ZStack(alignment: .leading) {
                Capsule().fill(track)
                Capsule()
                    .fill(LinearGradient(colors: [Theme.fire, Theme.violet], startPoint: .leading, endPoint: .trailing))
                    .frame(width: geometry.size.width * max(0, min(1, progress)))
            }
        }
        .frame(height: 8)
        .accessibilityElement()
        .accessibilityLabel("Experience")
        .accessibilityValue("\(Int((progress * 100).rounded())) percent")
    }
}

struct StatTile: View {
    let value: String
    let label: String
    var unit: String = ""

    var body: some View {
        VStack(spacing: 2) {
            HStack(alignment: .firstTextBaseline, spacing: 3) {
                Text(value)
                    .font(Theme.display(20, .heavy))
                    .foregroundStyle(Theme.text)
                if !unit.isEmpty {
                    Text(unit)
                        .font(Theme.body(12))
                        .foregroundStyle(Theme.dim)
                }
            }
            Text(label)
                .font(Theme.body(11))
                .foregroundStyle(Theme.dim)
        }
        .frame(maxWidth: .infinity)
        .padding(.vertical, 14)
        .padding(.horizontal, 8)
        .cardStyle(cornerRadius: 16)
    }
}

struct AvatarBadge: View {
    let initials: String
    let size: CGFloat
    let cornerRadius: CGFloat
    let fontSize: CGFloat
    var bordered = false

    var body: some View {
        Text(initials)
            .font(Theme.display(fontSize, .heavy))
            .foregroundStyle(Theme.text)
            .frame(width: size, height: size)
            .background(
                LinearGradient(colors: [Theme.violet, Theme.violetDeep], startPoint: .topLeading, endPoint: .bottomTrailing),
                in: RoundedRectangle(cornerRadius: cornerRadius))
            .overlay {
                if bordered {
                    RoundedRectangle(cornerRadius: cornerRadius).stroke(Theme.fire, lineWidth: 3)
                }
            }
    }
}

/// Backend errors, shown inline the way the web pages do.
struct ErrorText: View {
    let message: String

    var body: some View {
        if !message.isEmpty {
            Text(message)
                .font(Theme.body(12))
                .foregroundStyle(Theme.fire)
                .frame(maxWidth: .infinity, alignment: .leading)
        }
    }
}
