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

## What the page shows, and where it came from

Ten sections. Every claim maps to something merged; the browser check asserts
the page never says "Bronze" or "Diamond" (the tiers are Untrained through
World Class) and never mentions prestige or a trophy case, which are scoped
rather than built.

| Section | Media | Source |
|---|---|---|
| Hero | The PR banner firing, tilted | iOS tour, demo account |
| Not just a log | Dashboard -> live session -> summary, cross-fading | iOS tour |
| The moment it clicks | Rest timer, scrubbed by scroll | iOS tour |
| Training path | The three builds | iOS tour |
| Rank-up | All five promotions, scrubbed by scroll | Web app, live backend |
| Proof, not vibes | An SVG chart that draws itself, beside the real screen | iOS tour |
| Compete | League and raid | iOS tour |

The numbers counted up in the hero and the chart - 85 kg, 104.83 kg, 52 points -
are read off those captures, not invented. If the footage is replaced, check
them.

## Scrolling

Two things were tuned after "a bit of a scrolling issue", and both are now
checked rather than remembered:

- **Pinned sections are bounded.** A pin holds the page still while you scroll,
  so a long one feels like the site has stopped responding. They ran to 3.2
  viewports; they are now under 2.1, and the page went from 15.4 viewports to
  12.4.
- **Scrubbed video is encoded for seeking, not for playback.** Constant frame
  rate with a keyframe every 6 frames (`-r 24 -g 6 -keyint_min 6
  -sc_threshold 0`). With the default ~60-frame spacing, every seek decoded up
  to sixty frames and the first one into a section blocked the main thread for
  most of half a second. If you re-cut `rest-timer.mp4` or `rank-up.mp4`, keep
  those flags - they are the difference between scrubbing and stuttering.

**One element, one pin.** The morph screens ride the same timeline as the text
steps in that section. They used to have their own ScrollTrigger, which pinned
the same node a second time - two pins fighting over one element put the whole
card off-screen, and a viewport and a half scrolled past completely blank. The
check now walks the page and asserts something is on screen at every stop.

Lenis runs at `duration: 0.9` and leaves touch alone: a phone's own scrolling
is already better than anything layered over it.

## Media

`public/media/` holds clips cut from the recordings in
`~/Desktop/MetalArm Recordings/` (see `scripts/record_tour.sh` and
`scripts/e2e/rank_up_reel.mjs`). They are real captures of the app, scaled to
540px wide and CRF 30, which keeps the whole page under a megabyte of video.
Swapping in newer footage is a file replacement, not a code change.
