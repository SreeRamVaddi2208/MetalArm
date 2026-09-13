//
//  HomeView.swift
//  MetalARM
//

import SwiftUI

struct HomeView: View {
    @Environment(AppModel.self) private var model
    var onOpenWorkout: () -> Void = {}

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 16) {
                header
                if let me = model.me {
                    levelCard(me.progress)
                }
                todayCard
                if let points = model.points {
                    weekCard(points)
                }
                ErrorText(message: model.errorMessage)
            }
            .padding(20)
        }
        .background(Theme.bg)
        .task { await model.loadHome() }
        .refreshable { await model.loadHome() }
    }

    private var header: some View {
        HStack(spacing: 12) {
            AvatarBadge(initials: initials(of: model.me?.displayName ?? ""), size: 40, cornerRadius: 12, fontSize: 15)
            VStack(alignment: .leading, spacing: 0) {
                Text("Welcome back")
                    .font(Theme.body(13))
                    .foregroundStyle(Theme.dim)
                Text(model.me?.displayName ?? " ")
                    .font(Theme.display(15, .semibold))
                    .foregroundStyle(Theme.text)
            }
            Spacer()
        }
    }

    private func levelCard(_ progress: ProgressInfo) -> some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                HStack(spacing: 12) {
                    Text("\(progress.currentLevel)")
                        .font(Theme.display(17))
                        .foregroundStyle(Theme.fire)
                        .frame(width: 44, height: 44)
                        .background(Theme.bg, in: RoundedRectangle(cornerRadius: 14))
                        .overlay(RoundedRectangle(cornerRadius: 14).stroke(Theme.fire, lineWidth: 2))
                    VStack(alignment: .leading, spacing: 2) {
                        Text("Level \(progress.currentLevel) · Rank \(progress.rank)")
                            .font(Theme.display(15))
                            .foregroundStyle(Theme.text)
                        Text("\(progress.xpIntoLevel) / \(progress.xpForNextLevel) XP")
                            .font(Theme.body(12))
                            .foregroundStyle(Theme.dim)
                    }
                }
                Spacer()
                HStack(spacing: 4) {
                    Image(systemName: "flame.fill")
                        .font(Theme.body(13))
                        .foregroundStyle(progress.streakIsActive ? Theme.fire : Theme.faint)
                    Text("\(progress.currentStreak)")
                        .font(Theme.display(13))
                        .foregroundStyle(Theme.text)
                }
                .padding(.horizontal, 10)
                .padding(.vertical, 6)
                .background(Theme.bg, in: RoundedRectangle(cornerRadius: 10))
                .overlay(RoundedRectangle(cornerRadius: 10).stroke(Theme.cardBorder))
                .accessibilityElement(children: .combine)
                .accessibilityLabel("\(progress.currentStreak) day streak")
            }
            XPBar(progress: progress.xpProgress)
            if let next = progress.nextRank, let level = progress.nextRankLevel {
                Text("Rank \(next) unlocks at level \(level)\(progress.nextRankStreak.map { " with a \($0)-day streak" } ?? "")")
                    .font(Theme.body(11))
                    .foregroundStyle(Theme.dim)
            }
        }
        .padding(.horizontal, 18)
        .padding(.vertical, 16)
        .background {
            ZStack {
                Theme.card
                LinearGradient(colors: [Theme.violet.opacity(0.16), Theme.fire.opacity(0.16)], startPoint: .topLeading, endPoint: .bottomTrailing)
            }
            .clipShape(RoundedRectangle(cornerRadius: 20))
        }
        .overlay(RoundedRectangle(cornerRadius: 20).stroke(Theme.cardBorder))
    }

    private var todayCard: some View {
        VStack(spacing: 4) {
            Text("TODAY")
                .font(Theme.body(12))
                .kerning(0.4)
                .foregroundStyle(Theme.dim)
            Text(model.sessionActive ? "Workout in progress" : "Ready to train?")
                .font(Theme.display(20))
                .foregroundStyle(Theme.text)
            Button {
                Task {
                    if !model.sessionActive {
                        await model.startWorkout()
                    }
                    if model.sessionActive {
                        onOpenWorkout()
                    }
                }
            } label: {
                Label(model.sessionActive ? "Resume Workout" : "Start Workout", systemImage: model.sessionActive ? "play.fill" : "plus")
            }
            .buttonStyle(PrimaryButtonStyle())
            .accessibilityIdentifier("homeStartWorkoutButton")
            .padding(.top, 10)
        }
        .frame(maxWidth: .infinity)
        .padding(18)
        .cardStyle()
    }

    private func weekCard(_ points: PointsSummary) -> some View {
        VStack(alignment: .leading, spacing: 10) {
            Text("THIS WEEK")
                .font(Theme.body(12))
                .kerning(0.4)
                .foregroundStyle(Theme.dim)
            HStack(spacing: 12) {
                StatTile(value: "\(points.thisWeekPoints)", label: "Points")
                StatTile(value: "\(points.streak.thisWeekSessions)/\(points.streak.target)", label: "Workouts")
                StatTile(value: "\(points.streak.weeks)", label: "Week streak")
            }
            Text(points.streak.thisWeekDone
                 ? "Weekly goal met - your streak is safe."
                 : "\(points.streak.sessionsToGo) more workout\(points.streak.sessionsToGo == 1 ? "" : "s") this week keeps your streak.")
                .font(Theme.body(12))
                .foregroundStyle(points.streak.thisWeekDone ? Theme.green : Theme.dim)
        }
    }
}

#Preview {
    HomeView()
        .environment(AppModel(api: MockAPIClient()))
        .preferredColorScheme(.dark)
}
