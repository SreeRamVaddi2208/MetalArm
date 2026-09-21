//
//  TrainingPathCharacter.swift
//  MetalARM
//
//  A rotatable 3D figure per training path, so the choice can be made on what
//  a build LOOKS like rather than on three labels.
//
//  THE MODELS ARE FILES, NOT CODE. Drop `athlete.usdz`, `bodybuilder.usdz` and
//  `powerlifter.usdz` into MetalARM/Models/ and they are used automatically -
//  the target uses file-system synchronized groups, so Xcode picks new files up
//  without a project edit. See that folder's README for what to buy and how to
//  export it. Nothing else here changes.
//
//  Until a file exists for a path, a built-in placeholder stands in: primitives
//  shaped lean, broad and thick. It is honestly a mannequin, and it is there so
//  the screen, the tests and the recordings work while the art is sourced.
//
//  Whatever is shown, the model is framed and lit the same way: centred on its
//  own bounding box, scaled to fill the card, turning slowly, and draggable.
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
                .background(Theme.bg2)
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

    /// A real model if one has been added, else the placeholder.
    static func make(for category: String) -> SCNScene? {
        if let scene = bundled(category) { return scene }
        return placeholder(for: category)
    }

    /// `<category>.usdz` from the app bundle, framed and lit like the
    /// placeholder so a swap changes the art and nothing else.
    static func bundled(_ category: String) -> SCNScene? {
        guard let url = Bundle.main.url(forResource: category, withExtension: "usdz")
            ?? Bundle.main.url(forResource: category, withExtension: "scn"),
            let scene = try? SCNScene(url: url, options: [.checkConsistency: true])
        else { return nil }

        scene.background.contents = surface
        let figure = SCNNode()
        for child in scene.rootNode.childNodes where child.camera == nil && child.light == nil {
            child.removeFromParentNode()
            figure.addChildNode(child)
        }

        // Models arrive at any size and off any origin, so frame it rather than
        // trusting the export: centre on the bounding box, then scale to fit.
        let (minBound, maxBound) = figure.boundingBox
        let size = SCNVector3(maxBound.x - minBound.x, maxBound.y - minBound.y, maxBound.z - minBound.z)
        let tallest = max(size.x, max(size.y, size.z))
        if tallest > 0 {
            let scale = Float(1.9) / tallest
            figure.scale = SCNVector3(scale, scale, scale)
            figure.position = SCNVector3(
                -(minBound.x + size.x / 2) * scale,
                -(minBound.y + size.y / 2) * scale,
                -(minBound.z + size.z / 2) * scale)
        }
        spin(figure)
        scene.rootNode.addChildNode(figure)
        light(scene)
        return scene
    }

    private static let surface = UIColor(red: 0x12 / 255, green: 0x12 / 255, blue: 0x14 / 255, alpha: 1)

    private static func spin(_ node: SCNNode) {
        node.runAction(.repeatForever(.rotateBy(x: 0, y: .pi * 2, z: 0, duration: 18)))
    }

    private static func light(_ scene: SCNScene) {
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

        // A second, softer light so the far side is not a silhouette.
        let fill = SCNNode()
        fill.light = SCNLight()
        fill.light?.type = .omni
        fill.light?.intensity = 320
        fill.position = SCNVector3(-2.5, 1.5, 2)
        scene.rootNode.addChildNode(fill)
    }

    static func placeholder(for category: String) -> SCNScene? {
        guard let build = builds[category] else { return nil }
        let scene = SCNScene()
        // SceneKit paints its own background, and its default is WHITE, which
        // put a bright rectangle behind every figure on a near-black card.
        // `.clear` is not enough - it falls back to white - so name the colour:
        // Theme.bg2 (#121214), the same well the rest of the card sits in.
        scene.background.contents = surface
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
        spin(figure)
        scene.rootNode.addChildNode(figure)
        light(scene)
        return scene
    }
}
