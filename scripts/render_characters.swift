// Renders the three training-path characters to PNGs for the Android app,
// from the same SceneKit scene the iOS app shows (ios/MetalARM/Views/
// TrainingPathCharacter.swift): the placeholder mannequins today, and the
// real `<category>.usdz` models once they are added to ios/MetalARM/Models/.
//
//     swift scripts/render_characters.swift
//
// Writes android/app/src/main/res/drawable-nodpi/character_<category>.png.
// Re-run it whenever the iOS models change.

import AppKit
import SceneKit

let root = URL(fileURLWithPath: #filePath).deletingLastPathComponent().deletingLastPathComponent()
let output = root.appending(path: "android/app/src/main/res/drawable-nodpi")
let modelsDir = root.appending(path: "ios/MetalARM/Models")

struct Build { let shoulders, chest, waist, limb, legs, stance: CGFloat }

let builds: [String: Build] = [
    "athlete": Build(shoulders: 0.46, chest: 0.20, waist: 0.20, limb: 0.065, legs: 0.62, stance: 0.20),
    "bodybuilder": Build(shoulders: 0.70, chest: 0.30, waist: 0.24, limb: 0.105, legs: 0.52, stance: 0.17),
    "powerlifter": Build(shoulders: 0.62, chest: 0.34, waist: 0.38, limb: 0.115, legs: 0.44, stance: 0.26),
]

func light(_ scene: SCNScene) -> SCNNode {
    let camera = SCNNode()
    camera.camera = SCNCamera()
    camera.camera?.fieldOfView = 38
    // Offscreen renders come out brighter than the live SceneView; bring the
    // metal back to the brushed grey it has on iOS.
    camera.camera?.wantsHDR = true
    camera.camera?.wantsExposureAdaptation = false
    camera.camera?.exposureOffset = -1.6
    camera.position = SCNVector3(0, 0.15, 3.1)
    scene.rootNode.addChildNode(camera)
    let key = SCNNode()
    key.light = SCNLight()
    key.light?.type = .directional
    key.light?.intensity = 750
    key.position = SCNVector3(2, 3, 4)
    key.look(at: SCNVector3Zero)
    scene.rootNode.addChildNode(key)
    let fill = SCNNode()
    fill.light = SCNLight()
    fill.light?.type = .omni
    fill.light?.intensity = 320
    fill.position = SCNVector3(-2.5, 1.5, 2)
    scene.rootNode.addChildNode(fill)
    return camera
}

func bundled(_ category: String) -> SCNScene? {
    for ext in ["usdz", "scn"] {
        let url = modelsDir.appending(path: "\(category).\(ext)")
        // A missing file still yields an (empty) scene, so check first.
        guard FileManager.default.fileExists(atPath: url.path), let scene = try? SCNScene(url: url) else { continue }
        let figure = SCNNode()
        for child in scene.rootNode.childNodes where child.camera == nil && child.light == nil {
            child.removeFromParentNode()
            figure.addChildNode(child)
        }
        let (minBound, maxBound) = figure.boundingBox
        let size = SCNVector3(maxBound.x - minBound.x, maxBound.y - minBound.y, maxBound.z - minBound.z)
        let tallest = max(size.x, max(size.y, size.z))
        if tallest > 0 {
            let scale = 1.9 / tallest
            figure.scale = SCNVector3(scale, scale, scale)
            figure.position = SCNVector3(-(minBound.x + size.x / 2) * scale, -(minBound.y + size.y / 2) * scale, -(minBound.z + size.z / 2) * scale)
        }
        scene.rootNode.addChildNode(figure)
        return scene
    }
    return nil
}

func placeholder(_ build: Build) -> SCNScene {
    let scene = SCNScene()
    let figure = SCNNode()
    let metal = SCNMaterial()
    metal.lightingModel = .physicallyBased
    metal.diffuse.contents = NSColor(white: 0.78, alpha: 1)
    metal.metalness.contents = 0.65
    metal.roughness.contents = 0.35
    func add(_ geometry: SCNGeometry, at position: SCNVector3, rotatedZ: CGFloat = 0) {
        geometry.materials = [metal]
        let node = SCNNode(geometry: geometry)
        node.position = position
        node.eulerAngles.z = rotatedZ
        figure.addChildNode(node)
    }
    let hipY = build.legs
    let torso = build.chest * 1.9
    add(SCNSphere(radius: build.chest * 0.42), at: SCNVector3(0, hipY + torso + 0.16, 0))
    add(SCNCylinder(radius: build.limb * 0.8, height: 0.1), at: SCNVector3(0, hipY + torso + 0.05, 0))
    add(SCNCone(topRadius: build.shoulders * 0.5, bottomRadius: build.waist * 0.5, height: torso), at: SCNVector3(0, hipY + torso / 2, 0))
    for side: CGFloat in [-1, 1] {
        add(SCNCapsule(capRadius: build.limb, height: torso * 0.95),
            at: SCNVector3(side * build.shoulders * 0.55, hipY + torso * 0.45, 0), rotatedZ: side * 0.12)
    }
    for side: CGFloat in [-1, 1] {
        add(SCNCapsule(capRadius: build.limb * 1.1, height: build.legs), at: SCNVector3(side * build.stance * 0.5, build.legs / 2, 0))
    }
    figure.position = SCNVector3(0, -0.55, 0)
    // A three-quarter turn reads better as a still than square-on.
    figure.eulerAngles.y = -0.45
    scene.rootNode.addChildNode(figure)
    return scene
}

try? FileManager.default.createDirectory(at: output, withIntermediateDirectories: true)
let device = MTLCreateSystemDefaultDevice()
for (category, build) in builds {
    let scene = bundled(category) ?? placeholder(build)
    scene.background.contents = NSColor.clear
    // Metal reflects its surroundings; offscreen there are none, so give it a
    // soft grey studio the way the iOS SceneView's default lighting does.
    scene.lightingEnvironment.contents = NSColor(white: 0.3, alpha: 1)
    scene.lightingEnvironment.intensity = 0.7
    let camera = light(scene)
    let renderer = SCNRenderer(device: device, options: nil)
    renderer.scene = scene
    renderer.pointOfView = camera
    renderer.autoenablesDefaultLighting = false
    // 104 x 132 dp at xxxhdpi.
    let image = renderer.snapshot(atTime: 0, with: CGSize(width: 416, height: 528), antialiasingMode: .multisampling4X)
    guard let tiff = image.tiffRepresentation, let bitmap = NSBitmapImageRep(data: tiff),
          let png = bitmap.representation(using: .png, properties: [:]) else { fatalError("render failed: \(category)") }
    try png.write(to: output.appending(path: "character_\(category).png"))
    print("wrote character_\(category).png")
}
