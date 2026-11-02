//
//  FloatingTabBar.swift
//  MetalARM
//
//  The five tabs, in a pill that floats over the content.
//

import SwiftUI

enum AppTab: String, CaseIterable, Hashable, Identifiable {
    case home = "Home", explore = "Explore", workout = "Workout", library = "Library", you = "You"

    var id: String { rawValue }

    var systemImage: String {
        switch self {
        case .home: "house"
        case .explore: "magnifyingglass"
        case .workout: "plus.circle"
        case .library: "books.vertical"
        case .you: "person"
        }
    }
}

struct FloatingTabBar: View {
    @Binding var selected: AppTab

    var body: some View {
        HStack(spacing: 0) {
            ForEach(AppTab.allCases) { tab in
                Button {
                    selected = tab
                } label: {
                    VStack(spacing: Theme.Space.s4) {
                        Image(systemName: tab.systemImage).font(Theme.title)
                        Text(tab.rawValue).font(Theme.caption)
                    }
                    .foregroundStyle(Theme.text)
                    .frame(maxWidth: .infinity, maxHeight: .infinity)
                    .background { if tab == selected { Capsule().fill(Theme.bg) } }
                    .contentShape(Capsule())
                }
                .buttonStyle(.plain)
                .accessibilityIdentifier("tab-\(tab.rawValue)")
                .accessibilityAddTraits(tab == selected ? .isSelected : [])
            }
        }
        .padding(Theme.Space.s4)
        .frame(height: 68)
        .background(.ultraThinMaterial, in: Capsule())
        .overlay { Capsule().stroke(Theme.border) }
        .padding(.horizontal, Theme.gutter)
        .padding(.bottom, Theme.Space.s4)
    }
}
