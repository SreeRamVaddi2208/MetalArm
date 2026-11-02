//
//  ExerciseDemo.swift
//  MetalARM
//
//  The exercise's figure: what it works, drawn on the body. Served by the web
//  app, so a new figure is a data import (backend/scripts/import_figures.py)
//  and no app release. A custom exercise with no figure shows a plain icon, so
//  the layout is the same either way.
//

import SwiftUI

/// Figures live at paths the web app serves ("/exercises/diagrams/x.png").
func figureURL(_ path: String?) -> URL? {
    guard let path, !path.isEmpty else { return nil }
    return URL(string: path, relativeTo: AppConfig.webBaseURL)?.absoluteURL
}

struct FigureImage: View {
    let path: String?

    var body: some View {
        AsyncImage(url: figureURL(path)) { image in
            image.resizable().scaledToFit()
        } placeholder: {
            Image(systemName: "figure.strengthtraining.traditional")
                .font(Theme.label)
                .foregroundStyle(Theme.text3)
        }
    }
}

struct ExerciseDemo: View {
    let exercise: Exercise
    var size: CGFloat = 96
    var cornerRadius: CGFloat = Theme.radius
    /// Where this figure is being shown. The same exercise appears in several
    /// places at once - a card, the sheet over it, the picker - so the place
    /// is part of the identifier, or a test cannot say which one it means.
    var context: String = "demo"

    var body: some View {
        ZStack {
            RoundedRectangle(cornerRadius: cornerRadius)
                .fill(Theme.surface2)
            FigureImage(path: exercise.thumbnailUrl)
        }
        .frame(width: size, height: size)
        // One element, not a stack of them: a figure is a single thing to a
        // screen reader.
        .accessibilityElement(children: .ignore)
        .accessibilityLabel("\(exercise.name): muscles worked")
        .accessibilityIdentifier(context + "Figure-" + exercise.name)
    }
}
