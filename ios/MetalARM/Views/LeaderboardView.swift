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
                                .foregroundStyle(Theme.fire)
                        }
                        .accessibilityLabel("Add a party")
                    }
                }
                .padding(.bottom, 6)

                if model.parties.isEmpty {
                    if !model.isBusy { emptyState }
                } else {
                    partyHeader
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
                .foregroundStyle(Theme.fire)
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
                .background(Theme.fire, in: RoundedRectangle(cornerRadius: 8))
        }
        .padding(.bottom, 4)
    }

    private func row(_ entry: PartyBoardEntry) -> some View {
        HStack(spacing: 12) {
            Text("\(entry.position)")
                .font(Theme.display(14, .heavy))
                .foregroundStyle(entry.isMe ? Theme.fire : Theme.faint)
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
        .background(entry.isMe ? Theme.fire.opacity(0.16) : Color.clear, in: RoundedRectangle(cornerRadius: 14))
        .overlay(RoundedRectangle(cornerRadius: 14).stroke(entry.isMe ? Theme.fire.opacity(0.3) : Color.clear))
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
            .foregroundStyle(Theme.fire)
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
