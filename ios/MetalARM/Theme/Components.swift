//
//  Components.swift
//  MetalARM
//
//  The primitives every screen is built from - the iOS twins of the web
//  app's frontend/metalarm/ui/. One primary button per screen, pinned low
//  (`pinnedPrimary`); everything else secondary, ghost or danger. No shadows,
//  no gradients outside reward moments.
//

import SwiftUI

// MARK: - Buttons

enum ButtonKind { case primary, secondary, ghost, danger }

/// 52 pt, full pill. ONE `.primary` per screen.
struct MAButtonStyle: ButtonStyle {
    var kind: ButtonKind = .primary
    var full = true
    @Environment(\.isEnabled) private var isEnabled

    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .font(Theme.label)
            .foregroundStyle(foreground)
            .frame(maxWidth: full ? .infinity : nil, minHeight: Theme.buttonHeight)
            .padding(.horizontal, Theme.Space.s24)
            .background(background(pressed: configuration.isPressed), in: Capsule())
            .overlay { if kind == .secondary || kind == .danger { Capsule().stroke(outline) } }
            .contentShape(Capsule())
            .opacity(isEnabled ? 1 : 0.4)
    }

    private var foreground: Color {
        switch kind {
        case .primary: Theme.onAccent
        case .danger: Theme.danger
        default: Theme.text
        }
    }

    private var outline: Color { kind == .danger ? Theme.danger : Theme.border }

    private func background(pressed: Bool) -> Color {
        switch kind {
        case .primary: Theme.accent.opacity(pressed ? 0.85 : 1)
        default: pressed ? Theme.surface2 : .clear
        }
    }
}

extension ButtonStyle where Self == MAButtonStyle {
    static var primary: MAButtonStyle { MAButtonStyle(kind: .primary) }
    static var secondary: MAButtonStyle { MAButtonStyle(kind: .secondary) }
    static var ghost: MAButtonStyle { MAButtonStyle(kind: .ghost, full: false) }
    static var danger: MAButtonStyle { MAButtonStyle(kind: .danger) }
}

/// A 44 pt icon target with no background until pressed.
struct IconButton: View {
    let systemName: String
    let label: String
    var badge = false
    var tint: Color = Theme.text2
    let action: () -> Void

    var body: some View {
        Button(action: action) {
            Image(systemName: systemName)
                .font(.system(.title3))
                .foregroundStyle(tint)
                .frame(width: Theme.iconHit, height: Theme.iconHit)
                .overlay(alignment: .topTrailing) {
                    if badge {
                        Circle().fill(Theme.accent).frame(width: Theme.Space.s8, height: Theme.Space.s8)
                            .padding(Theme.Space.s8)
                    }
                }
                .contentShape(Rectangle())
        }
        .buttonStyle(.plain)
        .accessibilityLabel(label)
    }
}

// MARK: - Surfaces and rows

extension View {
    /// Surface, 12 pt radius, 16 pt padding. No border, no shadow.
    func card(padding: CGFloat = Theme.cardPadding) -> some View {
        self.padding(padding)
            .frame(maxWidth: .infinity, alignment: .leading)
            .background(Theme.surface, in: RoundedRectangle(cornerRadius: Theme.radius))
    }

    /// The screen's one primary action, pinned above the tab bar.
    func pinnedPrimary<Content: View>(@ViewBuilder _ content: () -> Content) -> some View {
        safeAreaInset(edge: .bottom) {
            content()
                .padding(.horizontal, Theme.gutter)
                .padding(.top, Theme.Space.s12)
                .padding(.bottom, Theme.Space.s8)
                .background(Theme.bg)
        }
    }

    /// A tab's root screen scrolls under the status bar; this keeps the bar
    /// clear so a section title never runs into the clock.
    func statusBarBackdrop() -> some View {
        safeAreaInset(edge: .top, spacing: 0) {
            Color.clear.frame(height: 0).background(Theme.bg, ignoresSafeAreaEdges: .top)
        }
    }

    /// The standard screen frame: scroll, gutters, background.
    func screen() -> some View {
        self.padding(.horizontal, Theme.gutter)
            .padding(.vertical, Theme.Space.s16)
            .frame(maxWidth: .infinity, alignment: .leading)
    }
}

/// Title, subtitle, and an optional trailing value or chevron. 56 pt minimum.
struct ListRow<Leading: View>: View {
    let title: String
    var subtitle: String = ""
    var trailing: String = ""
    var chevron = false
    var titleColor: Color = Theme.text
    @ViewBuilder var leading: () -> Leading

    var body: some View {
        HStack(spacing: Theme.Space.s12) {
            leading()
            VStack(alignment: .leading, spacing: 0) {
                Text(title).font(Theme.body).foregroundStyle(titleColor).lineLimit(1)
                if !subtitle.isEmpty {
                    Text(subtitle).font(Theme.caption).foregroundStyle(Theme.text2).lineLimit(2)
                }
            }
            Spacer(minLength: Theme.Space.s8)
            if !trailing.isEmpty {
                Text(trailing).font(Theme.body).foregroundStyle(Theme.text2)
            }
            if chevron {
                Image(systemName: "chevron.right").font(.system(.footnote, weight: .semibold))
                    .foregroundStyle(Theme.text3)
            }
        }
        .frame(minHeight: Theme.rowMin)
        .contentShape(Rectangle())
    }
}

extension ListRow where Leading == EmptyView {
    init(title: String, subtitle: String = "", trailing: String = "", chevron: Bool = false,
         titleColor: Color = Theme.text) {
        self.init(title: title, subtitle: subtitle, trailing: trailing, chevron: chevron, titleColor: titleColor) {
            EmptyView()
        }
    }
}

/// Rows separated by hairlines.
struct RowGroup<Content: View>: View {
    @ViewBuilder var content: () -> Content

    var body: some View {
        VStack(spacing: 0) {
            Group(subviews: content()) { subviews in
                ForEach(Array(subviews.enumerated()), id: \.offset) { index, subview in
                    if index > 0 { Rectangle().fill(Theme.border).frame(height: 1) }
                    subview
                }
            }
        }
    }
}

/// A titled group of content: spaced, not boxed.
struct SectionBlock<Content: View>: View {
    let title: String
    var action: String = ""
    var onAction: () -> Void = {}
    @ViewBuilder var content: () -> Content

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Space.s12) {
            HStack {
                Text(title).font(Theme.title).foregroundStyle(Theme.text)
                Spacer()
                if !action.isEmpty {
                    Button(action: onAction) {
                        HStack(spacing: Theme.Space.s4) {
                            Text(action).font(Theme.label)
                            Image(systemName: "chevron.right").font(.system(.caption, weight: .semibold))
                        }
                        .foregroundStyle(Theme.text2)
                        .frame(minHeight: Theme.touch)
                    }
                    .buttonStyle(.plain)
                }
            }
            content()
        }
    }
}

// MARK: - Controls

/// A pill: surface-2, accent-soft with accent text when selected.
struct Chip: View {
    let label: String
    var selected = false
    var dot = false
    let action: () -> Void

    var body: some View {
        Button(action: action) {
            HStack(spacing: Theme.Space.s8) {
                if dot {
                    Circle().fill(selected ? Theme.accent : Theme.text2)
                        .frame(width: 6, height: 6).accessibilityLabel("Your path")
                }
                Text(label).font(Theme.label)
            }
            .foregroundStyle(selected ? Theme.accent : Theme.text)
            .padding(.horizontal, Theme.Space.s16)
            .frame(minHeight: 40)
            .background(selected ? Theme.accentSoft : Theme.surface2, in: Capsule())
        }
        .buttonStyle(.plain)
        .accessibilityAddTraits(selected ? .isSelected : [])
    }
}

/// 2-4 options on a surface track.
struct Segmented: View {
    let options: [String]
    let selected: String
    let onSelect: (String) -> Void

    var body: some View {
        HStack(spacing: Theme.Space.s4) {
            ForEach(options, id: \.self) { option in
                Button { onSelect(option) } label: {
                    Text(option).font(Theme.label)
                        .foregroundStyle(option == selected ? Theme.text : Theme.text2)
                        .frame(maxWidth: .infinity, minHeight: 40)
                        .background(option == selected ? Theme.surface2 : .clear, in: Capsule())
                }
                .buttonStyle(.plain)
                .accessibilityAddTraits(option == selected ? .isSelected : [])
            }
        }
        .padding(Theme.Space.s4)
        .background(Theme.surface, in: Capsule())
    }
}

/// A number, its unit, and a small label under it. Groups of 2-3.
struct StatTile: View {
    let value: String
    let label: String
    var unit: String = ""
    var big = false

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Space.s4) {
            HStack(alignment: .firstTextBaseline, spacing: Theme.Space.s4) {
                Text(value).font(big ? Theme.display : Theme.title).foregroundStyle(Theme.text)
                    .lineLimit(1).minimumScaleFactor(0.7)
                if !unit.isEmpty {
                    Text(unit).font(Theme.caption).foregroundStyle(Theme.text2)
                }
            }
            Text(label).font(Theme.caption).foregroundStyle(Theme.text2)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .accessibilityElement(children: .combine)
    }
}

/// 4 pt track in surface-2, accent fill.
struct ProgressBar: View {
    let progress: Double
    var label: String = ""

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Space.s8) {
            GeometryReader { geometry in
                ZStack(alignment: .leading) {
                    Capsule().fill(Theme.surface2)
                    Capsule().fill(Theme.accent)
                        .frame(width: geometry.size.width * max(0, min(1, progress)))
                }
            }
            .frame(height: Theme.Space.s4)
            if !label.isEmpty {
                Text(label).font(Theme.caption).foregroundStyle(Theme.text2)
            }
        }
        .accessibilityElement()
        .accessibilityLabel(label.isEmpty ? "Progress" : label)
        .accessibilityValue("\(Int((progress * 100).rounded())) percent")
    }
}

/// A small tag - the "PR" pill.
struct Pill: View {
    let label: String
    var accent = true

    var body: some View {
        Text(label).font(Theme.caption.weight(.bold))
            .foregroundStyle(accent ? Theme.accent : Theme.text2)
            .padding(.horizontal, Theme.Space.s8)
            .padding(.vertical, 2)
            .background(accent ? Theme.accentSoft : Theme.surface2, in: Capsule())
    }
}

/// The rank as a hexagon in its tier colour - the only tier colour outside
/// the rank-up overlay.
struct RankBadge: View {
    let rank: String
    var size: CGFloat = 48

    var body: some View {
        ZStack {
            Hexagon().stroke(Theme.tier(rank), lineWidth: max(2, size / 16))
            Text(rank.uppercased())
                .font(size >= 96 ? Theme.display : size >= 48 ? Theme.title : Theme.caption.weight(.bold))
                .foregroundStyle(Theme.tier(rank))
        }
        .frame(width: size, height: size)
        .accessibilityElement()
        .accessibilityLabel("Rank \(RankTitle.of(rank))")
    }
}

struct Hexagon: Shape {
    func path(in rect: CGRect) -> Path {
        let w = rect.width, h = rect.height
        var path = Path()
        path.move(to: CGPoint(x: w * 0.25, y: h * 0.05))
        path.addLine(to: CGPoint(x: w * 0.75, y: h * 0.05))
        path.addLine(to: CGPoint(x: w, y: h * 0.5))
        path.addLine(to: CGPoint(x: w * 0.75, y: h * 0.95))
        path.addLine(to: CGPoint(x: w * 0.25, y: h * 0.95))
        path.addLine(to: CGPoint(x: 0, y: h * 0.5))
        path.closeSubpath()
        return path
    }
}

/// Neutral initials circle. Rank is shown by a RankBadge beside it.
struct Avatar: View {
    let initials: String
    var size: CGFloat = 40

    var body: some View {
        Text(initials)
            .font(size >= 96 ? Theme.titleLG : size >= 48 ? Theme.title : Theme.label)
            .foregroundStyle(Theme.text2)
            .frame(width: size, height: size)
            .background(Theme.surface2, in: Circle())
    }
}

// MARK: - States

/// One icon, one sentence, at most one (secondary) action.
struct EmptyState<Action: View>: View {
    let systemImage: String
    let line: String
    @ViewBuilder var action: () -> Action

    var body: some View {
        VStack(spacing: Theme.Space.s12) {
            Image(systemName: systemImage).font(.system(.title2)).foregroundStyle(Theme.text3)
            Text(line).font(Theme.body).foregroundStyle(Theme.text2).multilineTextAlignment(.center)
            action()
        }
        .frame(maxWidth: .infinity)
        .padding(.vertical, Theme.Space.s32)
    }
}

extension EmptyState where Action == EmptyView {
    init(systemImage: String, line: String) {
        self.init(systemImage: systemImage, line: line) { EmptyView() }
    }
}

/// What went wrong, in a sentence, and Try again.
struct ErrorState: View {
    let message: String
    var retry: (() -> Void)?

    var body: some View {
        if !message.isEmpty {
            HStack(alignment: .top, spacing: Theme.Space.s8) {
                Image(systemName: "exclamationmark.circle").foregroundStyle(Theme.text2)
                Text(message).font(Theme.body).foregroundStyle(Theme.text2)
                    .frame(maxWidth: .infinity, alignment: .leading)
                if let retry {
                    Button("Try again", action: retry).buttonStyle(.ghost)
                }
            }
            .accessibilityElement(children: .combine)
        }
    }
}

/// Inline errors, calm: danger red is for destructive actions only.
struct ErrorText: View {
    let message: String

    var body: some View {
        ErrorState(message: message)
    }
}

/// A placeholder block that shimmers - still when Reduce Motion is on.
struct Skeleton: View {
    var height: CGFloat = Theme.rowMin
    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    @State private var lit = false

    var body: some View {
        RoundedRectangle(cornerRadius: Theme.radius)
            .fill(lit ? Theme.surface2 : Theme.surface)
            .frame(height: height)
            .onAppear {
                guard !reduceMotion else { return }
                withAnimation(.easeInOut(duration: 0.9).repeatForever()) { lit = true }
            }
            .accessibilityHidden(true)
    }
}

/// A screen's large title, left-aligned, with one optional trailing action.
struct ScreenTitle<Trailing: View>: View {
    let title: String
    @ViewBuilder var trailing: () -> Trailing

    var body: some View {
        HStack {
            Text(title).font(Theme.titleLG).foregroundStyle(Theme.text)
                .accessibilityAddTraits(.isHeader)
            Spacer()
            trailing()
        }
        .frame(minHeight: Theme.touch)
    }
}

extension ScreenTitle where Trailing == EmptyView {
    init(_ title: String) { self.init(title: title) { EmptyView() } }
}
