//
//  LibraryProgramView.swift
//  MetalARM
//
//  A program: what it is, its weeks and days, the workouts in it. The one
//  primary follows it - and once followed, starts the next workout.
//

import SwiftUI

struct LibraryProgramView: View {
    @Environment(AppModel.self) private var model
    let slug: String
    var onStarted: () -> Void = {}

    private var program: LibraryProgram? { model.libraryProgram?.slug == slug ? model.libraryProgram : nil }

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: Theme.Space.s24) {
                if let program {
                    content(program)
                } else if model.errorMessage.isEmpty {
                    VStack(spacing: Theme.Space.s12) {
                        Skeleton(height: 96)
                        Skeleton(height: 64)
                        Skeleton(height: 200)
                    }
                }
                ErrorState(message: model.errorMessage) { Task { await model.loadLibraryProgram(slug) } }
            }
            .screen()
        }
        .background(Theme.bg)
        .navigationBarTitleDisplayMode(.inline)
        .task { await model.loadLibraryProgram(slug) }
        .pinnedPrimary {
            if let program { primary(program) }
        }
    }

    @ViewBuilder
    private func content(_ program: LibraryProgram) -> some View {
        VStack(alignment: .leading, spacing: Theme.Space.s8) {
            Text(program.name).font(Theme.titleLG).foregroundStyle(Theme.text)
                .accessibilityAddTraits(.isHeader)
            Pill(label: program.categoryLabel, accent: false)
        }
        HStack(spacing: Theme.Space.s16) {
            StatTile(value: "\(program.weeks)", label: "Weeks")
            StatTile(value: "\(program.daysPerWeek)", label: "Days a week")
            StatTile(value: LibraryVocabulary.label(program.difficulty), label: "Level")
        }
        if let description = program.description, !description.isEmpty {
            Text(description).font(Theme.body).foregroundStyle(Theme.text2)
        }
        if let enrollment = program.enrollment, enrollment.status == "active" {
            HStack {
                Text("Following · \(enrollment.whereLabel)").font(Theme.caption).foregroundStyle(Theme.text2)
                Spacer()
                Button("Pause") { Task { await model.unfollowProgram(slug) } }
                    .buttonStyle(.ghost)
                    .accessibilityIdentifier("pauseProgramButton")
            }
        }
        SectionBlock(title: "Schedule") {
            ScheduleGrid(weeks: program.schedule)
        }
        SectionBlock(title: "Workouts in this program") {
            RowGroup {
                ForEach(program.workouts) { WorkoutRow(workout: $0) }
            }
        }
        Text(LibraryVocabulary.note).font(Theme.caption).foregroundStyle(Theme.text2)
    }

    @ViewBuilder
    private func primary(_ program: LibraryProgram) -> some View {
        let enrollment = program.enrollment
        switch enrollment?.status {
        case "active":
            if let next = enrollment?.nextWorkout {
                Button {
                    Task { if await model.startLibraryWorkout(next.slug) { onStarted() } }
                } label: {
                    Label("Start next: \(next.name)", systemImage: "play.fill").lineLimit(1)
                }
                .buttonStyle(.primary)
                .disabled(model.isBusy)
                .accessibilityIdentifier("startNextButton")
            } else {
                followButton("Follow again")
            }
        case "paused": followButton("Resume program")
        case "completed": followButton("Start it again")
        default: followButton("Follow program")
        }
    }

    private func followButton(_ title: String) -> some View {
        Button(title) { Task { await model.followProgram(slug) } }
            .buttonStyle(.primary)
            .disabled(model.isBusy)
            .accessibilityIdentifier("followProgramButton")
    }
}
