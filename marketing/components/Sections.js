/**
 * The page's sections.
 *
 * Every claim here maps to something that is BUILT and merged, not scoped:
 * points on every set and the PR bonus (points_engine.py), ranks that can be
 * lost (leveling.rank_for, streak-gated at the top two), the training path
 * (training_categories.py), ready-made workouts, parties, weekly leagues with
 * promotion and relegation, party raids, duels and the activity feed
 * (app/core/duels.py, merged today), and next-set suggestions
 * (progression_hints.py). Nothing here promises prestige, avatar evolution,
 * a trophy case or natural-language logging - those are scoped, not shipped.
 */

import Chart from './Chart';
import Device, { Loop, Scrubbed } from './Device';
import Words from './Words';
import Waitlist from './Waitlist';

/** A number the app actually produced, counted up as it scrolls in. */
function Stat({ value, unit, label }) {
  return (
    <div>
      <p className="font-display text-4xl leading-none">
        {/* The real value is the TEXT, not the animation's endpoint: with no
            JavaScript, or under reduced motion, this has to read correctly.
            Motion.js zeroes it at the moment it starts counting. */}
        <span data-count-to={String(value)}>{value}</span>
        <span className="ml-1 text-lg text-muted">{unit}</span>
      </p>
      <p className="mt-2 text-sm text-faint">{label}</p>
    </div>
  );
}

export function Hero() {
  return (
    <section className="relative flex min-h-[92vh] flex-col items-center justify-center overflow-hidden px-6 pt-24 text-center">
      {/* The glow behind the hero drifts slower than the page. One of two
          parallax uses on the whole site; heavy motion is for the rank-up. */}
      <div
        data-parallax="18"
        aria-hidden="true"
        className="pointer-events-none absolute left-1/2 top-1/3 h-[38rem] w-[38rem] -translate-x-1/2
                   rounded-full bg-gold/10 blur-[120px]"
      />
      <p className="relative font-display text-xs tracking-[0.36em] text-gold">METALARM</p>
      <h1 className="relative mt-6 max-w-4xl font-display text-5xl leading-[1.05] sm:text-7xl">
        <Words text="The gym is the game." />
      </h1>
      <p className="relative mt-6 max-w-xl text-lg text-muted ma-rise">
        Not a tracker with a leaderboard bolted on. Every set you log is scored,
        every rank is one you can lose, and the workout is the thing that moves you.
      </p>
      <div className="relative mt-10 ma-rise">
        <Waitlist source="hero" />
      </div>
      <div className="relative mt-16 w-full max-w-[17rem] ma-rise">
        {/* The record, as it fires. The most concrete "this is real software"
            second the app has, so it is the first thing anyone sees - the
            five-tier rank-up gets its own section further down. */}
        <Device tilt>
          <Loop src="/media/pr-burst.mp4" poster="/media/pr-burst-poster.jpg" />
        </Device>
        <p className="mt-4 text-sm text-faint">A record, the moment it lands.</p>
      </div>
      {/* Real numbers from that session's summary screen, counted up. */}
      <div className="relative mt-14 grid w-full max-w-lg grid-cols-3 gap-6 text-center ma-rise">
        <Stat value={85} unit="kg" label="Top set, bench" />
        <Stat value={104.83} unit="kg" label="Estimated 1RM" />
        <Stat value={52} unit="pts" label="From that session" />
      </div>
    </section>
  );
}

export function NotJustALog() {
  const steps = [
    {
      title: 'You log a set.',
      body: 'Eighty kilos for eight. In a tracker, that is a row in a table and the end of it.',
    },
    {
      title: 'MetalArm scores it.',
      body: 'Points land on the set itself, weighted by how hard it was - and again when it beats your best.',
    },
    {
      title: 'It tells you what to try next.',
      body: 'Double progression, with a plateau backing you off and a hard month earning a deload.',
    },
    {
      title: 'And it says something.',
      body: '"That rep looked easy. It wasn\'t." A record is a moment, not a green cell in a spreadsheet.',
    },
  ];
  return (
    <section data-pin="" data-morph="" className="ma-pin-wrap relative h-[210vh] px-6">
      <div className="ma-pin flex h-screen items-center justify-center">
        <div className="mx-auto grid w-full max-w-5xl items-center gap-12 md:grid-cols-2">
          <div className="order-2 md:order-1">
            <p className="font-display text-xs tracking-[0.3em] text-gold">NOT JUST A LOG</p>
            {/* On desktop the steps are stacked in one box and swapped by the
                pinned timeline. On a phone there is no timeline - the pin is
                dropped - so they simply follow one another down the page, and
                the hidden state lives in CSS that only applies where the
                animation actually runs. Setting it inline here left three of
                the four invisible on a phone. */}
            <div className="mt-6 space-y-10 md:relative md:h-56 md:space-y-0">
              {steps.map((step) => (
                <div
                  key={step.title}
                  data-step=""
                  className="md:absolute md:inset-0"
                >
                  <h3 className="font-display text-3xl sm:text-4xl">{step.title}</h3>
                  <p className="mt-4 max-w-md text-lg text-muted">{step.body}</p>
                </div>
              ))}
            </div>
          </div>
          {/* The app's real navigation order - dashboard, the live session,
              the summary - cross-fading as the section advances, so the
              sequence reads as the product rather than a highlight reel. */}
          <div className="order-1 mx-auto w-full max-w-[15rem] md:order-2">
            <div className="relative space-y-6 md:space-y-0">
              {[
                ['continuity', 'The dashboard'],
                ['logging-a-set', 'A live session'],
                ['summary', 'The summary'],
              ].map(([name, caption], i) => (
                <div key={name} data-screen="" className={i === 0 ? 'md:relative' : 'md:absolute md:inset-0'}>
                  <Device>
                    <Loop src={`/media/${name}.mp4`} poster={`/media/${name}-poster.jpg`} />
                  </Device>
                  <p className="mt-3 text-center text-xs text-faint md:hidden">{caption}</p>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}

export function TrainingIdentity() {
  const paths = [
    { name: 'Athletic', detail: '12-20 reps · light · short rests' },
    { name: 'Bodybuilder', detail: '8-15 reps · moderate-heavy · moderate rests' },
    { name: 'Powerlifter', detail: '1-6 reps · heavy · long rests' },
  ];
  return (
    <section className="px-6 py-32">
      <div className="mx-auto max-w-5xl">
        <h2 className="max-w-2xl font-display text-4xl leading-tight sm:text-5xl">
          <Words text="Pick how you train. Once." />
        </h2>
        <p className="mt-5 max-w-xl text-lg text-muted ma-rise">
          Asked once, right after you sign up, and changeable any time from your profile.
          It sets the reps, the loads and the rest the app suggests - and the workouts it leads with.
          It never touches your points or your rank.
        </p>
        <div className="mt-14 grid items-center gap-10 md:grid-cols-2">
          <div className="mx-auto w-full max-w-[15rem] ma-rise">
            <Device>
              <Loop src="/media/training-path.mp4" poster="/media/training-path-poster.jpg" className="w-full" />
            </Device>
          </div>
          <ul className="space-y-4">
            {paths.map((path) => (
              <li key={path.name} className="rounded-2xl border border-border bg-panel p-5 ma-rise">
                <p className="font-display text-xl">{path.name}</p>
                <p className="mt-1 text-sm text-muted">{path.detail}</p>
              </li>
            ))}
          </ul>
        </div>
      </div>
    </section>
  );
}

export function TheMoment() {
  return (
    <section data-scrub-video="" className="ma-pin-wrap relative h-[170vh]">
      <div className="ma-pin flex h-screen items-center px-6">
        <div className="mx-auto grid w-full max-w-5xl items-center gap-12 md:grid-cols-2">
          <div>
            <p className="font-display text-xs tracking-[0.3em] text-gold">THE MOMENT IT CLICKS</p>
            <h2 className="mt-5 font-display text-4xl leading-tight sm:text-5xl" data-mask-reveal="">
              Ninety seconds, counting.
            </h2>
            <p className="mt-5 max-w-md text-lg text-muted">
              The rest timer runs while you sit there, because the rest is part of
              the set. It knows how long this movement wants - four minutes under a
              heavy bar, sixty seconds on a carry - from the workout you picked.
            </p>
            <p className="mt-4 max-w-md text-muted">
              Scroll to watch it run.
            </p>
          </div>
          <div className="mx-auto w-full max-w-[15rem]">
            <Device>
              <Scrubbed src="/media/rest-timer.mp4" poster="/media/rest-timer-poster.jpg" />
            </Device>
          </div>
        </div>
      </div>
    </section>
  );
}

export function ProgressDraws() {
  return (
    <section className="px-6 py-32">
      <div className="mx-auto max-w-5xl">
        <h2 className="max-w-2xl font-display text-4xl leading-tight sm:text-5xl">
          <Words text="Proof, not vibes." />
        </h2>
        <p className="mt-5 max-w-xl text-lg text-muted ma-rise">
          Every set you log goes into the record. Heaviest, best estimated one-rep
          max, most reps - per movement, with the date you did it.
        </p>
        <div className="mt-12 grid items-center gap-10 md:grid-cols-2">
          <div className="ma-rise">
            <Chart />
          </div>
          <div className="mx-auto w-full max-w-[15rem] ma-rise">
            <Device tilt>
              <Loop src="/media/progress-chart.mp4" poster="/media/progress-chart-poster.jpg" />
            </Device>
          </div>
        </div>
        <p className="mt-6 text-xs text-faint">
          Chart and records as the app draws them, from its demo account's bench
          press. Real software, real numbers, a made-up lifter.
        </p>
      </div>
    </section>
  );
}

export function RankUp() {
  return (
    <section data-scrub-video="" className="ma-pin-wrap relative h-[200vh]">
      <div className="ma-pin flex h-screen flex-col items-center justify-center px-6">
        <h2 className="max-w-3xl text-center font-display text-4xl leading-tight sm:text-5xl">
          <Words text="Six tiers. The last one takes years." />
        </h2>
        <p className="mt-4 max-w-lg text-center text-muted ma-rise">
          Untrained, Novice, Intermediate, Advanced, Elite, World Class. Each promotion
          is louder than the last - and the top two are held by your streak, so they can
          be lost as well as won.
        </p>
        <div className="mt-10 w-full max-w-[15rem]">
          <Device>
            <video
              src="/media/rank-up.mp4"
              poster="/media/rank-up-poster.jpg"
              muted
              playsInline
              preload="auto"
              className="w-full"
            />
          </Device>
        </div>
        <p className="mt-5 text-sm text-faint">Scroll to play.</p>
      </div>
    </section>
  );
}

export function Compete() {
  const items = [
    { title: 'Parties', body: 'Up to ten lifters, a shared quest board, and a leaderboard of what each of you contributed.' },
    { title: 'Duels', body: 'Head to head over a window you choose - volume, sets or sessions. No one to challenge? Your rival is paced from your own recent weeks.' },
    { title: 'The feed', body: "Your party's records, rank-ups, finished sessions and duel wins, as they happen." },
    { title: 'Weekly leagues', body: 'Twenty lifters, one week, promotion and relegation. Standings are summed from the ledger, so they cannot drift.' },
    { title: 'Raids', body: 'A weekly boss with health scaled to your party. Every qualified workout lands a hit; idle days heal it.' },
  ];
  return (
    <section className="px-6 py-32">
      <div className="mx-auto max-w-5xl">
        <h2 className="max-w-2xl font-display text-4xl leading-tight sm:text-5xl">
          <Words text="Nobody trains harder alone." />
        </h2>
        <div className="mt-14 grid gap-10 md:grid-cols-[1fr_15rem]">
          <ul className="grid gap-4 sm:grid-cols-2">
            {items.map((item) => (
              <li key={item.title} className="rounded-2xl border border-border bg-panel p-6 ma-rise">
                <p className="font-display text-xl">{item.title}</p>
                <p className="mt-2 text-sm leading-relaxed text-muted">{item.body}</p>
              </li>
            ))}
          </ul>
          <div className="mx-auto w-full max-w-[15rem] ma-rise">
            <Device>
              <Loop src="/media/social.mp4" poster="/media/social-poster.jpg" className="w-full" />
            </Device>
          </div>
        </div>
      </div>
    </section>
  );
}

export function Rival() {
  return (
    <section className="relative overflow-hidden px-6 py-32">
      <div
        data-parallax="-12"
        aria-hidden="true"
        className="pointer-events-none absolute right-[-10%] top-0 h-[26rem] w-[26rem] rounded-full bg-ruby/10 blur-[120px]"
      />
      <div className="relative mx-auto max-w-3xl text-center">
        <h2 className="font-display text-4xl leading-tight sm:text-5xl">
          <Words text="Your rival never skips a session." />
        </h2>
        <p className="mt-6 text-lg text-muted ma-rise">
          Challenge it when there is nobody else to challenge. Its pace comes from
          your own recent weeks - never another lifter's data - stretched just far
          enough to be worth beating.
        </p>
        <p className="mt-4 text-sm text-faint ma-rise">
          And after every set, the app tells you what to try next: add a rep, add
          the smallest jump you can load, or back off, depending on what your last
          few sessions actually did.
        </p>
      </div>
    </section>
  );
}

export function Comparison() {
  const rows = [
    ['Logging sets, history, personal records', true, true],
    ['Points on every set, weighted by effort', true, false],
    ['A rank you can lose if you stop', true, false],
    ['Head-to-head duels, in the app', true, false],
    ['A party board, weekly league and raid', true, false],
    ['A plan that follows how you train', true, false],
  ];
  return (
    <section className="px-6 py-24">
      <div className="mx-auto max-w-3xl">
        <h2 className="font-display text-3xl sm:text-4xl">
          <Words text="What makes it different" />
        </h2>
        <table className="mt-10 w-full border-collapse text-left">
          <thead>
            <tr className="border-b border-border text-xs tracking-[0.2em] text-faint">
              <th className="py-3 font-normal" scope="col"> </th>
              <th className="w-24 py-3 text-center font-normal" scope="col">METALARM</th>
              <th className="w-28 py-3 text-center font-normal" scope="col">A TRACKER</th>
            </tr>
          </thead>
          <tbody>
            {rows.map(([label, ours, theirs]) => (
              <tr key={label} className="border-b border-border/60 ma-rise">
                <td className="py-4 pr-4 text-sm text-text sm:text-base">{label}</td>
                <td className="py-4 text-center text-accent">{ours ? '●' : '–'}</td>
                <td className="py-4 text-center text-faint">{theirs ? '●' : '–'}</td>
              </tr>
            ))}
          </tbody>
        </table>
        <p className="mt-6 text-xs text-faint">
          "A tracker" means the common feature set of a plain logging app, not any
          particular product. Every row on the MetalArm side is shipped today.
        </p>
      </div>
    </section>
  );
}

export function Cta() {
  return (
    <section className="px-6 py-32">
      <div className="mx-auto flex max-w-3xl flex-col items-center text-center">
        <h2 className="font-display text-4xl leading-tight sm:text-5xl">
          <Words text="Start at Untrained." />
        </h2>
        <p className="mt-5 max-w-lg text-lg text-muted ma-rise">
          MetalArm is in build. Leave your address and you will hear from us when
          the app is ready - nothing else, ever.
        </p>
        <div className="mt-10 flex justify-center ma-rise">
          <Waitlist source="footer" />
        </div>
      </div>
      <footer className="mx-auto mt-24 max-w-5xl border-t border-border pt-8 text-center text-xs text-faint">
        <p className="mx-auto max-w-xl">
          Every screen on this page is a capture of MetalArm itself - the iPhone
          app on its demo account, and the web app on a live one. Nothing here is
          a mock-up, and nothing is a feature that has not been built.
        </p>
        <p className="mt-4">MetalArm - built by Sree Ram.</p>
      </footer>
    </section>
  );
}
