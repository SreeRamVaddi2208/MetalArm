//
//  OnboardingView.swift
//  MetalARM
//
//  The first screen: what MetalArm is, and the way in. Calm - no glow.
//

import SwiftUI

struct OnboardingView: View {
    var onFinish: (AuthView.Mode) -> Void

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Space.s24) {
            Spacer()
            Image(systemName: "bolt.fill")
                .font(.system(.largeTitle, weight: .bold))
                .foregroundStyle(Theme.accent)
                .frame(width: Theme.Space.s48 * 2, height: Theme.Space.s48 * 2)
                .background(Theme.accentSoft, in: RoundedRectangle(cornerRadius: Theme.radiusSheet))
            Text("Every rep counts.\nLiterally.")
                .font(Theme.titleLG)
                .foregroundStyle(Theme.text)
                .accessibilityIdentifier("onboardingTitle")
            Text("Log your workouts, level up your character, and compete with friends in your party.")
                .font(Theme.body)
                .foregroundStyle(Theme.text2)
            Spacer()
            VStack(spacing: Theme.Space.s12) {
                Button("Get started") { onFinish(.signUp) }
                    .buttonStyle(.primary)
                    .accessibilityIdentifier("getStartedButton")
                Button("I already have an account") { onFinish(.signIn) }
                    .buttonStyle(.secondary)
                    .accessibilityIdentifier("haveAccountButton")
            }
        }
        .padding(.horizontal, Theme.gutter)
        .padding(.bottom, Theme.Space.s24)
        .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .leading)
        .background(Theme.bg.ignoresSafeArea())
    }
}

#Preview {
    OnboardingView { _ in }
        .preferredColorScheme(.dark)
}
