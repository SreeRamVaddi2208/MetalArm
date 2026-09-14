//
//  Theme.swift
//  MetalARM
//
//  Design tokens: MetalArm's grey, machined-steel identity. Near-black ground,
//  graphite surfaces, white and silver as the only accents; red is kept for
//  errors and destructive actions. The same values as frontend/metalarm/theme.py.
//

import SwiftUI

private extension Color {
    init(hex: UInt32) {
        self.init(
            red: Double((hex >> 16) & 0xFF) / 255,
            green: Double((hex >> 8) & 0xFF) / 255,
            blue: Double(hex & 0xFF) / 255)
    }
}

enum Theme {
    static let bg = Color(hex: 0x0B0B0C)
    static let bg2 = Color(hex: 0x121214)
    static let card = Color(hex: 0x1A1A1D)
    static let cardBorder = Color(hex: 0x2A2A2E)
    static let borderStrong = Color(hex: 0x3A3A40)
    static let text = Color(hex: 0xF2F2F4)
    static let dim = Color(hex: 0xA8A8B0)
    static let faint = Color(hex: 0x7C7C84)
    /// Primary actions, highlights and the XP bar's bright end.
    static let accent = Color(hex: 0xFFFFFF)
    static let accentDeep = Color(hex: 0x9A9AA2)
    /// Metal surfaces: badges, trophies, secondary highlights.
    static let silver = Color(hex: 0xC0C0C8)
    static let silverDeep = Color(hex: 0x6A6A72)
    static let success = Color(hex: 0xB8B8BF)
    /// The one colour left: errors and destructive actions.
    static let danger = Color(hex: 0xE5484D)

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
            .background(Theme.accent.opacity(configuration.isPressed ? 0.8 : 1), in: RoundedRectangle(cornerRadius: 14))
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

/// White-to-silver XP progress bar.
struct XPBar: View {
    let progress: Double
    var track: Color = Theme.bg

    var body: some View {
        GeometryReader { geometry in
            ZStack(alignment: .leading) {
                Capsule().fill(track)
                Capsule()
                    .fill(LinearGradient(colors: [Theme.accent, Theme.accentDeep], startPoint: .leading, endPoint: .trailing))
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
                // Dark silver, so the white initials keep their contrast.
                LinearGradient(colors: [Theme.silverDeep, Theme.borderStrong], startPoint: .topLeading, endPoint: .bottomTrailing),
                in: RoundedRectangle(cornerRadius: cornerRadius))
            .overlay {
                if bordered {
                    RoundedRectangle(cornerRadius: cornerRadius).stroke(Theme.accent, lineWidth: 3)
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
                .foregroundStyle(Theme.danger)
                .frame(maxWidth: .infinity, alignment: .leading)
        }
    }
}
