//
//  OnboardingView.swift
//  MetalARM
//

import SwiftUI

struct OnboardingView: View {
    var onFinish: (AuthView.Mode) -> Void

    var body: some View {
        VStack(spacing: 0) {
            Spacer()
            VStack(spacing: 28) {
                ZStack {
                    RoundedRectangle(cornerRadius: 28)
                        .fill(LinearGradient(colors: [Theme.accent, Theme.accentDeep], startPoint: .topLeading, endPoint: .bottomTrailing))
                    Image(systemName: "bolt.fill")
                        .font(Theme.body(48, .bold))
                        .foregroundStyle(Theme.bg)
                }
                .frame(width: 104, height: 104)
                .shadow(color: Theme.accent.opacity(0.3), radius: 20, y: 16)

                VStack(spacing: 10) {
                    Text("Every rep counts.\nLiterally.")
                        .font(Theme.display(40))
                        .multilineTextAlignment(.center)
                        .foregroundStyle(Theme.text)
                        .accessibilityIdentifier("onboardingTitle")
                    Text("Log your workouts, level up your character, and compete with friends in your party.")
                        .font(Theme.body(15))
                        .foregroundStyle(Theme.dim)
                        .multilineTextAlignment(.center)
                        .frame(maxWidth: 300)
                }
            }
            .padding(32)
            Spacer()
            VStack(spacing: 12) {
                Button("Get Started") { onFinish(.signUp) }
                    .buttonStyle(PrimaryButtonStyle())
                    .accessibilityIdentifier("getStartedButton")
                Button("I already have an account") { onFinish(.signIn) }
                    .buttonStyle(SecondaryButtonStyle())
                    .accessibilityIdentifier("haveAccountButton")
            }
            .padding(.horizontal, 24)
            .padding(.bottom, 40)
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .background {
            ZStack {
                Theme.bg
                RadialGradient(colors: [Theme.accent.opacity(0.18), .clear], center: .top, startRadius: 0, endRadius: 420)
            }
            .ignoresSafeArea()
        }
    }
}

#Preview {
    OnboardingView { _ in }
        .preferredColorScheme(.dark)
}
