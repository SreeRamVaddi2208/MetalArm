//
//  ExerciseDemo.swift
//  MetalARM
//
//  The short clip that shows what a movement looks like. The link comes from
//  the exercise's `media_url`, so adding a demo is adding a URL to the library
//  (backend/app/data/exercises.json) - no app release needed.
//
//  Silent, looping and without controls: it is a diagram that moves, not
//  something to watch. An exercise with no link shows a placeholder rather
//  than an empty box, so the layout is the same either way.
//

import AVKit
import SwiftUI

struct ExerciseDemo: View {
    let exercise: Exercise
    var size: CGFloat = 96
    var cornerRadius: CGFloat = 12
    /// Where this demo is being shown. The same exercise appears in several
    /// places at once - a card, the sheet over it, the picker - so the place
    /// is part of the identifier, or a test cannot say which one it means.
    var context: String = "demo"

    var body: some View {
        ZStack {
            RoundedRectangle(cornerRadius: cornerRadius)
                .fill(Theme.bg2)
            if let url = exercise.mediaUrl.flatMap(URL.init(string:)) {
                LoopingVideo(url: url)
                    .clipShape(RoundedRectangle(cornerRadius: cornerRadius))
            } else {
                VStack(spacing: 5) {
                    Image(systemName: "play.slash")
                        .font(Theme.body(size > 70 ? 18 : 13))
                        .foregroundStyle(Theme.faint)
                    if size > 70 {
                        Text("Demo coming")
                            .font(Theme.body(10))
                            .foregroundStyle(Theme.faint)
                    }
                }

            }
        }
        .frame(width: size, height: size)
        .overlay(RoundedRectangle(cornerRadius: cornerRadius).stroke(Theme.cardBorder))
        // One element, not a stack of them: a demo is a single thing to a
        // screen reader. The identifier says which state it is in, so a test
        // can tell a playing clip from the "demo coming" placeholder.
        .accessibilityElement(children: .ignore)
        .accessibilityLabel(
            exercise.mediaUrl == nil
                ? "No demo for \(exercise.name) yet"
                : "Demo of \(exercise.name)")
        .accessibilityIdentifier(
            context + (exercise.mediaUrl == nil ? "Placeholder-" : "Video-") + exercise.name)
    }
}

/// AVPlayer wrapped for SwiftUI: muted, looping, no controls, and paused the
/// moment it leaves the screen so a list of demos cannot eat the battery.
private struct LoopingVideo: UIViewControllerRepresentable {
    let url: URL

    func makeUIViewController(context: Context) -> AVPlayerViewController {
        let player = AVQueuePlayer()
        player.isMuted = true
        // Looping without re-buffering, and without a notification observer
        // that would outlive this view.
        context.coordinator.looper = AVPlayerLooper(
            player: player, templateItem: AVPlayerItem(url: url))

        let controller = AVPlayerViewController()
        controller.player = player
        controller.showsPlaybackControls = false
        controller.videoGravity = .resizeAspectFill
        controller.view.backgroundColor = .clear
        controller.view.isUserInteractionEnabled = false
        player.play()
        return controller
    }

    func updateUIViewController(_ controller: AVPlayerViewController, context: Context) {}

    static func dismantleUIViewController(_ controller: AVPlayerViewController, coordinator: Coordinator) {
        controller.player?.pause()
        coordinator.looper = nil
    }

    func makeCoordinator() -> Coordinator { Coordinator() }

    final class Coordinator {
        var looper: AVPlayerLooper?
    }
}
