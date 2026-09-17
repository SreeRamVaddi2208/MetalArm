# Launch checklist

Everything in the code is ready. These are the steps only you can do, in
order. Replace `DOMAIN` with your domain throughout. Detail for steps 1 to 4 is
in [`deployment.md`](deployment.md).

## Web and API (about an hour)

1. **Domain and DNS.** Buy a domain. Create A records (and AAAA if the server
   has IPv6) for **both** `DOMAIN` and `api.DOMAIN`, pointing at the server.
   Do this first: HTTPS certificates are requested on the first start and fail
   if DNS isn't in place.
2. **Server.** A Linux server with Docker Engine and the Compose plugin
   (2 vCPU / 4 GB RAM is comfortable). Open inbound TCP 80 and 443, and UDP 443.
3. **Configuration.**

   ```bash
   git clone https://github.com/SreeRamVaddi2208/MetalArm.git metalarm && cd metalarm
   cp deploy/.env.production.example deploy/.env.production
   python3 -c "import secrets; print(secrets.token_urlsafe(48))"   # run once per secret
   ```

   In `deploy/.env.production`, replace every `CHANGE_ME`: `DOMAIN`,
   `ACME_EMAIL`, `SUPPORT_EMAIL` (shown on the privacy and support pages),
   `POSTGRES_PASSWORD`, `REDIS_PASSWORD` and `JWT_SECRET_KEY`. The file is
   gitignored; never commit it.
4. **Start and check.**

   ```bash
   docker compose -f deploy/docker-compose.prod.yml --env-file deploy/.env.production up -d --build
   curl -s https://api.DOMAIN/health       # "status": "ok"
   ```

   Then open `https://DOMAIN`, create an account, log a workout, and check
   that `https://DOMAIN/privacy` and `https://DOMAIN/support` show your
   support email.

## iPhone app (a few days, mostly Apple's waiting time)

5. **Apple Developer Program.** Enrol at developer.apple.com/programs
   ($99/year). Approval can take a day or two.
6. **Xcode settings.** Open `ios/MetalARM.xcodeproj`, select the **MetalARM**
   target:
   - **Signing & Capabilities:** choose your Team. Keep automatic signing.
   - **Build Settings → Release:** `METALARM_API_BASE_URL` is currently the
     placeholder `https://api.metalarm.example.com`; set it to
     `https://api.DOMAIN`. Set `METALARM_WEB_BASE_URL` (now
     `https://metalarm.example.com`) to `https://DOMAIN`. The in-app Privacy
     Policy link uses this address.
   - **Bundle identifier:** currently `com.SreeRam.MetalARM`. Keep it or change
     it now: it can't be changed after the first upload. Version is 1.0,
     build 1; raise the build number for every later upload.
7. **App Store Connect.** At appstoreconnect.apple.com, create a new app with
   that bundle identifier. Fill the listing from
   [`ios/AppStore/metadata.md`](../ios/AppStore/metadata.md), and upload the
   12 screenshots in `ios/AppStore/screenshots/`.
8. **Upload a build.** In Xcode, choose **Any iOS Device**, then
   **Product → Archive → Distribute App → App Store Connect**.
9. **TestFlight.** Install the build on your own iPhone through TestFlight and
   run through sign-up, a workout, the level-up celebration, and Delete Account
   against the live server.
10. **Demo account for App Review.** Sign up on the live server with an
    address you control, log a workout or two, and put the email and password
    in App Store Connect under **App Review Information**.
11. **Submit for review.** Add the build to the version and submit. Export
    compliance is already answered: `Info.plist` declares
    `ITSAppUsesNonExemptEncryption` = NO (the app only uses standard HTTPS), so
    App Store Connect won't ask. Keep the server running during review.

## After launch

- Backups run nightly (`deploy/backup.sh`, kept 14 days). Try one restore
  early so you know it works.
- Updating: `git pull`, then the same `docker compose ... up -d --build`.
  Migrations run automatically.

## Push notifications (after Apple Developer enrolment)

The iPhone app schedules LOCAL notifications on its own (rest timer done, and
"your streak ends tonight"); nothing below is needed for those. SERVER push -
a party member finishing a workout, a raid boss falling - needs:

- [ ] An **APNs auth key** (.p8) from the Apple Developer account, plus its Key
      ID and the Team ID.
- [ ] The **Push Notifications** capability on the app target, and
      `aps-environment` in `MetalARM.entitlements`.
- [ ] A backend device-token table and endpoint, so a device can register.
- [ ] Decide what is worth waking someone for. Party events only, and never a
      marketing message: the App Store treats that as a reason to reject.

## Apple Health (before the first upload)

- [ ] Review `NSHealthUpdateUsageDescription` in `ios/MetalARM/Info.plist`. App
      Review reads it, and it must say what is written and why.
- [ ] Confirm the HealthKit capability is on the App ID in the developer
      portal; the entitlement alone is not enough for a real device build.
- [ ] MetalArm asks to WRITE workouts only - never to read. Keep it that way
      unless a feature genuinely needs reading, because the ask gets harder.

