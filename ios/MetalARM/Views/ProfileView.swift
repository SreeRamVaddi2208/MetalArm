//
//  ProfileView.swift
//  MetalARM
//
//  Port of frontend/frontend/pages/profile.py.
//

import SwiftUI

struct ProfileView: View {
    @Environment(AppModel.self) private var model

    private let badgeColumns = Array(repeating: GridItem(.flexible(), spacing: 12), count: 4)

    var body: some View {
        ScrollView {
            VStack(spacing: 0) {
                if let user = model.user {
                    AvatarBadge(initials: initials(of: user.name), size: 84, cornerRadius: 24, fontSize: 28, bordered: true)
                    Text(user.name)
                        .font(Theme.display(22))
                        .foregroundStyle(Theme.text)
                        .padding(.top, 12)
                    Text("Level \(user.level) · \(user.levelName)")
                        .font(.system(size: 12.5, weight: .bold))
                        .foregroundStyle(Theme.fire)
                        .padding(.top, 5)
                    XPBar(progress: model.xpProgress, track: Theme.card)
                        .padding(.top, 16)
                    Text("\(user.xpCurrent) / \(user.xpToNextLevel) XP to next level")
                        .font(.system(size: 11))
                        .foregroundStyle(Theme.dim)
                        .padding(.top, 6)
                }
                if let stats = model.profileStats {
                    HStack(spacing: 12) {
                        StatTile(value: "\(stats.workouts)", label: "Workouts")
                        StatTile(value: "\(stats.streakDays)", label: "Day streak")
                        StatTile(value: "\(stats.prsSet)", label: "PRs set")
                    }
                    .padding(.top, 22)
                }
                HStack {
                    Text("Badges")
                        .font(Theme.display(16))
                        .foregroundStyle(Theme.text)
                    Spacer()
                    Text("\(model.badgesEarnedCount) / \(model.badges.count)")
                        .font(.system(size: 12))
                        .foregroundStyle(Theme.fire)
                }
                .padding(.top, 22)
                LazyVGrid(columns: badgeColumns, spacing: 12) {
                    ForEach(model.badges) { badge in
                        badgeTile(badge)
                    }
                }
                .padding(.top, 10)
                ErrorText(message: model.errorMessage)
                    .padding(.top, 12)
            }
            .padding(20)
        }
        .background(Theme.bg)
        .task { await model.loadProfile() }
        .refreshable { await model.loadProfile() }
    }

    private func badgeTile(_ badge: Badge) -> some View {
        VStack(spacing: 6) {
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
                Image(systemName: "rosette")
                    .font(.system(size: 20))
                    .foregroundStyle(badge.earned ? Theme.bg : Theme.faint)
            }
            .aspectRatio(1, contentMode: .fit)
            Text(badge.name)
                .font(.system(size: 10))
                .foregroundStyle(Theme.dim)
                .multilineTextAlignment(.center)
                .lineLimit(2)
        }
        .accessibilityElement(children: .ignore)
        .accessibilityLabel("\(badge.name), \(badge.earned ? "earned" : "locked")")
    }
}

#Preview {
    ProfileView()
        .environment(AppModel(api: MockAPIClient()))
        .preferredColorScheme(.dark)
}
