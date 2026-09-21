# Training path characters

Three models, one per path. Drop them in **this folder** with these exact names
and they appear in the app — no code change, no Xcode project edit (the target
uses file-system synchronized groups, so new files are picked up automatically):

```
athlete.usdz        lean, capable; a mid-stride or coiled stance
bodybuilder.usdz    developed, defined; a classic physique pose
powerlifter.usdz    thick, stocky, planted; a lift or a wide stance
```

Until a file is here, the app shows a built-in placeholder of the right build.
It never blocks: a missing, broken or unreadable model falls back silently.

## Format

- **`.usdz`** (preferred) or `.scn`. Most stores sell `.fbx` / `.obj` / `.blend`;
  convert with Reality Converter (free, from Apple) — drag the file in, drag the
  `.usdz` out. `.glb`/`.gltf` also import there.
- **Under about 8 MB each.** Three of them load on the onboarding screen, which
  is the first thing a new user sees. Decimate if a sculpt is millions of
  polygons; at this size on screen, a few tens of thousands is plenty.
- Baked colour/material is fine. There is one key light and one fill; a model
  with no material shows grey, which suits the app.

## Framing

Don't worry about scale, origin or units. The app centres each model on its own
bounding box and scales it to fill the card, so a model that exports 100× too
big or off-centre still looks right. Standing upright and facing +Z gives the
best first frame — it turns slowly on its own and can be dragged.

## Licensing

Buy a licence that covers **use in an app**, not editorial-only, and keep the
receipt with the project. The references this was designed from are watermarked
stock (Shutterstock 2688105181; FOR3D.RU) — those exact files cannot be used
until licensed. Sources worth checking: Shutterstock 3D, TurboSquid, CGTrader,
Sketchfab (filter by licence).

## Checking one

Drop the file in, then:

```
cd ios
xcodebuild test -project MetalARM.xcodeproj -scheme MetalARM \
  -destination "platform=iOS Simulator,name=iPhone 17 Pro Max" \
  -only-testing:MetalARMTests/TrainingPathTests
```

`everyPathHasAPlaceholderCharacter` proves every path still renders something;
run the app and look at the onboarding screen to judge the art itself.
