# MetalArm for Google Play

A Trusted Web Activity: a thin Android shell that opens the MetalArm web app
full-screen, with no browser chrome, using the device's own Chrome. It is the
same app that installs from the browser — this exists so it can be **found and
installed from Play**, which a plain web app cannot be.

> **Not built here.** This machine has no JDK, no Android SDK and no Gradle,
> and Homebrew could not reach its formula API to install them, so the project
> below has never been compiled. It is written to be correct and to build with
> one command once the toolchain exists — treat the first `assembleRelease` as
> the real test of it.

## What you need, once

1. **Android Studio** (or the command-line tools) — provides the SDK and Gradle.
2. **A Google Play Console account** — $25, one-off, and only you can create it.
3. **A release signing key**:
   ```bash
   keytool -genkey -v -keystore metalarm-release.jks \
     -keyalg RSA -keysize 2048 -validity 10000 -alias metalarm
   ```
   Keep this file out of the repo and backed up. Losing it means never being
   able to update the app under the same listing.

## Build

```bash
cd android
./gradlew assembleRelease      # an APK, for sideloading and testing
./gradlew bundleRelease        # an .aab, which is what Play wants
```

## The part that is easy to get wrong

A TWA only opens without browser chrome if the site proves it owns the app.
That is **Digital Asset Links**: `frontend/assets/.well-known/assetlinks.json`
must carry the SHA-256 fingerprint of the key that signed the APK.

```bash
keytool -list -v -keystore metalarm-release.jks -alias metalarm | grep SHA256
```

Put that fingerprint in `assetlinks.json`, deploy the site, and only then
install the APK. Get it wrong and the app still works — but opens inside a
Chrome tab with an address bar, which rather defeats the point.

**If you use Play App Signing** (recommended, and the default), Google re-signs
your upload with *their* key. The fingerprint that must go in `assetlinks.json`
is then the one Play shows under *Setup → App integrity*, not your local one.
This catches almost everyone once.

## Submitting

See `docs/play-listing.md` for the store side: copy, screenshots, the privacy
policy URL, and the data-safety form.
