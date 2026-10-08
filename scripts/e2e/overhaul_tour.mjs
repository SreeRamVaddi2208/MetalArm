// The "what's new" film: drives the REAL app through every screen the
// Lyfta-competitive overhaul added or rebuilt (phases 0-5), at phone size and a
// narrated pace, against a RUNNING stack seeded by scripts/demo/seed_fresh.sh.
//
//   node scripts/demo/render_assets.mjs A --narration scripts/demo/overhaul.json
//   node overhaul_tour.mjs <out-dir> A <email> <password>
//   python3 scripts/demo/build_demo.py --assets A --web-dir <out-dir> \
//     --narration scripts/demo/overhaul.json --name metalarm-whats-new --out O
//
// Writes <out-dir>/web-raw.webm and web-marks.json ({chapter: seconds}), the
// same contract as web_tour.mjs. Each chapter holds at least as long as its
// voice clip. Before recording it sets the stage through the API: the demo
// lifter follows two friends (so the feed and leaderboard have people in
// them) and has an upper-body routine to start.

import { mkdirSync, readFileSync, readdirSync, renameSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { chromium } from 'playwright-core';

const [OUT, ASSETS, EMAIL, PASSWORD] = process.argv.slice(2);
if (!PASSWORD) { console.error('usage: node overhaul_tour.mjs <out> <assets> <email> <password>'); process.exit(2); }
const UI = process.env.METALARM_UI || 'http://localhost:3000';
const API = process.env.METALARM_API || 'http://localhost:8000/api/v1';
const durations = JSON.parse(readFileSync(join(ASSETS, 'durations.json'), 'utf8')).web;
mkdirSync(OUT, { recursive: true });
const raw = join(tmpdir(), `metalarm-overhaul-${Date.now()}`);
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
const lookup = async (name) => (await api(`/exercises/browse?q=${encodeURIComponent(name)}&limit=10`, 'GET', null, token))
  .body.items.find((e) => e.name === name).id;
const benchId = await lookup('Barbell Bench Press');
const plan = [
  ['Barbell Bench Press', 3, 8, 60, null], ['Barbell Row', 3, 10, 50, null],
  ['Hammer Curl', 2, 12, 12, 1], ['Tricep Pushdown', 2, 12, 25, 1],
];
const exercises = [];
for (const [name, sets, reps, kg, group] of plan) {
  exercises.push({ exercise_id: await lookup(name), target_sets: sets, target_reps: reps, target_weight_kg: kg,
    rest_seconds: 90, superset_group: group });
}
await api('/routines', 'POST', { name: 'Upper Day', exercises }, token);
const mine = (await api('/me/exercises?limit=100', 'GET', null, token)).body.items;
const benchBest = (mine.find((e) => e.exercise_id === benchId) || {}).best_weight_kg || 60;
const lastMonth = (await api('/analytics/monthly-summary/latest', 'GET', null, token)).body.month;

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
  for (const label of ['Continue']) {
    const b = page.getByRole('button', { name: label, exact: true }).first();
    if (await b.isVisible().catch(() => false)) { await b.click().catch(() => {}); await wait(700); }
  }
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

try {
  await page.goto(`${UI}/login`);
  await page.locator('input').first().fill(EMAIL);
  await page.locator('input[type=password]').fill(PASSWORD);
  await page.getByRole('button', { name: 'Sign in' }).click();
  await page.waitForURL('**/home', { timeout: 30000 });
  await wait(1500);

  await chapter('intro', async () => { await wait(800); });

  await chapter('home', async () => { await glide(0); await wait(1500); await glide(420); });

  await chapter('feed', async () => {
    const card = page.locator('.ma-feed-card').filter({ hasText: 'Maya' }).first();
    await card.scrollIntoViewIfNeeded().catch(() => missed.push('friend in feed'));
    await wait(1200);
    await tap(card.getByRole('button', { name: 'Spotted' }), 'spot');
  });

  await chapter('leaderboard', async () => {
    await go('/leaderboard');
    await wait(1200);
    await glide(500);
  });

  await chapter('quests', async () => {
    await go('/quests');
    await wait(1200);
    await glide(700);
    await glide(1400);
  });

  await chapter('workout_tab', async () => {
    await go('/train');
    await wait(800);
    await glide(500);
  });

  await chapter('recovery', async () => {
    await go('/progress/recovery');
    await wait(3000);
  });

  await chapter('explore', async () => {
    await go('/library/exercises');
    await glide(600);
    await glide(1300);
    await glide(0);
  });

  await chapter('filter', async () => {
    await tap(page.getByRole('button', { name: 'Chest', exact: true }), 'chest');
    await wait(1200);
    await tap(page.getByRole('button', { name: 'Dumbbell', exact: true }), 'dumbbell');
    await wait(1500);
  });

  await chapter('exercise', async () => {
    await tap(page.locator('a[href^="/exercise/"]'), 'open exercise');
    await page.waitForURL('**/exercise/**', { timeout: 10000 }).catch(() => {});
    await wait(1200);
    await glide(500);
    await tap(page.getByRole('button', { name: 'Charts', exact: true }), 'charts');
    await wait(1500);
    await tap(page.getByRole('button', { name: 'Records', exact: true }), 'records');
    await wait(1200);
  });

  await chapter('programs', async () => {
    await go('/train');
    await wait(800);
    await tap(page.getByText('Upper / Lower Builder', { exact: true }), 'open program');
    await wait(1500);
    await tap(page.getByRole('button', { name: 'Save to library' }), 'save program');
    await wait(1500);
  });

  await chapter('library', async () => {
    // Saving opened your copy: its routines, each one tap from its detail.
    await wait(1200);
    await tap(page.getByText('Upper A', { exact: true }), 'open routine');
    await wait(1200);
    await glide(700);
  });

  const card = () => page.locator('.ma-card').first();
  await chapter('active', async () => {
    await go('/train');
    await tap(page.getByText('Upper Day').first(), 'open Upper Day');
    await tap(page.getByRole('button', { name: 'Start routine' }), 'start routine');
    await page.waitForURL(/\/train\/?$/, { timeout: 15000 }).catch(() => {});
    await card().waitFor({ timeout: 15000 }).catch(() => missed.push('cards'));
    await wait(800);
    await tap(card().getByRole('button', { name: 'Set type' }), 'warm-up badge');
    await tap(card().getByRole('button', { name: 'Log set' }), 'log warm-up');
    await wait(900);
    await clearOverlays();
    await tap(card().getByRole('button', { name: 'Log set' }), 'log set');
    await wait(900);
    await clearOverlays();
  });

  await chapter('picker', async () => {
    await tap(page.getByRole('button', { name: 'Add exercise' }), 'add exercise');
    await page.getByPlaceholder('Search exercises…').fill('curl').catch(() => missed.push('picker search'));
    await wait(1200);
    await tap(page.getByRole('checkbox', { name: 'EZ-Bar Curl', exact: true }), 'pick EZ-bar curl');
    await tap(page.getByRole('checkbox', { name: 'Cable Curl', exact: true }), 'pick cable curl');
    await wait(800);
    await tap(page.getByRole('button', { name: /^Add \d+ exercise/ }), 'add picked');
    await wait(1200);
  });

  await chapter('pr', async () => {
    await glide(0);
    await card().locator('.ma-entry input').first().fill(String(Math.round(benchBest + 5))).catch(() => missed.push('weight'));
    await wait(600);
    await tap(card().getByRole('button', { name: 'Log set' }), 'log PR set');
    await page.locator('.ma-pr-banner').waitFor({ timeout: 8000 }).catch(() => missed.push('PR banner'));
    await wait(4200);
    await clearOverlays();
  });

  await chapter('summary', async () => {
    await glide(0);
    await tap(page.getByRole('button', { name: 'Finish', exact: true }), 'finish');
    await tap(page.getByRole('button', { name: 'Finish workout' }), 'finish workout');
    await page.getByText('Workout complete').waitFor({ timeout: 15000 }).catch(() => missed.push('summary'));
    await wait(1500);
    await clearOverlays();
    await glide(500);
    await glide(1100);
    await tap(page.getByRole('button', { name: 'Public', exact: true }), 'visibility');
    await wait(1000);
    // Done closes the summary; the Train tab would keep showing it otherwise.
    await tap(page.getByRole('button', { name: 'Done', exact: true }), 'summary done');
  });

  await chapter('you', async () => {
    await go('/progress');
    await tap(page.getByRole('button', { name: 'Workouts', exact: true }), 'metric chip');
    await wait(1200);
    await tap(page.getByRole('button', { name: '6M', exact: true }), 'range');
    await wait(1200);
    await glide(700);
    await glide(1300);
  });

  await chapter('people', async () => {
    await go('/profile/people');
    await wait(1500);   // the page's own load resets the box: type after it
    await page.getByPlaceholder('Search people by name').fill('Sam').catch(() => missed.push('people search'));
    await page.locator('.ma-person').filter({ hasText: 'Sam' }).first().waitFor({ timeout: 8000 })
      .catch(() => missed.push('Sam found'));
    await wait(800);
    await tap(page.locator('.ma-person').filter({ hasText: 'Sam' }).getByRole('button', { name: 'Follow', exact: true }), 'follow Sam');
    await wait(1200);
  });

  await chapter('notifications', async () => {
    await go('/notifications');
    await wait(1500);
    await glide(400);
  });

  await chapter('monthly', async () => {
    await go(`/summary/${lastMonth}`);
    await page.locator('.ma-slide').waitFor({ timeout: 15000 }).catch(() => missed.push('summary story'));
    const per = Math.max(1500, ((durations.monthly + 0.7) * 1000 - 2000) / 7);
    for (let i = 0; i < 6; i++) {
      await wait(per);
      await page.locator('.ma-next').click({ position: { x: 150, y: 120 } }).catch(() => missed.push(`slide ${i + 2}`));
    }
    await wait(per);
  });

  await chapter('offline', async () => {
    await api('/workouts/sessions', 'POST', { name: 'Gym basement' }, token).then(async (r) => {
      if (r.status === 201) {
        await api(`/workouts/sessions/${r.body.id}/exercises`, 'POST', { exercise_id: benchId }, token);
      }
    });
    await go('/train');
    await card().waitFor({ timeout: 15000 }).catch(() => missed.push('offline card'));
    await card().locator('.ma-entry input').first().fill('60').catch(() => {});
    await card().locator('.ma-entry input').nth(1).fill('8').catch(() => {});
    await wait(1200);
    await context.setOffline(true);
    await wait(1200);
    await tap(card().getByRole('button', { name: 'Log set' }), 'offline set 1');
    await tap(card().getByRole('button', { name: 'Log set' }), 'offline set 2');
    await wait(2500);
    await context.setOffline(false);
    await card().getByRole('button', { name: 'Edit set' }).nth(1).waitFor({ timeout: 20000 })
      .catch(() => missed.push('queued sets arrive'));
    await wait(1500);
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
