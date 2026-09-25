# MetalArm — marketing site

The public page. Static export: no server, no auth, no database of its own.
The only request it makes at runtime is `POST /waitlist` to the MetalArm API.

```bash
npm install
npm run dev            # http://localhost:4000, against the local API
npm run build          # static export into out/
npx serve out -l 4000  # serve the built site
```

`NEXT_PUBLIC_API_URL` is baked in **at build time** (it defaults to
`http://localhost:8000/api/v1`). Point it at the deployed API before building
for production, and remember the API's `CORS_ORIGINS` must list wherever this
site is served from, or the waitlist form fails with what looks like the server
being down.

## Why this is a separate app

The web product (`../frontend`) is Reflex, which owns its own Node toolchain
and deliberately has no hand-written `package.json` — see the note at the top
of `frontend/requirements.txt`, which exists because the predecessor project
died on a host-generated lockfile. This site has different needs (GSAP
timelines, scroll-scrubbed video) and keeping it separate means it cannot drag
JavaScript tooling into that app. The cost is that brand tokens live in two
places: `app/globals.css` here copies `frontend/metalarm/theme.py`, and the
fonts match `ios/MetalARM`'s Theme. If you change one, change the other.

## The rules this page follows

- **Copy never depends on JavaScript.** The hidden state for every reveal is
  scoped to `html.ma-js`, a class the motion layer adds. If it never runs, the
  page is fully readable — a check in `scripts/e2e/marketing_site.mjs` loads it
  with JavaScript disabled and asserts exactly that.
- **`prefers-reduced-motion` skips the motion layer entirely** — no Lenis, no
  pins, no scrubbing. Not "animate, then shorten".
- **Pinned sections are desktop-only.** On a phone a pinned section fills the
  screen, so holding it still while content changes reads as a page that has
  frozen. They become ordinary stacked copy below 768px.
- **Every claim maps to something shipped.** No prestige, no trophy case, no
  natural-language logging — those are scoped, not built. The check asserts the
  page never says "Bronze" or "Diamond" either: MetalArm's tiers are Untrained
  through World Class.

## Media

`public/media/` holds clips cut from the recordings in
`~/Desktop/MetalArm Recordings/` (see `scripts/record_tour.sh` and
`scripts/e2e/rank_up_reel.mjs`). They are real captures of the app, scaled to
540px wide and CRF 30, which keeps the whole page under a megabyte of video.
Swapping in newer footage is a file replacement, not a code change.
