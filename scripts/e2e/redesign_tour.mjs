// The "what's new" film for the minimal redesign: drives the REAL app through
// the four tabs at phone size and a narrated pace, against a RUNNING stack
// seeded by scripts/demo/seed_fresh.sh.
//
//   node scripts/demo/render_assets.mjs A --narration scripts/demo/redesign.json
//   node redesign_tour.mjs <out-dir> A <email> <password>
//   python3 scripts/demo/build_demo.py --assets A --web-dir <out-dir> \
//     --narration scripts/demo/redesign.json --name metalarm-redesign --out O
//
// Writes <out-dir>/web-raw.webm and web-marks.json ({chapter: seconds}), the
// same contract as web_tour.mjs. Each chapter holds at least as long as its
// voice clip. Before recording it sets the stage through the API: the demo
// lifter follows two friends and has a fresh "Upper Day" routine with two
// supersets, and no workout is live.

import { mkdirSync, readFileSync, readdirSync, renameSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { chromium } from 'playwright-core';

const [OUT, ASSETS, EMAIL, PASSWORD] = process.argv.slice(2);
if (!PASSWORD) { console.error('usage: node redesign_tour.mjs <out> <assets> <email> <password>'); process.exit(2); }
const UI = process.env.METALARM_UI || 'http://localhost:3000';
const API = process.env.METALARM_API || 'http://localhost:8000/api/v1';
const durations = JSON.parse(readFileSync(join(ASSETS, 'durations.json'), 'utf8')).web;
mkdirSync(OUT, { recursive: true });
const raw = join(tmpdir(), `metalarm-redesign-${Date.now()}`);
mkdirSync(raw, { recursive: true });

async function api(path, method = 'GET', body, token) {
  const r = await fetch(API + path, {
    method,
    headers: { 'Content-Type': 'application/json', ...(token ? { Authorization: `Bearer ${token}` } : {}) },
    body: body ? JSON.stringify(body) : undefined,
  });
  const text = await r.text();
  return { status: r.status, body: text ? JSON.parse(text) : null };
}

// --- The stage -----------------------------------------------------------------
const token = (await api('/auth/login', 'POST', { email: EMAIL, password: PASSWORD })).body.access_token;
for (const name of ['Maya', 'Dev']) {
  const found = (await api(`/users/search?q=${name}`, 'GET', null, token)).body.items || [];
  const friend = found.find((u) => u.display_name === name);
  if (friend) await api(`/follows/${friend.id}`, 'POST', null, token);
}
const live = (await api('/workouts/sessions/active', 'GET', null, token)).body.session;
if (live) await api(`/workouts/sessions/${live.id}/abandon`, 'POST', null, token);
// One "Upper Day", freshly made: earlier films may have left copies behind.
const routines = (await api('/routines', 'GET', null, token)).body;
for (const r of (routines.items || routines)) {
  if (r.name === 'Upper Day') await api(`/routines/${r.id}`, 'DELETE', null, token);
}
const lookup = async (name) => (await api(`/exercises/browse?q=${encodeURIComponent(name)}&limit=10`, 'GET', null, token))
  .body.items.find((e) => e.name === name).id;
const benchId = await lookup('Barbell Bench Press');
const plan = [
  ['Barbell Bench Press', 3, 8, 60, 1], ['Barbell Row', 3, 10, 50, 1],
  ['Hammer Curl', 2, 12, 12, 2], ['Tricep Pushdown', 2, 12, 25, 2],
];
const exercises = [];
for (const [name, sets, reps, kg, group] of plan) {
  exercises.push({ exercise_id: await lookup(name), target_sets: sets, target_reps: reps, target_weight_kg: kg,
    rest_seconds: 90, superset_group: group });
}
await api('/routines', 'POST', { name: 'Upper Day', exercises }, token);
const mine = (await api('/me/exercises?limit=100', 'GET', null, token)).body.items;
const benchBest = (mine.find((e) => e.exercise_id === benchId) || {}).best_weight_kg || 60;

// --- Recording -------------------------------------------------------------------
const launch = process.env.CHROME_PATH
  ? { executablePath: process.env.CHROME_PATH, headless: true }
  : { channel: 'chrome', headless: true };
const browser = await chromium.launch(launch);
// A 430 x 932 phone, recorded at its own size: the film frames the app 960 px
// tall, so this lands almost 1:1. (Playwright's recorder never upscales, and
// zooming the page instead breaks clicks on fixed sheets.)
const VIEW = { width: 430, height: 932 };
const context = await browser.newContext({
  viewport: VIEW, isMobile: true, hasTouch: true, recordVideo: { dir: raw, size: VIEW },
});
const page = await context.newPage();
const t0 = Date.now();
const marks = {};
const missed = [];
const wait = (ms) => page.waitForTimeout(ms);

async function tap(locator, label) {
  try {
    await locator.first().scrollIntoViewIfNeeded({ timeout: 4000 });
    await locator.first().click({ timeout: 4000 });
    await wait(500);
    return true;
  } catch {
    missed.push(label);
    console.log(`    (missed: ${label})`);
    return false;
  }
}

async function clearOverlays() {
  const b = page.getByRole('button', { name: 'Continue', exact: true }).first();
  if (await b.isVisible().catch(() => false)) { await b.click().catch(() => {}); await wait(700); }
}

async function glide(y) {
  await page.evaluate((to) => window.scrollTo({ top: to, behavior: 'smooth' }), y);
  await wait(1000);
}

async function go(path) {
  await page.goto(UI + path);
  await page.waitForLoadState('networkidle').catch(() => {});
  await wait(1000);
}

async function chapter(id, body) {
  marks[id] = (Date.now() - t0) / 1000;
  console.log(`  ${id}`);
  const started = Date.now();
  await body();
  const left = (durations[id] + 0.7) * 1000 - (Date.now() - started);
  if (left > 0) await wait(left);
}

const cards = () => page.locator('.ma-card');
const logSet = async (label) => {
  await tap(page.getByRole('button', { name: 'Log set' }), label);
  await wait(1200);
  await clearOverlays();
};

try {
  await page.goto(`${UI}/login`);
  await page.locator('input').first().fill(EMAIL);
  await page.locator('input[type=password]').fill(PASSWORD);
  await page.getByRole('button', { name: 'Sign in' }).click();
  await page.waitForURL('**/home', { timeout: 30000 });
  await wait(1500);

  await chapter('intro', async () => { await wait(800); });

  // --- Home --------------------------------------------------------------------------
  await chapter('home', async () => { await glide(0); await wait(2500); await glide(260); });

  await chapter('feed', async () => {
    await glide(700);
    const card = page.locator('.ma-feed-card').filter({ hasText: 'Maya' }).first();
    await card.scrollIntoViewIfNeeded().catch(() => missed.push('friend in feed'));
    await wait(1200);
    await tap(card.getByRole('button', { name: 'Spotted' }), 'spot');
  });

  await chapter('leaderboard', async () => {
    await go('/leaderboard');
    await wait(1500);
    await tap(page.getByRole('button', { name: 'All time', exact: true }), 'all time');
    await wait(1200);
  });

  // --- Train -------------------------------------------------------------------------
  await chapter('train', async () => {
    await go('/train');
    await wait(1200);
    await glide(600);
    await glide(1300);
    await glide(0);
  });

  await chapter('exercises', async () => {
    await go('/library/exercises');
    await wait(800);
    await tap(page.getByRole('button', { name: 'Chest', exact: true }), 'chest');
    await wait(1000);
    await tap(page.getByRole('button', { name: 'Dumbbell', exact: true }), 'dumbbell');
    await wait(1200);
  });

  await chapter('routine', async () => {
    await go('/train');
    await tap(page.getByText('Upper Day').first(), 'open Upper Day');
    await page.waitForURL('**/train/routine/**', { timeout: 10000 }).catch(() => {});
    await wait(1800);
  });

  await chapter('active', async () => {
    await tap(page.getByRole('button', { name: 'Start routine' }), 'start routine');
    await cards().first().waitFor({ timeout: 15000 }).catch(() => missed.push('cards'));
    await wait(2200);
    await logSet('log bench set 1');
    await wait(1500);
  });

  await chapter('advance', async () => {
    // Focus moved to the row, the bench's superset partner.
    await wait(1200);
    await logSet('log row set 1');
    await wait(1200);
    await logSet('log bench set 2');
  });

  await chapter('options', async () => {
    await tap(cards().nth(1).getByRole('button', { name: 'Exercise options' }), 'options');
    await wait(1200);
    await page.getByRole('dialog').getByPlaceholder('Notes for this exercise')
      .pressSequentially('Pause at the chest', { delay: 60 }).catch(() => missed.push('notes'));
    await wait(1200);
    await tap(page.getByRole('dialog').getByRole('button', { name: 'Close' }), 'close options');
  });

  await chapter('pr', async () => {
    // The bench, at a weight it has never seen: the record.
    const bench = cards().first();
    if (!(await bench.locator('.ma-entry').count())) {
      await tap(bench.getByText(/^(Log next set|Start this exercise)$/), 'focus bench');
    }
    await glide(0);
    await bench.locator('.ma-entry input').first().fill(String(Math.round(benchBest + 5))).catch(() => missed.push('weight'));
    await wait(700);
    await tap(page.getByRole('button', { name: 'Log set' }), 'log PR set');
    await page.locator('.ma-pr-banner').waitFor({ timeout: 8000 }).catch(() => missed.push('PR banner'));
    await wait(2600);
    await clearOverlays();
  });

  await chapter('summary', async () => {
    await glide(0);
    await tap(page.getByRole('button', { name: 'Finish', exact: true }), 'finish');
    await wait(900);
    await tap(page.getByRole('button', { name: 'Finish workout' }), 'finish workout');
    await page.getByText('Workout complete').waitFor({ timeout: 15000 }).catch(() => missed.push('summary'));
    await wait(1200);
    await clearOverlays();
    await glide(450);
    await glide(1000);
    await glide(1500);
    await tap(page.getByRole('button', { name: 'Done', exact: true }), 'summary done');
  });

  // --- Progress ----------------------------------------------------------------------
  await chapter('progress', async () => {
    await go('/progress');
    await wait(1000);
    await tap(page.locator('.ma-focus-row'), 'chart sheet');
    await wait(1000);
    await tap(page.getByRole('dialog').getByText('Barbell Bench Press', { exact: true }), 'bench on the chart');
    await wait(1800);
    await glide(500);
  });

  await chapter('history', async () => {
    await go('/progress/history');
    await wait(1500);
    await glide(500);
  });

  // --- Profile -----------------------------------------------------------------------
  await chapter('profile', async () => {
    await go('/profile');
    await wait(1500);
    await glide(500);
    await glide(1100);
  });

  await chapter('game', async () => {
    await go('/quests');
    await wait(1600);
    await go('/parties');
    await wait(1600);
  });

  await chapter('motion', async () => {
    await go('/profile');
    const sw = page.getByRole('switch', { name: 'Reduce motion' });
    await sw.scrollIntoViewIfNeeded().catch(() => {});
    await wait(1000);
    await tap(sw, 'reduce motion on');
    await wait(2200);
    await tap(sw, 'reduce motion off');   // leave the demo browser as it was
  });

  await chapter('system', async () => {
    await go('/design-system');
    await wait(800);
    for (const y of [700, 1500, 2400, 3300]) await glide(y);
  });

  await chapter('end', async () => {
    await go('/home');
    await wait(1000);
  });
} finally {
  await context.close();
  await browser.close();
}

const webm = readdirSync(raw).find((f) => f.endsWith('.webm'));
if (!webm) { console.error('No video was recorded'); process.exit(1); }
renameSync(join(raw, webm), join(OUT, 'web-raw.webm'));
rmSync(raw, { recursive: true, force: true });
writeFileSync(join(OUT, 'web-marks.json'), JSON.stringify(marks, null, 1));
const expected = Object.keys(durations);
const absent = expected.filter((id) => !(id in marks));
console.log(`\nchapters: ${Object.keys(marks).length}/${expected.length}` + (absent.length ? `  MISSING: ${absent.join(', ')}` : ''));
if (missed.length) console.log(`missed controls: ${missed.join('; ')}`);
console.log(`wrote ${join(OUT, 'web-raw.webm')}`);
process.exit(absent.length ? 1 : 0);
