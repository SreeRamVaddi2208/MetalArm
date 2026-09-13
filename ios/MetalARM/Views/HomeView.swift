//
//  HomeView.swift
//  MetalARM
//
//  Port of frontend/frontend/pages/home.py.
//

import SwiftUI

struct HomeView: View {
    @Environment(AppModel.self) private var model
    var onStartWorkout: () -> Void = {}

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 16) {
                header
                if let user = model.user {
                    xpCard(user)
                }
                todayCard
                friendActivity
                ErrorText(message: model.errorMessage)
            }
            .padding(.horizontal, 20)
            .padding(.vertical, 20)
        }
        .background(Theme.bg)
        .task { await model.loadHome() }
        .refreshable { await model.loadHome() }
    }

    private var header: some View {
        HStack(spacing: 12) {
            AvatarBadge(initials: initials(of: model.user?.name ?? ""), size: 40, cornerRadius: 12, fontSize: 15)
            VStack(alignment: .leading, spacing: 0) {
                Text("Welcome back")
                    .font(.system(size: 13))
                    .foregroundStyle(Theme.dim)
                Text(model.user?.name ?? " ")
                    .font(Theme.display(15, .semibold))
                    .foregroundStyle(Theme.text)
            }
            Spacer()
            Image(systemName: "bell")
                .font(.system(size: 16))
                .foregroundStyle(Theme.dim)
                .frame(width: 38, height: 38)
                .cardStyle(cornerRadius: 11)
        }
    }

    private func xpCard(_ user: User) -> some View {
        VStack(spacing: 12) {
            HStack {
                HStack(spacing: 12) {
                    Text("\(user.level)")
                        .font(Theme.display(17))
                        .foregroundStyle(Theme.fire)
                        .frame(width: 44, height: 44)
                        .background(Theme.bg, in: RoundedRectangle(cornerRadius: 14))
                        .overlay(RoundedRectangle(cornerRadius: 14).stroke(Theme.fire, lineWidth: 2))
                    VStack(alignment: .leading, spacing: 2) {
                        Text("Level \(user.level) — \(user.levelName)")
                            .font(Theme.display(15))
                            .foregroundStyle(Theme.text)
                        Text("\(user.xpCurrent) / \(user.xpToNextLevel) XP")
                            .font(.system(size: 12))
                            .foregroundStyle(Theme.dim)
                    }
                }
                Spacer()
                HStack(spacing: 4) {
                    Image(systemName: "flame.fill")
                        .font(.system(size: 13))
                        .foregroundStyle(Theme.fire)
                    Text("\(user.streakDays ?? 0)")
                        .font(Theme.display(13))
                        .foregroundStyle(Theme.text)
                }
                .padding(.horizontal, 10)
                .padding(.vertical, 6)
                .background(Theme.bg, in: RoundedRectangle(cornerRadius: 10))
                .overlay(RoundedRectangle(cornerRadius: 10).stroke(Theme.cardBorder))
                .accessibilityElement(children: .combine)
                .accessibilityLabel("\(user.streakDays ?? 0) day streak")
            }
            XPBar(progress: model.xpProgress)
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
                .font(.system(size: 12))
                .kerning(0.4)
                .foregroundStyle(Theme.dim)
            Text(model.sessionActive ? "Workout in progress" : "No workout logged yet")
                .font(Theme.display(20))
                .foregroundStyle(Theme.text)
            Button {
                Task {
                    if !model.sessionActive {
                        await model.startWorkout()
                    }
                    if model.sessionActive {
                        onStartWorkout()
                    }
                }
            } label: {
                Label(model.sessionActive ? "Resume Workout" : "Start Workout", systemImage: "plus")
            }
            .buttonStyle(PrimaryButtonStyle())
            .accessibilityIdentifier("homeStartWorkoutButton")
            .padding(.top, 10)
        }
        .frame(maxWidth: .infinity)
        .padding(18)
        .cardStyle()
    }

    private var friendActivity: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack {
                Text("Friend activity")
                    .font(Theme.display(16))
                    .foregroundStyle(Theme.text)
                Spacer()
                Text("See all")
                    .font(.system(size: 12))
                    .foregroundStyle(Theme.fire)
            }
            .padding(.top, 2)
            ForEach(model.friendActivity) { item in
                HStack(spacing: 12) {
                    RoundedRectangle(cornerRadius: 9)
                        .fill(Theme.violet)
                        .frame(width: 32, height: 32)
                    Text("\(Text(item.userName).bold().foregroundStyle(Theme.text)) \(item.text)")
                        .font(.system(size: 13))
                        .foregroundStyle(Theme.dim)
                    Spacer()
                    Text("\(item.hoursAgo)h")
                        .font(.system(size: 11))
                        .foregroundStyle(Theme.faint)
                }
                .padding(.horizontal, 12)
                .padding(.vertical, 11)
                .cardStyle(cornerRadius: 14)
            }
        }
    }
}

#Preview {
    HomeView()
        .environment(AppModel(api: MockAPIClient()))
        .preferredColorScheme(.dark)
}
