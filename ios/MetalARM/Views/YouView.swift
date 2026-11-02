//
//  YouView.swift
//  MetalARM
//
//  The You tab: your progress and your profile, one switch apart.
//

import SwiftUI

struct YouView: View {
    private enum Part: String, CaseIterable { case progress = "Progress", profile = "Profile" }

    @State private var part: Part = .progress

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            ScreenTitle("You")
                .padding(.horizontal, Theme.gutter)
            HStack(spacing: Theme.Space.s4) {
                ForEach(Part.allCases, id: \.self) { option in
                    Button { part = option } label: {
                        Text(option.rawValue).font(Theme.label)
                            .foregroundStyle(part == option ? Theme.text : Theme.text2)
                            .frame(maxWidth: .infinity, minHeight: Theme.touch)
                            .background(part == option ? Theme.surface2 : .clear, in: RoundedRectangle(cornerRadius: Theme.radius))
                            .contentShape(Rectangle())
                    }
                    .buttonStyle(.plain)
                    .accessibilityIdentifier("you-\(option.rawValue)")
                    .accessibilityAddTraits(part == option ? .isSelected : [])
                }
            }
            .padding(Theme.Space.s4)
            .background(Theme.surface, in: RoundedRectangle(cornerRadius: Theme.radius))
            .padding(.horizontal, Theme.gutter)
            switch part {
            case .progress: ProgressScreen()
            case .profile: ProfileView()
            }
        }
        .background(Theme.bg)
    }
}
