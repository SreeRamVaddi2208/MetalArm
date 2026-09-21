//
//  ProfileView.swift
//  MetalARM
//
//  Character sheet plus account settings: weight unit, privacy, sign out,
//  and account deletion (required by the App Store for apps with sign-up).
//

import SwiftUI
import UIKit
import UniformTypeIdentifiers

struct ProfileView: View {
    @Environment(AppModel.self) private var model
    @State private var showingDelete = false
    @State private var confirmingSignOutEverywhere = false
    @State private var showingImporter = false

    private let badgeColumns = Array(repeating: GridItem(.flexible(), spacing: 12), count: 4)

    var body: some View {
        ScrollView {
            VStack(spacing: 0) {
                if let profile = model.profile {
                    header(profile)
                    stats(profile.stats)
                    if let sheet = model.characterSheet {
                        character(sheet)
                    }
                    if !model.rankTrials.isEmpty {
                        trials(model.rankTrials)
                    }
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
        .fileImporter(isPresented: $showingImporter, allowedContentTypes: [.commaSeparatedText, .plainText]) { result in
            guard case .success(let url) = result else { return }
            let scoped = url.startAccessingSecurityScopedResource()
            defer { if scoped { url.stopAccessingSecurityScopedResource() } }
            guard let csv = try? String(contentsOf: url, encoding: .utf8) else {
                model.errorMessage = "Couldn't read that file"
                return
            }
            Task { await model.importWorkouts(csv: csv) }
        }
        .alert("Import finished", isPresented: Binding(
            get: { !model.importSummary.isEmpty },
            set: { if !$0 { model.importSummary = "" } }
        )) {
            Button("OK", role: .cancel) {}
        } message: {
            Text(model.importSummary)
        }
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
            Text("Level \(profile.progress.currentLevel) · \(RankTitle.of(profile.progress.rank))")
                .font(Theme.body(12.5, .bold))
                .foregroundStyle(Theme.accent)
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

    /// Three stats from real training, plus the cosmetic class that highlights them.
    private func character(_ sheet: CharacterSheet) -> some View {
        VStack(alignment: .leading, spacing: 14) {
            HStack {
                Text("Character")
                    .font(Theme.display(16))
                    .foregroundStyle(Theme.text)
                Spacer()
                if !sheet.classLabel.isEmpty {
                    Text(sheet.classLabel)
                        .font(Theme.body(12, .bold))
                        .foregroundStyle(Theme.accent)
                }
            }
            ForEach(sheet.stats) { stat in
                VStack(alignment: .leading, spacing: 6) {
                    HStack {
                        Text(stat.label)
                            .font(Theme.body(12.5, .semibold))
                            .foregroundStyle(stat.highlighted ? Theme.accent : Theme.text)
                        Spacer()
                        Text("\(stat.value)")
                            .font(Theme.display(13))
                            .foregroundStyle(Theme.text)
                    }
                    XPBar(progress: stat.fraction, track: Theme.bg)
                    Text(stat.detail)
                        .font(Theme.body(10.5))
                        .foregroundStyle(Theme.dim)
                }
                .accessibilityElement(children: .combine)
            }
            Text("A class highlights the stats you care about. It never changes a score.")
                .font(Theme.body(10.5))
                .foregroundStyle(Theme.dim)
            HStack(spacing: 8) {
                ForEach(["powerlifter", "bodybuilder", "athlete"], id: \.self) { value in
                    Button {
                        Task { await model.chooseClass(value) }
                    } label: {
                        Text(value.capitalized)
                            .font(Theme.body(11, .bold))
                            .foregroundStyle(sheet.characterClass == value ? Theme.bg : Theme.text)
                            .padding(.horizontal, 10)
                            .padding(.vertical, 7)
                            .background(sheet.characterClass == value ? Theme.accent : Theme.bg, in: RoundedRectangle(cornerRadius: 9))
                            .overlay(RoundedRectangle(cornerRadius: 9).stroke(Theme.cardBorder))
                    }
                    .accessibilityIdentifier("class-\(value)")
                }
            }
        }
        .padding(16)
        .frame(maxWidth: .infinity, alignment: .leading)
        .cardStyle(cornerRadius: 16)
        .padding(.top, 22)
        .accessibilityElement(children: .contain)
        .accessibilityIdentifier("characterCard")
    }

    /// The strength trials that gate ranks B, A and S, with progress to each.
    private func trials(_ trials: [RankTrial]) -> some View {
        VStack(alignment: .leading, spacing: 14) {
            Text("Rank trials")
                .font(Theme.display(16))
                .foregroundStyle(Theme.text)
            Text("\(RankTitle.list(["B", "A", "S"])) also need a lift at a multiple of your bodyweight.")
                .font(Theme.body(11))
                .foregroundStyle(Theme.dim)
            ForEach(trials) { trial in
                trialRow(trial)
            }
        }
        .padding(16)
        .frame(maxWidth: .infinity, alignment: .leading)
        .cardStyle(cornerRadius: 16)
        .padding(.top, 22)
        .accessibilityElement(children: .contain)
        .accessibilityIdentifier("rankTrialsCard")
    }

    private func trialRow(_ trial: RankTrial) -> some View {
        VStack(alignment: .leading, spacing: 7) {
            HStack(spacing: 10) {
                Text(trial.rank)
                    .font(Theme.display(14))
                    .foregroundStyle(trial.passed ? Theme.bg : Theme.text)
                    .frame(width: 28, height: 28)
                    .background(trial.passed ? Theme.accent : Theme.bg, in: RoundedRectangle(cornerRadius: 8))
                    .overlay(RoundedRectangle(cornerRadius: 8).stroke(Theme.cardBorder))
                Text(trial.description)
                    .font(Theme.body(12.5, .semibold))
                    .foregroundStyle(Theme.text)
                Spacer(minLength: 0)
                if trial.passed {
                    Image(systemName: "checkmark.seal.fill")
                        .foregroundStyle(Theme.success)
                }
            }
            XPBar(progress: trial.fraction, track: Theme.bg)
            Text(trialProgress(trial))
                .font(Theme.body(10.5))
                .foregroundStyle(Theme.dim)
        }
        .accessibilityElement(children: .combine)
    }

    private func trialProgress(_ trial: RankTrial) -> String {
        guard let target = trial.targetKg else { return "Log your bodyweight to set a target" }
        let unit = model.weightUnit
        let best = trial.bestKg.map { unit.format(kilograms: $0) }
        if trial.passed { return "Passed · best \(best ?? "")" }
        return "Best \(best ?? "none yet") of \(unit.format(kilograms: target))"
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
                    .foregroundStyle(Theme.accent)
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
                        .fill(LinearGradient(colors: [Theme.silver, Theme.silverDeep], startPoint: .topLeading, endPoint: .bottomTrailing))
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
                Toggle(isOn: Binding(
                    get: { model.healthSettings.enabled },
                    set: { on in Task { await model.setHealthSync(on) } }
                )) {
                    settingsLabel("Save to Apple Health", icon: "heart", chevron: false)
                }
                .padding(.trailing, 16)
                .accessibilityIdentifier("healthSyncToggle")
                if !model.healthStatus.isEmpty {
                    Text(model.healthStatus)
                        .font(Theme.body(10.5))
                        .foregroundStyle(Theme.dim)
                        .padding(.horizontal, 16)
                        .padding(.bottom, 8)
                        .accessibilityIdentifier("healthStatusText")
                }
                divider
                Toggle(isOn: Binding(
                    get: { model.notificationSettings.restAlerts },
                    set: { on in Task { await model.setRestAlerts(on) } }
                )) {
                    settingsLabel("Rest timer alerts", icon: "bell", chevron: false)
                }
                .padding(.trailing, 16)
                .accessibilityIdentifier("restAlertsToggle")
                divider
                Toggle(isOn: Binding(
                    get: { model.notificationSettings.streakReminders },
                    set: { on in Task { await model.setStreakReminders(on) } }
                )) {
                    settingsLabel("Streak reminders", icon: "flame", chevron: false)
                }
                .padding(.trailing, 16)
                .accessibilityIdentifier("streakRemindersToggle")
                divider
                Button { showingImporter = true } label: { settingsLabel("Import from Strong or Hevy", icon: "square.and.arrow.down") }
                    .accessibilityIdentifier("importWorkoutsButton")
                divider
                Link(destination: AppConfig.privacyPolicyURL) { settingsLabel("Privacy Policy", icon: "hand.raised") }
                divider
                Link(destination: AppConfig.supportURL) { settingsLabel("Support", icon: "questionmark.circle") }
                divider
                Button { Task { await model.signOut() } } label: { settingsLabel("Sign Out", icon: "rectangle.portrait.and.arrow.right") }
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

    /// `chevron: false` for a Toggle's label: a chevron says "opens something",
    /// and beside a switch it only made the row look like a link.
    private func settingsLabel(_ title: String, icon: String, destructive: Bool = false, chevron: Bool = true) -> some View {
        HStack {
            Image(systemName: icon)
                .frame(width: 22)
            Text(title)
            Spacer()
            if chevron {
                Image(systemName: "chevron.right")
                    .font(Theme.body(12, .semibold))
                    .foregroundStyle(Theme.faint)
            }
        }
        .font(Theme.body(15))
        .foregroundStyle(destructive ? Theme.danger : Theme.text)
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
                        .background(Theme.danger.opacity(password.isEmpty ? 0.35 : 0.85), in: RoundedRectangle(cornerRadius: 14))
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
