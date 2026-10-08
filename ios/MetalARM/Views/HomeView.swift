//
//  HomeView.swift
//  MetalARM
//
//  Home: who you are in the game, this week in three numbers, and how you
//  stand in your party - its top three and you, with the full leaderboard
//  one tap away. One primary: Start workout (or Resume, while one is live).
//

import SwiftUI

struct HomeView: View {
    @Environment(AppModel.self) private var model
    var onOpenWorkout: () -> Void = {}

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: Theme.Space.s24) {
                header
                if let points = model.points {
                    week(points)
                }
                leaderboard
                ErrorText(message: model.errorMessage)
            }
            .screen()
        }
        .background(Theme.bg)
        .task { await model.loadHome() }
        .task { await model.loadParties() }
        .refreshable { await model.loadHome() }
        .navigationDestination(for: HomeRoute.self) { _ in LeaderboardView() }
        .pinnedPrimary {
            Button {
                Task {
                    if !model.sessionActive { await model.startWorkout() }
                    if model.sessionActive { onOpenWorkout() }
                }
            } label: {
                Label(model.sessionActive ? "Resume workout" : "Start workout", systemImage: "play.fill")
            }
            .buttonStyle(.primary)
            .accessibilityIdentifier("homeStartWorkoutButton")
        }
    }

    private var header: some View {
        VStack(alignment: .leading, spacing: Theme.Space.s16) {
            HStack(spacing: Theme.Space.s12) {
                RankBadge(rank: model.me?.progress.rank ?? "E", size: 48)
                VStack(alignment: .leading, spacing: 0) {
                    Text("Hi, \(model.me?.displayName ?? "")").font(Theme.title).foregroundStyle(Theme.text)
                        .lineLimit(1)
                    if let progress = model.me?.progress {
                        Text("Level \(progress.currentLevel) · \(RankTitle.of(progress.rank))")
                            .font(Theme.caption).foregroundStyle(Theme.text2)
                    }
                }
                Spacer()
            }
            if let progress = model.me?.progress {
                ProgressBar(progress: progress.xpProgress,
                            label: "\(progress.xpIntoLevel) / \(progress.xpForNextLevel) XP to level \(progress.currentLevel + 1)")
                if let trial = progress.nextRankTrial {
                    Text("Trial: \(trial)").font(Theme.caption).foregroundStyle(Theme.text2)
                        .accessibilityIdentifier("nextTrialText")
                }
            }
        }
        .padding(.top, Theme.Space.s16)
    }

    private func week(_ points: PointsSummary) -> some View {
        VStack(alignment: .leading, spacing: Theme.Space.s8) {
            HStack(spacing: Theme.Space.s16) {
                StatTile(value: "\(points.streak.weeks)", label: "Week streak")
                StatTile(value: "\(points.streak.thisWeekSessions)/\(points.streak.target)", label: "Workouts this week")
                StatTile(value: "\(points.thisWeekPoints)", label: "Points this week")
            }
            Text(points.streak.thisWeekDone
                 ? "Weekly goal met - your streak is safe."
                 : "\(points.streak.sessionsToGo) more workout\(points.streak.sessionsToGo == 1 ? "" : "s") this week keeps your streak.")
                .font(Theme.caption).foregroundStyle(Theme.text2)
        }
    }

    private var leaderboard: some View {
        let entries = model.partyBoard?.entries ?? []
        let top = Array(entries.prefix(3))
        let me = entries.first { $0.isMe }
        return VStack(alignment: .leading, spacing: Theme.Space.s12) {
            HStack {
                Text("Leaderboard").font(Theme.title).foregroundStyle(Theme.text)
                Spacer()
                NavigationLink(value: HomeRoute.leaderboard) {
                    HStack(spacing: Theme.Space.s4) {
                        Text("See all").font(Theme.label)
                        Image(systemName: "chevron.right").font(.system(.caption, weight: .semibold))
                    }
                    .foregroundStyle(Theme.text2)
                    .frame(minHeight: Theme.touch)
                }
                .accessibilityIdentifier("homeLeaderboardLink")
            }
            if entries.isEmpty {
                Text("Join or create a party to see how you stack up.").font(Theme.body).foregroundStyle(Theme.text2)
            } else {
                VStack(spacing: Theme.Space.s4) {
                    ForEach(top) { row($0) }
                    if let me, !top.contains(where: \.isMe) { row(me) }
                }
            }
        }
    }

    private func row(_ entry: PartyBoardEntry) -> some View {
        BoardRow(position: entry.position, name: entry.displayName, value: "\(entry.points)",
                 isMe: entry.isMe, rank: entry.rank)
            .accessibilityIdentifier("homeBoardRow-\(entry.displayName)")
    }
}

enum HomeRoute: Hashable { case leaderboard }

#Preview {
    NavigationStack { HomeView() }
        .environment(AppModel(api: MockAPIClient()))
        .preferredColorScheme(.dark)
}
