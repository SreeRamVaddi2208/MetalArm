# Putting MetalArm on Google Play

The Android app is the web app: a Trusted Web Activity (`android/`) that opens
it full-screen with no browser chrome. It installs from the browser already —
this is about being **found** in the Play Store, which a web app cannot be.

Everything here needs an account, a key or a domain, so it is yours to do. The
shell itself is written and waiting.

## 1. Before anything else

- [ ] A **Play Console account** — $25, one-off, at play.google.com/console
- [ ] The site **deployed over HTTPS** on a real domain (`docs/deployment.md`).
      A TWA cannot point at localhost, and Play will not accept one that does.
- [ ] A **release signing key**, kept out of the repo and backed up:
      ```bash
      keytool -genkey -v -keystore metalarm-release.jks \
        -keyalg RSA -keysize 2048 -validity 10000 -alias metalarm
      ```
      Lose this and you can never update the listing again.

## 2. Tie the app to the site

This is the step that decides whether the app opens clean or inside a browser
tab with an address bar.

- [ ] Build once and read the fingerprint:
      ```bash
      keytool -list -v -keystore metalarm-release.jks -alias metalarm | grep SHA256
      ```
- [ ] Put it in `frontend/assets/.well-known/assetlinks.json`, replacing the
      placeholder, and deploy the site.
- [ ] Set the host in `android/gradle.properties`, or pass
      `-PmetalarmHost=yourdomain` when building.
- [ ] Check it serves: `curl https://<domain>/.well-known/assetlinks.json`
- [ ] **If you use Play App Signing** — the default, and recommended — Google
      re-signs your upload with their own key, so the fingerprint that belongs
      in that file is the one shown under *Setup → App integrity*, **not** your
      local one. This catches nearly everyone the first time.

## 3. Build what Play wants

```bash
cd android && ./gradlew bundleRelease
# app/build/outputs/bundle/release/app-release.aab
```

## 4. The listing

- [ ] **Screenshots**, at least two phone shots. There are usable ones already:
      `~/Desktop/MetalArm Recordings/` has the tour and the rank-up reel, and
      `scripts/e2e` can produce fresh phone-width captures of any screen.
- [ ] **Feature graphic**, 1024×500.
- [ ] **Short description** (80 chars). The marketing site's hero line fits:
      *"The gym is the game."*
- [ ] **Full description** — the marketing site's sections are the copy, already
      checked against what is actually built.
- [ ] **Privacy policy URL** — the app serves one at `/privacy`.
- [ ] **Data safety form**: MetalArm collects an email address and the training
      you log. It does not collect location, contacts or advertising IDs, and
      nothing is sold or shared. Account deletion exists in-app (Profile →
      Delete Account), which Play asks about specifically.
- [ ] **Content rating** questionnaire — a fitness tracker rates as Everyone.

## 5. Before you press publish

- [ ] Install the signed APK on a real phone and confirm it opens **without**
      an address bar. If one appears, the asset-link check failed — go back to
      step 2; it is almost always the Play App Signing fingerprint.
- [ ] Turn on notifications in Profile and confirm one arrives while the app is
      closed.
- [ ] Log a set in aeroplane mode, then reconnect, and confirm it lands.
