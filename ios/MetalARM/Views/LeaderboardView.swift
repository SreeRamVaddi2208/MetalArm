//
//  LeaderboardView.swift
//  MetalARM
//
//  The leaderboard, opened from Home: your party's weekly workout board, this
//  week's league, and the party raid. There is no global board - parties are
//  how friends compete.
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
            VStack(alignment: .leading, spacing: Theme.Space.s24) {
                if let league = model.league {
                    leagueSection(league)
                }
                if model.parties.isEmpty {
                    if !model.isBusy { emptyState }
                } else {
                    partySection
                    if let raid = model.partyRaid {
                        raidSection(raid)
                    }
                    if let party = model.selectedParty, let code = party.inviteCode {
                        inviteRow(party: party, code: code)
                    }
                }
                ErrorText(message: model.errorMessage)
            }
            .screen()
        }
        .background(Theme.bg)
        .navigationTitle("Leaderboard")
        .navigationBarTitleDisplayMode(.inline)
        .toolbar {
            if !model.parties.isEmpty {
                ToolbarItem(placement: .topBarTrailing) {
                    Menu {
                        Button("Create a party", systemImage: "plus") { showingCreate = true }
                        Button("Join with a code", systemImage: "person.badge.plus") { showingJoin = true }
                    } label: {
                        Image(systemName: "plus").foregroundStyle(Theme.text2)
                    }
                    .accessibilityLabel("Add a party")
                }
            }
        }
        .task { await model.loadParties() }
        .task { await model.loadLeague() }
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

    /// This week's league: division, where the user sits, and the cutoffs.
    private func leagueSection(_ league: League) -> some View {
        SectionBlock(title: "League") {
            Text("\(league.divisionLabel) · \(league.daysLeft(from: Date())) days left")
                .font(Theme.caption).foregroundStyle(Theme.text2)
            if let me = league.me {
                Text("You're \(me.position) of \(league.entries.count) with \(me.points) points")
                    .font(Theme.body).foregroundStyle(Theme.text)
            }
            VStack(spacing: Theme.Space.s4) {
                ForEach(league.entries.prefix(5)) { entry in
                    BoardRow(position: entry.position, name: entry.displayName, detail: "",
                             value: "\(entry.points)", isMe: entry.isMe)
                }
            }
            Text("Top \(league.promoteCutoff) move up. Bottom places move down.")
                .font(Theme.caption).foregroundStyle(Theme.text2)
        }
        .accessibilityElement(children: .contain)
        .accessibilityIdentifier("leagueCard")
    }

    private var emptyState: some View {
        VStack(spacing: Theme.Space.s12) {
            EmptyState(systemImage: "person.3",
                       line: "Create a party and share its code, or join one. Members are ranked by workout points each week.")
            Button("Create a party") { showingCreate = true }
                .buttonStyle(.primary)
                .accessibilityIdentifier("createPartyButton")
            Button("Join with an invite code") { showingJoin = true }
                .buttonStyle(.secondary)
                .accessibilityIdentifier("joinPartyButton")
        }
    }

    private var partySection: some View {
        SectionBlock(title: model.selectedParty?.name ?? "Your party") {
            if model.parties.count > 1 {
                ScrollView(.horizontal, showsIndicators: false) {
                    HStack(spacing: Theme.Space.s8) {
                        ForEach(model.parties) { party in
                            Chip(label: party.name, selected: party.id == model.selectedParty?.id) {
                                Task { await model.selectParty(party.id) }
                            }
                        }
                    }
                }
            }
            Text("This week").font(Theme.caption).foregroundStyle(Theme.text2)
            VStack(spacing: Theme.Space.s4) {
                ForEach(model.partyBoard?.entries ?? []) { entry in
                    BoardRow(position: entry.position, name: entry.displayName,
                             detail: "\(entry.workouts) workout\(entry.workouts == 1 ? "" : "s")",
                             value: "\(entry.points)", isMe: entry.isMe, rank: entry.rank)
                        .accessibilityIdentifier("partyRow-\(entry.displayName)")
                }
            }
        }
    }

    /// This week's party boss: HP, idle-day healing, and the top hitters.
    private func raidSection(_ raid: PartyRaid) -> some View {
        SectionBlock(title: "Party raid") {
            HStack {
                Text(raid.name).font(Theme.body).foregroundStyle(Theme.text)
                Spacer()
                if raid.defeated {
                    Pill(label: "Defeated")
                } else {
                    let days = raid.daysLeft()
                    Text("\(days) day\(days == 1 ? "" : "s") left").font(Theme.caption).foregroundStyle(Theme.text2)
                }
            }
            ProgressBar(progress: raid.hpFraction,
                        label: "\(raid.hpRemaining.formatted()) / \(raid.maxHp.formatted()) HP"
                            + (raid.healed > 0 && !raid.defeated ? " · +\(raid.healed.formatted()) healed on idle days" : ""))
                .accessibilityLabel("Boss health")
            if raid.hitters.isEmpty {
                Text("No hits yet. Finish a workout to strike first.").font(Theme.body).foregroundStyle(Theme.text2)
            } else {
                RowGroup {
                    ForEach(raid.hitters.prefix(3)) { hitter in
                        ListRow(title: hitter.displayName + (hitter.isMe ? " (you)" : ""),
                                trailing: "\(hitter.damage.formatted()) dmg")
                    }
                }
            }
        }
        .accessibilityElement(children: .contain)
        .accessibilityIdentifier("raidCard")
    }

    private func inviteRow(party: Party, code: String) -> some View {
        HStack {
            VStack(alignment: .leading, spacing: 0) {
                Text("Invite code").font(Theme.caption).foregroundStyle(Theme.text2)
                Text(code).font(Theme.title).foregroundStyle(Theme.text).textSelection(.enabled)
            }
            Spacer()
            ShareLink(item: "Join my MetalArm party \"\(party.name)\" with invite code \(code).") {
                Label("Share", systemImage: "square.and.arrow.up").font(Theme.label)
            }
            .buttonStyle(MAButtonStyle(kind: .ghost, full: false))
        }
        .card()
    }
}

/// One line of a board: place, name (rank beside it), the number it is
/// ranked by. Yours is tinted.
struct BoardRow: View {
    let position: Int
    let name: String
    var detail: String = ""
    let value: String
    let isMe: Bool
    var rank: String?

    var body: some View {
        HStack(spacing: Theme.Space.s12) {
            Text("\(position)").font(Theme.label).foregroundStyle(Theme.text2).frame(width: Theme.Space.s24)
            Avatar(initials: initials(of: name))
            VStack(alignment: .leading, spacing: 0) {
                HStack(spacing: Theme.Space.s8) {
                    Text(name + (isMe ? " (you)" : "")).font(Theme.body).foregroundStyle(Theme.text).lineLimit(1)
                    if let rank { RankBadge(rank: rank, size: 24) }
                }
                if !detail.isEmpty {
                    Text(detail).font(Theme.caption).foregroundStyle(Theme.text2)
                }
            }
            Spacer()
            Text(value).font(Theme.body).foregroundStyle(Theme.text2)
        }
        .padding(.horizontal, Theme.Space.s8)
        .frame(minHeight: Theme.rowMin)
        .background(isMe ? Theme.accentSoft : .clear, in: RoundedRectangle(cornerRadius: Theme.radius))
        .accessibilityElement(children: .combine)
    }
}

#Preview {
    NavigationStack { LeaderboardView() }
        .environment(AppModel(api: MockAPIClient()))
        .preferredColorScheme(.dark)
}
