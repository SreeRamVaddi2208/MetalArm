//
//  CreditsView.swift
//  MetalARM
//
//  Who drew each exercise figure, and whose words the how-to steps are. A
//  condition of using licensed material, not a courtesy.
//

import SwiftUI

struct CreditsView: View {
    @Environment(AppModel.self) private var model
    @State private var cards: [ExerciseCard] = []
    @State private var error = ""

    private var figures: [ExerciseCard] { cards.filter { $0.mediaLicense != nil && $0.mediaAuthor != "MetalArm" } }
    private var texts: [ExerciseCard] { cards.filter { $0.textSourceUrl != nil } }

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: Theme.Space.s16) {
                Text("MetalArm's own muscle figures are released under CC0 1.0. Many how-to steps come from the wger project (wger.de) and its contributors, under Creative Commons Attribution-ShareAlike licences.")
                    .font(Theme.body).foregroundStyle(Theme.text2)
                if !error.isEmpty {
                    ErrorState(message: error) { Task { await load() } }
                }
                if !figures.isEmpty {
                    SectionBlock(title: "Exercise figures") {
                        RowGroup {
                            ForEach(figures) { card in
                                entry(card.name, "\(card.mediaAuthor ?? "") · \(card.mediaLicense ?? "")", card.mediaSourceUrl)
                            }
                        }
                    }
                }
                if !texts.isEmpty {
                    SectionBlock(title: "How-to steps") {
                        RowGroup {
                            ForEach(texts) { card in
                                entry(card.name, "wger contributors · \(card.textLicense ?? "")", card.textSourceUrl)
                            }
                        }
                    }
                }
            }
            .screen()
        }
        .background(Theme.bg)
        .navigationTitle("Credits")
        .navigationBarTitleDisplayMode(.inline)
        .task { await load() }
    }

    @ViewBuilder
    private func entry(_ title: String, _ subtitle: String, _ source: String?) -> some View {
        if let url = source.flatMap(URL.init(string:)) {
            Link(destination: url) { ListRow(title: title, subtitle: subtitle, chevron: true) }
        } else {
            ListRow(title: title, subtitle: subtitle)
        }
    }

    private func load() async {
        error = ""
        var all: [ExerciseCard] = []
        var cursor: String?
        do {
            repeat {
                let page = try await model.api.browseExercises(query: "", muscle: nil, equipment: nil, cursor: cursor)
                all += page.items.filter { !$0.isCustom }
                cursor = page.nextCursor
            } while cursor != nil
            cards = all
        } catch {
            self.error = error.localizedDescription
        }
    }
}
