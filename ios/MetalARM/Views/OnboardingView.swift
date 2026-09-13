//
//  OnboardingView.swift
//  MetalARM
//
//  Port of frontend/frontend/pages/onboarding.py.
//

import SwiftUI

struct OnboardingView: View {
    var onFinish: () -> Void

    var body: some View {
        VStack(spacing: 0) {
            Spacer()
            VStack(spacing: 28) {
                ZStack {
                    RoundedRectangle(cornerRadius: 28)
                        .fill(LinearGradient(colors: [Theme.fire, Theme.fireDeep], startPoint: .topLeading, endPoint: .bottomTrailing))
                    Image(systemName: "bolt.fill")
                        .font(.system(size: 48, weight: .bold))
                        .foregroundStyle(Theme.bg)
                }
                .frame(width: 104, height: 104)
                .shadow(color: Theme.fire.opacity(0.3), radius: 20, y: 16)

                VStack(spacing: 10) {
                    Text("Every rep counts.\nLiterally.")
                        .font(Theme.display(40))
                        .multilineTextAlignment(.center)
                        .foregroundStyle(Theme.text)
                        .accessibilityIdentifier("onboardingTitle")
                    Text("Log your workouts, level up your character, and compete with friends on the leaderboard in real time.")
                        .font(.system(size: 15))
                        .foregroundStyle(Theme.dim)
                        .multilineTextAlignment(.center)
                        .frame(maxWidth: 300)
                }
            }
            .padding(32)
            Spacer()
            VStack(spacing: 12) {
                Button("Get Started", action: onFinish)
                    .buttonStyle(PrimaryButtonStyle())
                    .accessibilityIdentifier("getStartedButton")
                // No auth yet — both paths lead to the demo user, as on the web.
                Button("I already have an account", action: onFinish)
                    .buttonStyle(SecondaryButtonStyle())
            }
            .padding(.horizontal, 24)
            .padding(.bottom, 40)
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .background {
            ZStack {
                Theme.bg
                RadialGradient(colors: [Theme.fire.opacity(0.18), .clear], center: .top, startRadius: 0, endRadius: 420)
            }
            .ignoresSafeArea()
        }
    }
}

#Preview {
    OnboardingView {}
        .preferredColorScheme(.dark)
}
