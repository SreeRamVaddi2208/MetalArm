//
//  LeaderboardView.swift
//  MetalARM
//
//  The Ranks tab: your party's weekly workout leaderboard. There is no global
//  board - parties are how friends compete.
//

import SwiftUI

struct LeaderboardView: View {
    @Environment(AppModel.self) private var model
    @State private var showingCreate = false
    @State private var showingJoin = false
    @State private var partyName = ""
    @State private var inviteCode = ""

    var body: some View {
        ScrollView {
            VStack(spacing: 10) {
                HStack {
                    Text("Ranks")
                        .font(Theme.display(28))
                        .foregroundStyle(Theme.text)
                    Spacer()
                    if !model.parties.isEmpty {
                        Menu {
                            Button("Create a Party", systemImage: "plus") { showingCreate = true }
                            Button("Join with Code", systemImage: "person.badge.plus") { showingJoin = true }
                        } label: {
                            Image(systemName: "plus.circle.fill")
                                .font(Theme.body(24))
                                .foregroundStyle(Theme.accent)
                        }
                        .accessibilityLabel("Add a party")
                    }
                }
                .padding(.bottom, 6)

                if model.parties.isEmpty {
                    if !model.isBusy { emptyState }
                } else {
                    partyHeader
                    if let raid = model.partyRaid {
                        raidCard(raid)
                    }
                    ForEach(model.partyBoard?.entries ?? []) { entry in
                        row(entry)
                    }
                    if let party = model.selectedParty, let code = party.inviteCode {
                        inviteCard(party: party, code: code)
                    }
                }
                ErrorText(message: model.errorMessage)
            }
            .padding(20)
        }
        .background(Theme.bg)
        .task { await model.loadParties() }
        .refreshable { await model.loadParties() }
        .alert("Create a party", isPresented: $showingCreate) {
            TextField("Party name", text: $partyName)
            Button("Create") {
                let name = partyName
                partyName = ""
                Task { await model.createParty(name: name) }
            }
            Button("Cancel", role: .cancel) { partyName = "" }
        } message: {
            Text("Friends join with the invite code you share.")
        }
        .alert("Join a party", isPresented: $showingJoin) {
            TextField("Invite code", text: $inviteCode)
                .textInputAutocapitalization(.characters)
                .autocorrectionDisabled()
            Button("Join") {
                let code = inviteCode
                inviteCode = ""
                Task { await model.joinParty(inviteCode: code) }
            }
            Button("Cancel", role: .cancel) { inviteCode = "" }
        } message: {
            Text("Enter the code a party member shared with you.")
        }
    }

    private var emptyState: some View {
        VStack(spacing: 14) {
            Image(systemName: "person.3.fill")
                .font(Theme.body(40))
                .foregroundStyle(Theme.accent)
            Text("Train with friends")
                .font(Theme.display(22))
                .foregroundStyle(Theme.text)
            Text("Create a party and share its invite code, or join one. Members are ranked by workout points each week.")
                .font(Theme.body(14))
                .foregroundStyle(Theme.dim)
                .multilineTextAlignment(.center)
            Button("Create a Party") { showingCreate = true }
                .buttonStyle(PrimaryButtonStyle())
                .accessibilityIdentifier("createPartyButton")
            Button("Join with Invite Code") { showingJoin = true }
                .buttonStyle(SecondaryButtonStyle())
                .accessibilityIdentifier("joinPartyButton")
        }
        .padding(.top, 40)
    }

    private var partyHeader: some View {
        HStack {
            if model.parties.count > 1 {
                Menu {
                    ForEach(model.parties) { party in
                        Button(party.name) { Task { await model.selectParty(party.id) } }
                    }
                } label: {
                    HStack(spacing: 4) {
                        Text(model.selectedParty?.name ?? "")
                        Image(systemName: "chevron.down")
                            .font(Theme.body(11, .bold))
                    }
                    .font(Theme.display(16))
                    .foregroundStyle(Theme.text)
                }
            } else {
                Text(model.selectedParty?.name ?? "")
                    .font(Theme.display(16))
                    .foregroundStyle(Theme.text)
            }
            Spacer()
            Text("This Week")
                .font(Theme.body(11.5, .bold))
                .foregroundStyle(Theme.bg)
                .padding(.horizontal, 10)
                .padding(.vertical, 6)
                .background(Theme.accent, in: RoundedRectangle(cornerRadius: 8))
        }
        .padding(.bottom, 4)
    }

    private func row(_ entry: PartyBoardEntry) -> some View {
        HStack(spacing: 12) {
            Text("\(entry.position)")
                .font(Theme.display(14, .heavy))
                .foregroundStyle(entry.isMe ? Theme.accent : Theme.faint)
                .frame(width: 20)
            AvatarBadge(initials: initials(of: entry.displayName), size: 34, cornerRadius: 10, fontSize: 12)
            VStack(alignment: .leading, spacing: 2) {
                HStack(spacing: 4) {
                    Text(entry.displayName)
                        .font(Theme.body(13.5, .bold))
                        .foregroundStyle(Theme.text)
                    if entry.isMe {
                        Text("(you)")
                            .font(Theme.body(13.5, .medium))
                            .foregroundStyle(Theme.dim)
                    }
                }
                Text("\(entry.workouts) workout\(entry.workouts == 1 ? "" : "s") · Rank \(entry.rank)")
                    .font(Theme.body(11))
                    .foregroundStyle(Theme.dim)
            }
            Spacer()
            Text("\(entry.points)")
                .font(Theme.display(13))
                .foregroundStyle(entry.isMe ? Theme.text : Theme.dim)
        }
        .padding(.horizontal, 14)
        .padding(.vertical, 12)
        .background(entry.isMe ? Theme.accent.opacity(0.16) : Color.clear, in: RoundedRectangle(cornerRadius: 14))
        .overlay(RoundedRectangle(cornerRadius: 14).stroke(entry.isMe ? Theme.accent.opacity(0.3) : Color.clear))
    }

    /// This week's party boss: HP, idle-day healing, and the top hitters.
    private func raidCard(_ raid: PartyRaid) -> some View {
        VStack(alignment: .leading, spacing: 10) {
            HStack(alignment: .firstTextBaseline) {
                VStack(alignment: .leading, spacing: 2) {
                    Text("PARTY RAID")
                        .font(Theme.body(11, .bold))
                        .kerning(1)
                        .foregroundStyle(Theme.dim)
                    Text(raid.name)
                        .font(Theme.display(20))
                        .foregroundStyle(Theme.text)
                }
                Spacer()
                if raid.defeated {
                    Text("DEFEATED")
                        .font(Theme.body(11, .bold))
                        .foregroundStyle(Theme.bg)
                        .padding(.horizontal, 8)
                        .padding(.vertical, 4)
                        .background(Theme.accent, in: RoundedRectangle(cornerRadius: 6))
                } else {
                    let days = raid.daysLeft()
                    Text("\(days) day\(days == 1 ? "" : "s") left")
                        .font(Theme.body(12, .semibold))
                        .foregroundStyle(Theme.dim)
                }
            }
            GeometryReader { geometry in
                ZStack(alignment: .leading) {
                    Capsule().fill(Theme.bg)
                    Capsule()
                        .fill(LinearGradient(colors: [Theme.accent, Theme.accentDeep], startPoint: .leading, endPoint: .trailing))
                        .frame(width: geometry.size.width * max(0, min(1, raid.hpFraction)))
                }
            }
            .frame(height: 10)
            .accessibilityElement()
            .accessibilityLabel("Boss health")
            .accessibilityValue("\(raid.hpRemaining) of \(raid.maxHp)")
            HStack {
                Text("\(raid.hpRemaining.formatted()) / \(raid.maxHp.formatted()) HP")
                Spacer()
                if raid.healed > 0 && !raid.defeated {
                    Text("+\(raid.healed.formatted()) healed on idle days")
                }
            }
            .font(Theme.body(11.5))
            .foregroundStyle(Theme.dim)
            if raid.hitters.isEmpty {
                Text("No hits yet. Finish a workout to strike first.")
                    .font(Theme.body(12))
                    .foregroundStyle(Theme.dim)
            } else {
                ForEach(raid.hitters.prefix(3)) { hitter in
                    HStack {
                        Text(hitter.displayName + (hitter.isMe ? " (you)" : ""))
                            .font(Theme.body(13, hitter.isMe ? .bold : .regular))
                            .foregroundStyle(Theme.text)
                        Spacer()
                        Text("\(hitter.damage.formatted()) dmg")
                            .font(Theme.display(13))
                            .foregroundStyle(hitter.isMe ? Theme.text : Theme.dim)
                    }
                }
            }
        }
        .padding(16)
        .cardStyle(cornerRadius: 16)
        .padding(.bottom, 6)
        .accessibilityElement(children: .contain)
        .accessibilityIdentifier("raidCard")
    }

    private func inviteCard(party: Party, code: String) -> some View {
        HStack {
            VStack(alignment: .leading, spacing: 2) {
                Text("INVITE CODE")
                    .font(Theme.body(11))
                    .kerning(0.5)
                    .foregroundStyle(Theme.dim)
                Text(code)
                    .font(Theme.display(20))
                    .foregroundStyle(Theme.text)
                    .textSelection(.enabled)
            }
            Spacer()
            ShareLink(item: "Join my MetalArm party \"\(party.name)\" with invite code \(code).") {
                Label("Share", systemImage: "square.and.arrow.up")
                    .font(Theme.body(13, .semibold))
            }
            .foregroundStyle(Theme.accent)
        }
        .padding(14)
        .cardStyle(cornerRadius: 14)
        .padding(.top, 8)
    }
}

#Preview {
    LeaderboardView()
        .environment(AppModel(api: MockAPIClient()))
        .preferredColorScheme(.dark)
}
