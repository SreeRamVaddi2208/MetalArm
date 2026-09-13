//
//  ProfileView.swift
//  MetalARM
//
//  Character sheet plus account settings: weight unit, privacy, sign out,
//  and account deletion (required by the App Store for apps with sign-up).
//

import SwiftUI
import UIKit

struct ProfileView: View {
    @Environment(AppModel.self) private var model
    @State private var showingDelete = false
    @State private var confirmingSignOutEverywhere = false

    private let badgeColumns = Array(repeating: GridItem(.flexible(), spacing: 12), count: 4)

    var body: some View {
        ScrollView {
            VStack(spacing: 0) {
                if let profile = model.profile {
                    header(profile)
                    stats(profile.stats)
                    badges(profile)
                }
                settings
                ErrorText(message: model.errorMessage)
                    .padding(.top, 12)
            }
            .padding(20)
        }
        .background(Theme.bg)
        .task { await model.loadProfile() }
        .refreshable { await model.loadProfile() }
        .sheet(isPresented: $showingDelete) { DeleteAccountSheet() }
        .confirmationDialog("Sign out of every device?", isPresented: $confirmingSignOutEverywhere, titleVisibility: .visible) {
            Button("Sign Out Everywhere", role: .destructive) {
                Task { await model.signOutEverywhere() }
            }
        } message: {
            Text("You'll need to sign in again on this and every other device.")
        }
    }

    private func header(_ profile: Profile) -> some View {
        VStack(spacing: 0) {
            AvatarBadge(initials: initials(of: profile.user.displayName), size: 84, cornerRadius: 24, fontSize: 28, bordered: true)
            Text(profile.user.displayName)
                .font(Theme.display(22))
                .foregroundStyle(Theme.text)
                .padding(.top, 12)
            Text("Level \(profile.progress.currentLevel) · Rank \(profile.progress.rank)")
                .font(Theme.body(12.5, .bold))
                .foregroundStyle(Theme.fire)
                .padding(.top, 5)
            XPBar(progress: profile.progress.xpProgress, track: Theme.card)
                .padding(.top, 16)
            Text("\(profile.progress.xpIntoLevel) / \(profile.progress.xpForNextLevel) XP to next level")
                .font(Theme.body(11))
                .foregroundStyle(Theme.dim)
                .padding(.top, 6)
        }
    }

    private func stats(_ stats: LifetimeStats) -> some View {
        HStack(spacing: 12) {
            StatTile(value: "\(stats.workoutsCompleted)", label: "Workouts")
            StatTile(value: "\(stats.workoutPrs)", label: "Workout PRs")
            StatTile(value: "\(stats.longestWorkoutStreak)", label: "Best streak", unit: "wk")
        }
        .padding(.top, 22)
    }

    private func badges(_ profile: Profile) -> some View {
        VStack(spacing: 10) {
            HStack {
                Text("Badges")
                    .font(Theme.display(16))
                    .foregroundStyle(Theme.text)
                Spacer()
                Text("\(profile.badgesEarned) / \(profile.badgesTotal)")
                    .font(Theme.body(12))
                    .foregroundStyle(Theme.fire)
            }
            LazyVGrid(columns: badgeColumns, spacing: 12) {
                ForEach(profile.badges) { badge in
                    badgeTile(badge)
                }
            }
        }
        .padding(.top, 22)
    }

    private func badgeTile(_ badge: Badge) -> some View {
        VStack(spacing: 5) {
            ZStack {
                if badge.earned {
                    RoundedRectangle(cornerRadius: 14)
                        .fill(LinearGradient(colors: [Theme.gold, Theme.goldDeep], startPoint: .topLeading, endPoint: .bottomTrailing))
                } else {
                    RoundedRectangle(cornerRadius: 14)
                        .fill(Theme.card)
                    RoundedRectangle(cornerRadius: 14)
                        .strokeBorder(Theme.cardBorder, style: StrokeStyle(lineWidth: 1, dash: [4]))
                }
                badgeIcon(badge.icon)
                    .font(Theme.body(20))
                    .foregroundStyle(badge.earned ? Theme.bg : Theme.faint)
            }
            .aspectRatio(1, contentMode: .fit)
            Text(badge.name)
                .font(Theme.body(10))
                .foregroundStyle(Theme.dim)
                .multilineTextAlignment(.center)
                .lineLimit(2)
            if !badge.earned {
                Text("\(badge.percent)%")
                    .font(Theme.body(9, .semibold))
                    .foregroundStyle(Theme.faint)
            }
        }
        .accessibilityElement(children: .ignore)
        .accessibilityLabel("\(badge.name), \(badge.earned ? "earned" : "\(badge.percent) percent")")
        .accessibilityHint(badge.description)
    }

    /// The server sends an icon name; show it as an SF Symbol or emoji when it is one.
    @ViewBuilder
    private func badgeIcon(_ icon: String) -> some View {
        if UIImage(systemName: icon) != nil {
            Image(systemName: icon)
        } else if icon.unicodeScalars.contains(where: { $0.properties.isEmojiPresentation }) {
            Text(icon)
        } else {
            Image(systemName: "rosette")
        }
    }

    private var settings: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text("SETTINGS")
                .font(Theme.body(12))
                .kerning(0.4)
                .foregroundStyle(Theme.dim)
            VStack(spacing: 0) {
                HStack {
                    Image(systemName: "scalemass")
                        .frame(width: 22)
                    Text("Weight unit")
                    Spacer()
                    Picker("Weight unit", selection: Binding(
                        get: { model.weightUnit },
                        set: { unit in Task { await model.setWeightUnit(unit) } }
                    )) {
                        ForEach(WeightUnit.allCases) { unit in
                            Text(unit.rawValue).tag(unit)
                        }
                    }
                    .pickerStyle(.segmented)
                    .frame(width: 110)
                    .accessibilityIdentifier("weightUnitPicker")
                }
                .font(Theme.body(15))
                .foregroundStyle(Theme.text)
                .padding(.horizontal, 16)
                .padding(.vertical, 10)
                divider
                Link(destination: AppConfig.privacyPolicyURL) { settingsLabel("Privacy Policy", icon: "hand.raised") }
                divider
                Link(destination: AppConfig.supportURL) { settingsLabel("Support", icon: "questionmark.circle") }
                divider
                Button { model.signOut() } label: { settingsLabel("Sign Out", icon: "rectangle.portrait.and.arrow.right") }
                    .accessibilityIdentifier("signOutButton")
                divider
                Button { confirmingSignOutEverywhere = true } label: { settingsLabel("Sign Out of All Devices", icon: "iphone.slash") }
                divider
                Button { showingDelete = true } label: { settingsLabel("Delete Account", icon: "trash", destructive: true) }
                    .accessibilityIdentifier("deleteAccountButton")
            }
            .cardStyle(cornerRadius: 16)
        }
        .padding(.top, 26)
    }

    private var divider: some View {
        Rectangle()
            .fill(Theme.cardBorder)
            .frame(height: 1)
            .padding(.leading, 50)
    }

    private func settingsLabel(_ title: String, icon: String, destructive: Bool = false) -> some View {
        HStack {
            Image(systemName: icon)
                .frame(width: 22)
            Text(title)
            Spacer()
            Image(systemName: "chevron.right")
                .font(Theme.body(12, .semibold))
                .foregroundStyle(Theme.faint)
        }
        .font(Theme.body(15))
        .foregroundStyle(destructive ? Theme.fire : Theme.text)
        .padding(.horizontal, 16)
        .padding(.vertical, 14)
        .contentShape(Rectangle())
    }
}

struct DeleteAccountSheet: View {
    @Environment(AppModel.self) private var model
    @Environment(\.dismiss) private var dismiss
    @State private var password = ""

    var body: some View {
        NavigationStack {
            VStack(alignment: .leading, spacing: 16) {
                Text("This permanently deletes your account and everything you've logged: workouts, records, points, quests and rewards. A party you own passes to its longest-standing member. This can't be undone.")
                    .font(Theme.body(14))
                    .foregroundStyle(Theme.dim)
                SecureField("", text: $password, prompt: Text("Confirm your password").foregroundStyle(Theme.faint))
                    .textContentType(.password)
                    .modifier(FieldStyle())
                    .accessibilityIdentifier("deletePasswordField")
                ErrorText(message: model.errorMessage)
                Button(role: .destructive) {
                    Task {
                        if await model.deleteAccount(password: password) { dismiss() }
                    }
                } label: {
                    Text("Delete My Account")
                        .font(Theme.display(16))
                        .foregroundStyle(Theme.text)
                        .frame(maxWidth: .infinity)
                        .padding(15)
                        .background(Color.red.opacity(password.isEmpty ? 0.35 : 0.85), in: RoundedRectangle(cornerRadius: 14))
                }
                .disabled(password.isEmpty || model.isBusy)
                .accessibilityIdentifier("confirmDeleteButton")
                Spacer()
            }
            .padding(20)
            .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .top)
            .background(Theme.bg)
            .navigationTitle("Delete Account")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Cancel") { dismiss() }
                }
            }
        }
        .presentationDetents([.medium, .large])
        .preferredColorScheme(.dark)
        .onAppear { model.errorMessage = "" }
    }
}

#Preview {
    ProfileView()
        .environment(AppModel(api: MockAPIClient()))
        .preferredColorScheme(.dark)
}
