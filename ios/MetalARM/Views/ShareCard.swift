//
//  ShareCard.swift
//  MetalARM
//
//  A 1080 x 1920 story card for the moment worth bragging about - a rank-up, a
//  level-up, a new record, or just a finished workout - built from the server's
//  FinishResponse and carrying the party invite code, so a share can bring a
//  friend straight into the party.
//

import SwiftUI
import UIKit

struct ShareCardContent: Equatable {
    enum Kind: Equatable { case rankUp, levelUp, record, workout }

    struct Stat: Equatable, Hashable {
        let value: String
        let label: String
    }

    let kind: Kind
    let eyebrow: String
    let headline: String
    let caption: String
    /// The line that follows a personal record; empty for the other kinds.
    var note: String = ""
    let stats: [Stat]
    let inviteCode: String?

    /// The biggest moment of the workout leads: rank-up, then level-up, then a record.
    static func make(result: FinishResult, unit: WeightUnit, inviteCode: String?) -> ShareCardContent {
        let progression = result.progression
        let volume = formatNumber(unit.fromKilograms(result.session.totalVolumeKg).rounded())
        let stats = [
            Stat(value: "\(max(1, result.session.durationSeconds / 60)) min", label: "Duration"),
            Stat(value: "\(volume) \(unit.rawValue)", label: "Volume"),
            Stat(value: "\(result.session.workingSets)", label: result.session.workingSets == 1 ? "Set" : "Sets"),
        ]
        let code = inviteCode.flatMap { $0.isEmpty ? nil : $0 }
        if progression.rankedUp {
            return ShareCardContent(
                kind: .rankUp, eyebrow: "RANK UP", headline: RankTitle.shout(progression.rankAfter),
                caption: "\(RankTitle.of(progression.rankAfter)) at level \(progression.levelAfter)", stats: stats, inviteCode: code)
        }
        if progression.leveledUp {
            return ShareCardContent(
                kind: .levelUp, eyebrow: "LEVEL UP", headline: "\(progression.levelAfter)",
                caption: "Level \(progression.levelAfter) reached", stats: stats, inviteCode: code)
        }
        if let record = result.prEvents.celebrated {
            return ShareCardContent(
                kind: .record, eyebrow: "NEW PERSONAL RECORD", headline: "PR",
                caption: record.headline(in: unit), note: record.motivation, stats: stats,
                inviteCode: code)
        }
        return ShareCardContent(
            kind: .workout, eyebrow: "WORKOUT COMPLETE", headline: "+\(result.breakdown.total)",
            caption: "points earned", stats: stats, inviteCode: code)
    }
}

/// Laid out at 360 x 640 points and rendered at 3x.
struct ShareCardView: View {
    let content: ShareCardContent

    var body: some View {
        ZStack {
            Theme.bg
            RadialGradient(
                colors: [Theme.silver.opacity(0.28), .clear], center: UnitPoint(x: 0.5, y: 0.4),
                startRadius: 0, endRadius: 300)

            VStack(spacing: 0) {
                Text("METALARM")
                    .font(Theme.display(14, .bold))
                    .tracking(6)
                    .foregroundStyle(Theme.dim)
                    .padding(.top, 56)

                Spacer()

                Text(content.eyebrow)
                    .font(Theme.display(16, .bold))
                    .tracking(5)
                    .foregroundStyle(Theme.silver)
                Text(content.headline)
                    .font(Theme.display(120, .bold))
                    .minimumScaleFactor(0.4)
                    .lineLimit(1)
                    .foregroundStyle(
                        LinearGradient(
                            colors: [Theme.accent, Theme.silver, Theme.silverDeep], startPoint: .top, endPoint: .bottom))
                    .shadow(color: Theme.accent.opacity(0.35), radius: 18)
                    .padding(.horizontal, 24)
                Text(content.caption)
                    .font(Theme.body(15))
                    .foregroundStyle(Theme.text)
                    .multilineTextAlignment(.center)
                    .padding(.horizontal, 32)
                    .padding(.top, 6)
                if !content.note.isEmpty {
                    Text(content.note)
                        .font(Theme.body(13, .semibold))
                        .foregroundStyle(Theme.silver)
                        .multilineTextAlignment(.center)
                        .padding(.horizontal, 32)
                        .padding(.top, 8)
                }

                Spacer()

                HStack(spacing: 10) {
                    ForEach(content.stats, id: \.self) { stat in
                        VStack(spacing: 2) {
                            Text(stat.value)
                                .font(Theme.display(16, .bold))
                                .foregroundStyle(Theme.text)
                            Text(stat.label)
                                .font(Theme.body(10))
                                .foregroundStyle(Theme.dim)
                        }
                        .frame(maxWidth: .infinity)
                        .padding(.vertical, 12)
                        .background(Theme.card, in: RoundedRectangle(cornerRadius: 12))
                        .overlay(RoundedRectangle(cornerRadius: 12).stroke(Theme.cardBorder))
                    }
                }
                .padding(.horizontal, 24)

                Text(content.inviteCode.map { "Join my party: \($0)" } ?? "Level up every workout")
                    .font(Theme.body(13, .semibold))
                    .foregroundStyle(Theme.dim)
                    .padding(.top, 18)
                    .padding(.bottom, 48)
            }
        }
        .frame(width: 360, height: 640)
    }
}

enum ShareCardRenderer {
    /// 1080 x 1920 pixels: the size Instagram, TikTok and Snapchat stories use.
    @MainActor
    static func render(_ content: ShareCardContent) -> UIImage? {
        let renderer = ImageRenderer(content: ShareCardView(content: content))
        renderer.scale = 3
        return renderer.uiImage
    }
}
