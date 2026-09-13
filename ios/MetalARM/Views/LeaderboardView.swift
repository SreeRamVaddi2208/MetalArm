//
//  LeaderboardView.swift
//  MetalARM
//
//  Port of frontend/frontend/pages/leaderboard.py.
//

import SwiftUI

struct LeaderboardView: View {
    @Environment(AppModel.self) private var model

    var body: some View {
        ScrollView {
            VStack(spacing: 8) {
                HStack {
                    Text("Leaderboard")
                        .font(Theme.display(28))
                        .foregroundStyle(Theme.text)
                    Spacer()
                    Text("This Week")
                        .font(.system(size: 11.5, weight: .bold))
                        .foregroundStyle(Theme.bg)
                        .padding(.horizontal, 10)
                        .padding(.vertical, 6)
                        .background(Theme.fire, in: RoundedRectangle(cornerRadius: 8))
                        .padding(3)
                        .cardStyle(cornerRadius: 10)
                }
                .padding(.bottom, 12)
                ForEach(model.leaderboard) { entry in
                    row(entry)
                }
                ErrorText(message: model.errorMessage)
                // Placeholder until the backend has a friend graph and invite flow.
                Label("Invite friends", systemImage: "person.badge.plus")
                    .font(Theme.display(13.5, .semibold))
                    .foregroundStyle(Theme.dim)
                    .frame(maxWidth: .infinity)
                    .padding(13)
                    .cardStyle(cornerRadius: 14)
                    .padding(.top, 12)
            }
            .padding(20)
        }
        .background(Theme.bg)
        .task { await model.loadLeaderboard() }
        .refreshable { await model.loadLeaderboard() }
    }

    private func row(_ entry: LeaderboardEntry) -> some View {
        let isMe = entry.isCurrentUser
        return HStack(spacing: 12) {
            Text("\(entry.rank)")
                .font(Theme.display(14, .heavy))
                .foregroundStyle(isMe ? Theme.fire : Theme.faint)
                .frame(width: 20)
            RoundedRectangle(cornerRadius: 10)
                .fill(Theme.violet)
                .frame(width: 34, height: 34)
            HStack(spacing: 4) {
                Text(entry.name)
                    .font(.system(size: 13.5, weight: .bold))
                    .foregroundStyle(Theme.text)
                if isMe {
                    Text("(you)")
                        .font(.system(size: 13.5, weight: .medium))
                        .foregroundStyle(Theme.dim)
                }
            }
            Spacer()
            Text("\(entry.points)")
                .font(Theme.display(13))
                .foregroundStyle(isMe ? Theme.text : Theme.dim)
        }
        .padding(.horizontal, 14)
        .padding(.vertical, 12)
        .background(isMe ? Theme.fire.opacity(0.16) : Color.clear, in: RoundedRectangle(cornerRadius: 14))
        .overlay(RoundedRectangle(cornerRadius: 14).stroke(isMe ? Theme.fire.opacity(0.3) : Color.clear))
    }
}

#Preview {
    LeaderboardView()
        .environment(AppModel(api: MockAPIClient()))
        .preferredColorScheme(.dark)
}
