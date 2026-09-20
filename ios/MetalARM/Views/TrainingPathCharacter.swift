//
//  TrainingPathCharacter.swift
//  MetalARM
//
//  A rotatable 3D figure per training path, so the choice can be made on what
//  a build LOOKS like rather than on three labels.
//
//  These are PLACEHOLDERS, built from primitives rather than loaded from an
//  asset: lean, broad and thick silhouettes whose proportions differ enough to
//  read at a glance. That keeps the step buildable and testable while the real
//  characters are commissioned - swapping one in later means loading a .usdz
//  into `scene` and deleting the builder below, with no other change.
//
//  Drag rotates the figure; left alone it turns slowly on its own. If a scene
//  cannot be built at all, the card shows a flat silhouette and stays
//  selectable: a 3D failure must never block onboarding.
//

import SceneKit
import SwiftUI

struct TrainingPathCharacter: View {
    let category: String
    var height: CGFloat = 150

    var body: some View {
        Group {
            if let scene = CharacterScene.make(for: category) {
                SceneView(
                    scene: scene,
                    options: [.allowsCameraControl, .autoenablesDefaultLighting]
                )
                .background(Color.clear)
                .accessibilityIdentifier("pathCharacter-\(category)")
            } else {
                Image(systemName: "figure.strengthtraining.traditional")
                    .font(.system(size: height * 0.5, weight: .semibold))
                    .foregroundStyle(Theme.silver)
                    .accessibilityIdentifier("pathCharacterFallback-\(category)")
            }
        }
        .frame(height: height)
        .accessibilityLabel("\(category) build")
    }
}

/// The placeholder figures. One set of proportions per path.
enum CharacterScene {
    /// (shoulder width, chest depth, waist, limb thickness, leg length, stance)
    private struct Build {
        let shoulders: CGFloat
        let chest: CGFloat
        let waist: CGFloat
        let limb: CGFloat
        let legs: CGFloat
        let stance: CGFloat
    }

    private static let builds: [String: Build] = [
        // Lean and long-limbed, feet apart as if about to move.
        "athlete": Build(shoulders: 0.46, chest: 0.20, waist: 0.20, limb: 0.065, legs: 0.62, stance: 0.20),
        // The V: wide shoulders, deep chest, tight waist.
        "bodybuilder": Build(shoulders: 0.70, chest: 0.30, waist: 0.24, limb: 0.105, legs: 0.52, stance: 0.17),
        // Thick everywhere and planted wide.
        "powerlifter": Build(shoulders: 0.62, chest: 0.34, waist: 0.38, limb: 0.115, legs: 0.44, stance: 0.26),
    ]

    static func make(for category: String) -> SCNScene? {
        guard let build = builds[category] else { return nil }
        let scene = SCNScene()
        let figure = SCNNode()

        let metal = SCNMaterial()
        metal.lightingModel = .physicallyBased
        metal.diffuse.contents = UIColor(white: 0.78, alpha: 1)
        metal.metalness.contents = 0.65
        metal.roughness.contents = 0.35

        func add(_ geometry: SCNGeometry, at position: SCNVector3, rotatedZ: CGFloat = 0) {
            geometry.materials = [metal]
            let node = SCNNode(geometry: geometry)
            node.position = position
            node.eulerAngles.z = Float(rotatedZ)
            figure.addChildNode(node)
        }

        let hipY = build.legs
        let torso = build.chest * 1.9

        // Head, then torso tapering from shoulders to waist.
        add(SCNSphere(radius: build.chest * 0.42), at: SCNVector3(0, Float(hipY + torso + 0.16), 0))
        add(
            SCNCylinder(radius: build.limb * 0.8, height: 0.1),
            at: SCNVector3(0, Float(hipY + torso + 0.05), 0))
        add(
            SCNCone(topRadius: build.shoulders * 0.5, bottomRadius: build.waist * 0.5, height: torso),
            at: SCNVector3(0, Float(hipY + torso / 2), 0))

        // Arms, hanging away from the body by the width of the shoulders.
        for side in [-1.0, 1.0] {
            add(
                SCNCapsule(capRadius: build.limb, height: torso * 0.95),
                at: SCNVector3(Float(side) * Float(build.shoulders * 0.55), Float(hipY + torso * 0.45), 0),
                rotatedZ: side * 0.12)
        }
        // Legs, set apart by the stance.
        for side in [-1.0, 1.0] {
            add(
                SCNCapsule(capRadius: build.limb * 1.1, height: build.legs),
                at: SCNVector3(Float(side) * Float(build.stance * 0.5), Float(build.legs / 2), 0))
        }

        figure.position = SCNVector3(0, -0.55, 0)
        // Turning slowly on its own: alive, without asking for a gesture.
        figure.runAction(.repeatForever(.rotateBy(x: 0, y: .pi * 2, z: 0, duration: 18)))
        scene.rootNode.addChildNode(figure)

        let camera = SCNNode()
        camera.camera = SCNCamera()
        camera.camera?.fieldOfView = 38
        camera.position = SCNVector3(0, 0.15, 3.1)
        scene.rootNode.addChildNode(camera)

        let key = SCNNode()
        key.light = SCNLight()
        key.light?.type = .directional
        key.light?.intensity = 750
        key.position = SCNVector3(2, 3, 4)
        key.look(at: SCNVector3Zero)
        scene.rootNode.addChildNode(key)

        return scene
    }
}
