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
    @State private var showingPath = false

    private let badgeColumns = Array(repeating: GridItem(.flexible(), spacing: Theme.Space.s12), count: 4)

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: Theme.Space.s32) {
                ScreenTitle("Profile")
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
            }
            .screen()
        }
        .background(Theme.bg)
        .task { await model.loadProfile() }
        .refreshable { await model.loadProfile() }
        .sheet(isPresented: $showingDelete) { DeleteAccountSheet() }
        .sheet(isPresented: $showingPath) {
            NavigationStack {
                TrainingPathView(isOnboarding: false) { showingPath = false }
                    .navigationTitle("Training path")
                    .navigationBarTitleDisplayMode(.inline)
                    .toolbar {
                        ToolbarItem(placement: .cancellationAction) {
                            Button("Cancel") { showingPath = false }
                        }
                    }
            }
            .preferredColorScheme(.dark)
        }
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
            Button("Sign out everywhere", role: .destructive) {
                Task { await model.signOutEverywhere() }
            }
        } message: {
            Text("You'll need to sign in again on this and every other device.")
        }
    }

    private func header(_ profile: Profile) -> some View {
        VStack(alignment: .leading, spacing: Theme.Space.s16) {
            HStack {
                Avatar(initials: initials(of: profile.user.displayName), size: 96)
                Spacer()
                RankBadge(rank: profile.progress.rank, size: 96)
            }
            VStack(alignment: .leading, spacing: 0) {
                Text(profile.user.displayName).font(Theme.titleLG).foregroundStyle(Theme.text)
                Text("\(RankTitle.of(profile.progress.rank)) · Level \(profile.progress.currentLevel)")
                    .font(Theme.body).foregroundStyle(Theme.text2)
            }
            ProgressBar(progress: profile.progress.xpProgress,
                        label: "\(profile.progress.xpIntoLevel) / \(profile.progress.xpForNextLevel) XP to the next level")
        }
    }

    private func stats(_ stats: LifetimeStats) -> some View {
        HStack(spacing: Theme.Space.s16) {
            StatTile(value: "\(stats.workoutsCompleted)", label: "Workouts")
            StatTile(value: "\(stats.workoutPrs)", label: "Records")
            StatTile(value: "\(stats.longestWorkoutStreak)", label: "Best streak", unit: "wk")
        }
    }

    /// Three stats from real training, plus the path that highlights them.
    private func character(_ sheet: CharacterSheet) -> some View {
        SectionBlock(title: "Character") {
            VStack(spacing: Theme.Space.s16) {
                ForEach(sheet.stats) { stat in
                    VStack(alignment: .leading, spacing: Theme.Space.s8) {
                        HStack {
                            Text(stat.label).font(Theme.body).foregroundStyle(stat.highlighted ? Theme.text : Theme.text2)
                            Spacer()
                            Text("\(stat.value)").font(Theme.body).foregroundStyle(Theme.text)
                        }
                        ProgressBar(progress: stat.fraction, label: stat.detail)
                    }
                    .accessibilityElement(children: .combine)
                }
            }
            // One way to choose a path, here and at onboarding: the same cards.
            Button { showingPath = true } label: {
                ListRow(title: "Training path", subtitle: sheet.classLabel.isEmpty ? "Not chosen yet" : sheet.classLabel,
                        chevron: true) {
                    Image(systemName: "point.topleft.down.to.point.bottomright.curvepath").foregroundStyle(Theme.text2)
                }
            }
            .buttonStyle(.plain)
            .accessibilityIdentifier("trainingPathButton")
            Text("Your path highlights the stats you care about and decides what MetalArm suggests. It never changes a score.")
                .font(Theme.caption).foregroundStyle(Theme.text2)
        }
        .accessibilityElement(children: .contain)
        .accessibilityIdentifier("characterCard")
    }

    /// The strength trials that gate ranks B, A and S, with progress to each.
    private func trials(_ trials: [RankTrial]) -> some View {
        SectionBlock(title: "Rank trials") {
            Text("\(RankTitle.list(["B", "A", "S"])) also need a lift at a multiple of your bodyweight.")
                .font(Theme.caption).foregroundStyle(Theme.text2)
            VStack(spacing: Theme.Space.s16) {
                ForEach(trials) { trial in
                    VStack(alignment: .leading, spacing: Theme.Space.s8) {
                        HStack(spacing: Theme.Space.s12) {
                            RankBadge(rank: trial.rank, size: 24)
                            Text(trial.description).font(Theme.body).foregroundStyle(Theme.text)
                            Spacer(minLength: 0)
                            if trial.passed { Image(systemName: "checkmark").foregroundStyle(Theme.accent) }
                        }
                        ProgressBar(progress: trial.fraction, label: trialProgress(trial))
                    }
                    .accessibilityElement(children: .combine)
                }
            }
        }
        .accessibilityElement(children: .contain)
        .accessibilityIdentifier("rankTrialsCard")
    }

    private func trialProgress(_ trial: RankTrial) -> String {
        guard let target = trial.targetKg else { return "Log your bodyweight to set a target" }
        let unit = model.weightUnit
        let best = trial.bestKg.map { unit.format(kilograms: $0) }
        if trial.passed { return "Passed · best \(best ?? "")" }
        return "Best \(best ?? "none yet") of \(unit.format(kilograms: target))"
    }

    private func badges(_ profile: Profile) -> some View {
        VStack(alignment: .leading, spacing: Theme.Space.s12) {
            HStack {
                Text("Badges").font(Theme.title).foregroundStyle(Theme.text)
                Spacer()
                Text("\(profile.badgesEarned) of \(profile.badgesTotal)").font(Theme.caption).foregroundStyle(Theme.text2)
            }
            LazyVGrid(columns: badgeColumns, spacing: Theme.Space.s12) {
                ForEach(profile.badges) { badge in
                    badgeTile(badge)
                }
            }
        }
    }

    private func badgeTile(_ badge: Badge) -> some View {
        VStack(spacing: Theme.Space.s4) {
            badgeIcon(badge.icon)
                .font(.system(.title3))
                .foregroundStyle(badge.earned ? Theme.accent : Theme.text3)
                .frame(maxWidth: .infinity)
                .aspectRatio(1, contentMode: .fit)
                .background(badge.earned ? Theme.accentSoft : Theme.surface, in: RoundedRectangle(cornerRadius: Theme.radius))
            Text(badge.name).font(Theme.caption).foregroundStyle(Theme.text2)
                .multilineTextAlignment(.center).lineLimit(2)
            if !badge.earned {
                Text("\(badge.percent)%").font(Theme.caption).foregroundStyle(Theme.text3)
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
        VStack(alignment: .leading, spacing: Theme.Space.s32) {
            SectionBlock(title: "Training") {
                RowGroup {
                    HStack {
                        settingsLabel("Weight unit", icon: "scalemass", chevron: false)
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
                    Button { showingImporter = true } label: {
                        settingsLabel("Import from Strong or Hevy", icon: "square.and.arrow.down")
                    }
                    .buttonStyle(.plain)
                    .accessibilityIdentifier("importWorkoutsButton")
                }
            }
            SectionBlock(title: "App") {
                RowGroup {
                    VStack(alignment: .leading, spacing: 0) {
                        toggle("Save to Apple Health", icon: "heart", isOn: model.healthSettings.enabled) { on in
                            Task { await model.setHealthSync(on) }
                        }
                        .accessibilityIdentifier("healthSyncToggle")
                        if !model.healthStatus.isEmpty {
                            Text(model.healthStatus).font(Theme.caption).foregroundStyle(Theme.text2)
                                .padding(.bottom, Theme.Space.s8)
                                .accessibilityIdentifier("healthStatusText")
                        }
                    }
                    toggle("Rest timer alerts", icon: "bell", isOn: model.notificationSettings.restAlerts) { on in
                        Task { await model.setRestAlerts(on) }
                    }
                    .accessibilityIdentifier("restAlertsToggle")
                    toggle("Streak reminders", icon: "flame", isOn: model.notificationSettings.streakReminders) { on in
                        Task { await model.setStreakReminders(on) }
                    }
                    .accessibilityIdentifier("streakRemindersToggle")
                }
            }
            SectionBlock(title: "Account") {
                RowGroup {
                    Link(destination: AppConfig.privacyPolicyURL) { settingsLabel("Privacy policy", icon: "hand.raised") }
                    Link(destination: AppConfig.supportURL) { settingsLabel("Support", icon: "questionmark.circle") }
                    Button { Task { await model.signOut() } } label: {
                        settingsLabel("Sign out", icon: "rectangle.portrait.and.arrow.right")
                    }
                    .buttonStyle(.plain)
                    .accessibilityIdentifier("signOutButton")
                    Button { confirmingSignOutEverywhere = true } label: {
                        settingsLabel("Sign out of all devices", icon: "iphone.slash")
                    }
                    .buttonStyle(.plain)
                    Button { showingDelete = true } label: {
                        settingsLabel("Delete account", icon: "trash", destructive: true)
                    }
                    .buttonStyle(.plain)
                    .accessibilityIdentifier("deleteAccountButton")
                }
            }
        }
    }

    private func toggle(_ title: String, icon: String, isOn: Bool, set: @escaping (Bool) -> Void) -> some View {
        Toggle(isOn: Binding(get: { isOn }, set: set)) {
            settingsLabel(title, icon: icon, chevron: false)
        }
        .tint(Theme.accent)
    }

    /// `chevron: false` for a Toggle's label: a chevron says "opens something",
    /// and beside a switch it only made the row look like a link.
    private func settingsLabel(_ title: String, icon: String, destructive: Bool = false, chevron: Bool = true) -> some View {
        HStack(spacing: Theme.Space.s12) {
            Image(systemName: icon).foregroundStyle(destructive ? Theme.danger : Theme.text2).frame(width: Theme.Space.s24)
            Text(title).font(Theme.body).foregroundStyle(destructive ? Theme.danger : Theme.text)
            Spacer()
            if chevron {
                Image(systemName: "chevron.right").font(.system(.footnote, weight: .semibold)).foregroundStyle(Theme.text3)
            }
        }
        .frame(minHeight: Theme.rowMin)
        .contentShape(Rectangle())
    }
}

struct DeleteAccountSheet: View {
    @Environment(AppModel.self) private var model
    @Environment(\.dismiss) private var dismiss
    @State private var password = ""

    var body: some View {
        NavigationStack {
            VStack(alignment: .leading, spacing: Theme.Space.s16) {
                Text("This permanently deletes your account and everything you've logged: workouts, records, points, quests and rewards. A party you own passes to its longest-standing member. This can't be undone.")
                    .font(Theme.body)
                    .foregroundStyle(Theme.text2)
                SecureField("", text: $password, prompt: Text("Confirm your password").foregroundStyle(Theme.text3))
                    .textContentType(.password)
                    .modifier(FieldStyle())
                    .accessibilityIdentifier("deletePasswordField")
                ErrorText(message: model.errorMessage)
                Button(role: .destructive) {
                    Task {
                        if await model.deleteAccount(password: password) { dismiss() }
                    }
                } label: {
                    Text("Delete my account")
                }
                .buttonStyle(.danger)
                .disabled(password.isEmpty || model.isBusy)
                .accessibilityIdentifier("confirmDeleteButton")
                Spacer()
            }
            .screen()
            .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .top)
            .background(Theme.bg)
            .navigationTitle("Delete account")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Cancel") { dismiss() }
                }
            }
        }
        .presentationDetents([.medium, .large])
        .presentationBackground(Theme.bg)
        .preferredColorScheme(.dark)
        .onAppear { model.errorMessage = "" }
    }
}

#Preview {
    NavigationStack { ProfileView() }
        .environment(AppModel(api: MockAPIClient()))
        .preferredColorScheme(.dark)
}
