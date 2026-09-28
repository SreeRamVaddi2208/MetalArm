//
//  DuelsView.swift
//  MetalARM
//
//  Head to head over a window you choose, and what your party has been doing.
//  Opened from Ranks, which is already long enough without another three
//  sections on it.
//
//  Reading the duels is what JUDGES any whose window has closed (see
//  app/core/duels.py), so the response can carry a win that has just been
//  decided - which is why the celebration is raised by a load and never by the
//  app deciding on its own that something has been won.
//

import SwiftUI

struct DuelsView: View {
    @Environment(AppModel.self) private var model
    @Environment(\.dismiss) private var dismiss

    @State private var metric = "volume"
    @State private var days = 7

    private var me: String { model.me?.id ?? "" }

    var body: some View {
        NavigationStack {
            ZStack {
                ScrollView {
                    VStack(alignment: .leading, spacing: 16) {
                        challengePanel
                        section("WAITING", model.duels.pending) { duel in
                            pendingCard(duel)
                        }
                        section("RUNNING", model.duels.active) { duel in
                            duelCard(duel)
                        }
                        section("SETTLED", model.duels.completed) { duel in
                            duelCard(duel)
                        }
                        feedSection
                        ErrorText(message: model.errorMessage)
                    }
                    .padding(20)
                }
                .background(Theme.bg)

                if let won = model.justWon {
                    winOverlay(won)
                }
            }
            .navigationTitle("Duels")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Done") { dismiss() }
                        .accessibilityIdentifier("closeDuelsButton")
                }
            }
        }
        .preferredColorScheme(.dark)
        .task { await model.loadDuels() }
    }

    // MARK: - Starting one

    private var challengePanel: some View {
        VStack(alignment: .leading, spacing: 12) {
            Picker("What you are measured on", selection: $metric) {
                Text("Volume").tag("volume")
                Text("Sets").tag("sets")
                Text("Sessions").tag("sessions")
            }
            .pickerStyle(.segmented)
            .accessibilityIdentifier("duelMetricPicker")

            Stepper("Over \(days) day\(days == 1 ? "" : "s")", value: $days, in: 1...28)
                .font(Theme.body(13))
                .foregroundStyle(Theme.dim)
                .accessibilityIdentifier("duelDaysStepper")

            Button {
                Task { await model.challenge(opponentID: nil, metric: metric, days: days) }
            } label: {
                Text("Challenge your rival")
            }
            .buttonStyle(PrimaryButtonStyle())
            .disabled(model.isBusy)
            .accessibilityIdentifier("challengeRivalButton")

            // Saying where the rival comes from is the difference between a
            // training tool and a fake friend.
            Text("Your rival's pace comes from your own recent weeks, not another lifter.")
                .font(Theme.body(11))
                .foregroundStyle(Theme.faint)

            let members = (model.partyBoard?.entries ?? []).filter { $0.userId != me }
            if !members.isEmpty {
                Text("OR CHALLENGE YOUR PARTY")
                    .font(Theme.body(10, .semibold))
                    .kerning(0.6)
                    .foregroundStyle(Theme.dim)
                    .padding(.top, 4)
                ForEach(members) { member in
                    HStack {
                        Text(member.displayName)
                            .font(Theme.body(14))
                            .foregroundStyle(Theme.text)
                        Spacer()
                        Button("Challenge") {
                            Task { await model.challenge(opponentID: member.userId, metric: metric, days: days) }
                        }
                        .font(Theme.body(12, .semibold))
                        .foregroundStyle(Theme.accent)
                        .accessibilityIdentifier("challenge-\(member.displayName)")
                    }
                    .padding(.vertical, 2)
                }
            }
        }
        .padding(14)
        .frame(maxWidth: .infinity, alignment: .leading)
        .cardStyle(cornerRadius: 16)
    }

    // MARK: - Cards

    @ViewBuilder
    private func section<T: Identifiable>(
        _ title: String, _ items: [T], @ViewBuilder row: @escaping (T) -> some View
    ) -> some View {
        if !items.isEmpty {
            Text(title)
                .font(Theme.body(10, .semibold))
                .kerning(0.6)
                .foregroundStyle(Theme.dim)
                .padding(.top, 4)
            ForEach(items) { row($0) }
        }
    }

    private func duelCard(_ duel: Duel) -> some View {
        let mine = duel.mine(me)
        let theirs = duel.theirs(me)
        let ahead = mine.score > theirs.score
        return VStack(alignment: .leading, spacing: 10) {
            HStack {
                Text(duel.metric.uppercased())
                    .font(Theme.body(10, .semibold))
                    .kerning(0.6)
                    .foregroundStyle(Theme.accent)
                Spacer()
                Text(duel.endsLabel)
                    .font(Theme.body(11))
                    .foregroundStyle(Theme.dim)
            }
            HStack(alignment: .top, spacing: 14) {
                score("YOU", duel.label(for: mine.score), highlighted: ahead)
                Text("vs")
                    .font(Theme.body(11))
                    .foregroundStyle(Theme.faint)
                    .padding(.top, 14)
                score(theirs.rival ? "YOUR RIVAL" : theirs.displayName.uppercased(),
                      duel.label(for: theirs.score), highlighted: !ahead)
                Spacer(minLength: 0)
            }
            if duel.status == "completed" {
                Text(duel.drawn ? "Drawn."
                     : duel.iWon(me) ? "You won." : "\(theirs.displayName) won.")
                    .font(Theme.body(12, .semibold))
                    .foregroundStyle(duel.iWon(me) ? Theme.accent : Theme.dim)
            }
        }
        .padding(14)
        .frame(maxWidth: .infinity, alignment: .leading)
        .cardStyle(cornerRadius: 16)
        .accessibilityElement(children: .combine)
        .accessibilityIdentifier("duel-\(duel.id)")
    }

    private func score(_ label: String, _ value: String, highlighted: Bool) -> some View {
        VStack(alignment: .leading, spacing: 3) {
            Text(label)
                .font(Theme.body(10))
                .kerning(0.5)
                .foregroundStyle(Theme.dim)
            Text(value)
                .font(Theme.display(20))
                .foregroundStyle(highlighted ? Theme.accent : Theme.text)
        }
    }

    private func pendingCard(_ duel: Duel) -> some View {
        // Which side you are on changes what this card says entirely, and
        // "a challenger exists" is not the test for it.
        let incoming = !duel.iChallenged(me)
        let them = duel.theirs(me)
        return VStack(alignment: .leading, spacing: 10) {
            Text(incoming ? "\(them.displayName) challenged you" : "Waiting for \(them.displayName)")
                .font(Theme.body(14, .semibold))
                .foregroundStyle(Theme.text)
            Text("\(duel.metric.uppercased()) · starts when accepted")
                .font(Theme.body(11))
                .foregroundStyle(Theme.dim)
            HStack(spacing: 10) {
                if incoming {
                    Button("Accept") { Task { await model.acceptDuel(duel.id) } }
                        .buttonStyle(PrimaryButtonStyle())
                        .accessibilityIdentifier("acceptDuelButton")
                }
                Button(incoming ? "Decline" : "Withdraw") {
                    Task { await model.declineDuel(duel.id) }
                }
                .font(Theme.body(12, .semibold))
                .foregroundStyle(Theme.dim)
                .accessibilityIdentifier("declineDuelButton")
            }
        }
        .padding(14)
        .frame(maxWidth: .infinity, alignment: .leading)
        .cardStyle(cornerRadius: 16)
    }

    // MARK: - The feed

    @ViewBuilder
    private var feedSection: some View {
        Text("ACTIVITY")
            .font(Theme.body(10, .semibold))
            .kerning(0.6)
            .foregroundStyle(Theme.dim)
            .padding(.top, 8)
        if model.feed.isEmpty {
            Text("Nothing yet. Finish a workout, hit a record, or win a duel.")
                .font(Theme.body(12))
                .foregroundStyle(Theme.faint)
        } else {
            VStack(spacing: 0) {
                ForEach(Array(model.feed.enumerated()), id: \.element.id) { index, entry in
                    HStack(alignment: .top, spacing: 10) {
                        Image(systemName: entry.symbol)
                            .font(Theme.body(12))
                            .foregroundStyle(Theme.accent)
                            .frame(width: 18)
                        VStack(alignment: .leading, spacing: 2) {
                            Text(entry.headline)
                                .font(Theme.body(13, .semibold))
                                .foregroundStyle(Theme.text)
                            Text("\(entry.displayName) · \(entry.whenLabel)")
                                .font(Theme.body(11))
                                .foregroundStyle(Theme.dim)
                        }
                        Spacer(minLength: 0)
                    }
                    .padding(.vertical, 9)
                    if index < model.feed.count - 1 {
                        Rectangle().fill(Theme.cardBorder).frame(height: 1)
                    }
                }
            }
            .padding(.horizontal, 14)
            .frame(maxWidth: .infinity)
            .cardStyle(cornerRadius: 16)
            .accessibilityElement(children: .contain)
            .accessibilityIdentifier("activityFeed")
        }
    }

    // MARK: - The win

    /// A smaller sibling of the rank-up: a duel is worth a flourish, a
    /// promotion is the event.
    private func winOverlay(_ duel: Duel) -> some View {
        ZStack {
            Color.black.opacity(0.84).ignoresSafeArea()
            VStack(spacing: 12) {
                Text("DUEL WON")
                    .font(Theme.display(26))
                    .kerning(2)
                    .foregroundStyle(Theme.text)
                Text("You beat \(duel.theirs(me).displayName).")
                    .font(Theme.body(13))
                    .foregroundStyle(Theme.dim)
                Text("+\(duel.pointsAwarded ?? 0) points")
                    .font(Theme.display(18))
                    .foregroundStyle(Theme.accent)
                Button("Continue") { model.dismissDuelWin() }
                    .buttonStyle(PrimaryButtonStyle())
                    .accessibilityIdentifier("duelWinContinueButton")
            }
            .padding(24)
            .frame(maxWidth: 320)
            .cardStyle(cornerRadius: 20)
        }
        // A bare ZStack is not exposed to XCUITest at all; `.contain` makes it
        // an element that still lets its texts be found individually.
        .accessibilityElement(children: .contain)
        .accessibilityIdentifier("duelWinOverlay")
        .transition(.opacity)
    }
}
