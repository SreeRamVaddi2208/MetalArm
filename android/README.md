# MetalArm for Android

A native Android app at parity with the iPhone app, on the same backend and
the same design system. It's written in Kotlin and Jetpack Compose, and runs on
Android 9 (API 28) and later.

**Every change ships to all three clients.** A feature or fix goes to the web
app, the iPhone app and this app in the same piece of work.

## Layout

| Path | What it is |
|---|---|
| `app/src/main/java/com/sreeram/metalarm/api/` | `MetalArmApi` (one to one with iOS `MetalArmAPI.swift`), `LiveApi` (OkHttp, token refresh), `MockApi` (in-memory backend), models, fixtures |
| `…/state/AppModel.kt` | App-wide state: the twin of iOS `AppModel.swift`, in Compose snapshot state |
| `…/state/Platform.kt` | Interfaces for settings, the offline set queue, notifications and Health Connect |
| `…/platform/` | Android implementations: Keystore tokens, alarms and notifications, Health Connect, connectivity |
| `…/theme/` | `Theme.kt`, the tokens (value for value with `theme.py` and `Theme.swift`), and `Components.kt`, the primitives |
| `…/ui/`, `…/ui/library/` | The screens, one per iOS view |
| `app/src/test/` | JVM unit tests: decoding, transport, `AppModel` flows, the Library, focus advance |
| `app/src/androidTest/` | Compose UI tests on the emulator, plus the opt-in live-backend test |

## Set up

You need JDK 21 and the Android SDK (platform 37, build-tools, emulator). On a
Mac:

```bash
brew install openjdk@21 && brew install --cask android-commandlinetools
export JAVA_HOME=/opt/homebrew/opt/openjdk@21
export ANDROID_HOME=/opt/homebrew/share/android-commandlinetools
sdkmanager "platform-tools" "platforms;android-37.0" "build-tools;37.0.0" "emulator" \
  "system-images;android-36;google_apis;arm64-v8a"
avdmanager create avd -n MetalArm_Pixel -k "system-images;android-36;google_apis;arm64-v8a" -d pixel_9
```

Android Studio works too: open `android/`.

## Run

Start the backend (see the root README), then:

```bash
./gradlew installDebug
```

The debug build talks to `http://10.0.2.2:8000`, which is the host's
localhost as seen from the emulator. The release build points at
`https://api.metalarm.example.com`, a placeholder; set the real domain in
`app/build.gradle.kts` before shipping.

## Test

```bash
./gradlew lint testDebugUnitTest assembleRelease   # lint, unit tests, release build
./gradlew connectedDebugAndroidTest                # UI tests on a running emulator
```

The UI tests run against `MockApi`: they set `AppGraph.testConfig`, the way
the iOS tests pass `-UITest*` launch arguments.

One more test drives the real backend end to end. It signs up a throwaway
account, picks a path, logs and finishes a workout, starts a Library workout,
and then deletes the account. Opt in with:

```bash
./gradlew connectedDebugAndroidTest \
  -Pandroid.testInstrumentationRunnerArguments.class=com.sreeram.metalarm.LiveBackendTest \
  -Pandroid.testInstrumentationRunnerArguments.live=1
```

The UI tests save screenshots on the device. To pull them, add
`-Pandroid.injected.androidTest.leaveApksInstalledAfterRun=true` to the run,
then:

```bash
adb pull /sdcard/Android/data/com.sreeram.metalarm/files/screenshots
```

CI runs all of this, except the live test, in `.github/workflows/android.yml`.
`scripts/check_client_tokens.py` keeps every screen on the design tokens.

## Path characters

The training-path cards show still renders of the iOS app's SceneKit figures.
They're saved in `app/src/main/res/drawable-nodpi/character_*.png` and made by:

```bash
swift scripts/render_characters.swift
```

Re-run it when the real models (`ios/MetalARM/Models/*.usdz`) are added.
