// Browser end-to-end test for MetalArm, against a RUNNING compose stack.
//
// Drives the real UI in the locally installed Chrome (headless, via
// playwright-core - no browser download) at phone width, then sweeps the
// main pages at phone and desktop width, and the old URLs' redirects.
//
//   docker compose up -d
//   cd scripts/e2e && npm install && node workout_e2e.mjs [screenshot-dir]
//
// CHROME_PATH=/path/to/chrome overrides the browser. Screenshots default to
// <tmp>/metalarm-e2e. Exits non-zero on any failed check.
//
// Complements scripts/smoke_test.py (HTTP only) and the pytest suite: this is
// the only test that exercises Reflex's websocket events, hydration, and the
// client-side scripts.

import { mkdirSync, readFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { chromium } from 'playwright-core';

const API = process.env.METALARM_API || 'http://localhost:8000/api/v1';
const UI = process.env.METALARM_UI || 'http://localhost:3000';
const OUT = process.argv[2] || join(tmpdir(), 'metalarm-e2e');
mkdirSync(OUT, { recursive: true });

const email = `e2e-${Date.now()}@metalarm.dev`;
const password = 'e2e-test-passphrase';

let passed = 0;
const failed = [];
function check(label, ok, detail = '') {
  if (ok) { passed++; console.log('  PASS', label); }
  else { failed.push(label); console.log('  FAIL', label, detail); }
}
function section(name) { console.log(`\n${name}`); }

async function api(path, method = 'GET', body, token) {
  const r = await fetch(API + path, {
    method,
    headers: { 'Content-Type': 'application/json', ...(token ? { Authorization: `Bearer ${token}` } : {}) },
    body: body ? JSON.stringify(body) : undefined,
  });
  const text = await r.text();
  return { status: r.status, body: text ? JSON.parse(text) : null };
}
const visible = (locator) => locator.isVisible().catch(() => false);

async function signIn(page) {
  await page.goto(UI + '/login');
  await page.locator('input').first().fill(email);
  await page.locator('input[type=password]').fill(password);
  await page.getByRole('button', { name: 'Sign in' }).click();
  await page.waitForURL('**/home', { timeout: 20000 });
}

const ok = (promise) => promise.then(() => true).catch(() => false);

async function addExercise(page, name) {
  await page.getByRole('button', { name: /^Add exercises?$/ }).click();
  await page.getByPlaceholder('Search exercises…').fill(name);
  await page.getByRole('checkbox', { name }).first().click();
  await page.getByRole('button', { name: /^Add \d+ exercise/ }).click();
}

async function discardWorkout(page) {
  await page.getByRole('button', { name: 'Finish', exact: true }).click();
  await page.getByRole('button', { name: 'Discard workout' }).click();
  await page.getByText('Discard this workout?').waitFor({ timeout: 15000 });
  await page.getByRole('button', { name: 'Discard', exact: true }).click();
  await page.getByRole('button', { name: 'Start empty workout' }).waitFor({ timeout: 15000 });
}

const launchOptions = process.env.CHROME_PATH
  ? { executablePath: process.env.CHROME_PATH, headless: true }
  : { channel: 'chrome', headless: true };
const browser = await chromium.launch(launchOptions);

try {
  const signup = await api('/auth/signup', 'POST', { email, password, display_name: 'E2E Lifter', timezone: 'UTC' });
  check('signup via API', signup.status === 201, JSON.stringify(signup.body));
  const token = (await api('/auth/login', 'POST', { email, password })).body.access_token;

  const ctx = await browser.newContext({ viewport: { width: 390, height: 860 }, deviceScaleFactor: 2 });
  const page = await ctx.newPage();
  const pageErrors = [];
  page.on('pageerror', (e) => pageErrors.push(String(e)));

  // ---------------------------------------------------------------------
  section('Workout: logging loop');
  await signIn(page);
  check('signed in through the form', page.url().endsWith('/home'));

  await page.goto(UI + '/train');
  await page.getByRole('button', { name: 'Start empty workout' }).click();
  await page.getByRole('button', { name: 'Add exercise' }).waitFor({ timeout: 15000 });
  check('blank workout started', true);
  check('a blank workout is named by time of day',
    await visible(page.getByText(/(Morning|Afternoon|Evening|Late-night) workout/).first()));

  await addExercise(page, 'Barbell Bench Press');
  check('exercise added from the picker',
    await ok(page.getByText('First time - this sets your baseline').waitFor({ timeout: 15000 })));

  const bench = page.locator('.ma-card').first();
  const fields = bench.locator('.ma-entry input');
  const logged = () => bench.getByRole('button', { name: 'Edit set' }).count();
  async function logSet(weight, reps) {
    const before = await logged();
    if (weight !== undefined) await fields.nth(0).fill(String(weight));
    if (reps !== undefined) await fields.nth(1).fill(String(reps));
    await bench.getByRole('button', { name: 'Log set' }).click();
    await bench.getByRole('button', { name: 'Edit set' }).nth(before).waitFor({ timeout: 15000 });
  }
  async function dismissLevelUp() {
    const cont = page.getByRole('button', { name: 'Continue' });
    if (await ok(cont.waitFor({ timeout: 3000 }))) {
      await page.waitForTimeout(700);
      return cont.click().then(() => true);
    }
    return false;
  }
  await logSet(60, 5);
  check('set logged and rendered', (await logged()) === 1);
  check('a first-ever set is a baseline, not a PR', !(await visible(page.locator('.ma-pr-banner'))));
  await dismissLevelUp();
  await page.waitForTimeout(400);
  check('rest timer started (client-side)', (await page.locator('#ma-rest[data-ma-state="on"]').count()) === 1);
  check('entry pre-filled for the next set', (await fields.nth(0).inputValue()) === '60');
  await page.screenshot({ path: `${OUT}/01-first-set.png` });

  await fields.nth(0).fill('65');
  await bench.getByRole('button', { name: 'Log set' }).click();
  const banner = page.locator('.ma-pr-banner');
  check('a heavier set shows the PR banner - not a takeover', await ok(banner.waitFor({ timeout: 15000 })));
  check('the banner names the lift', await visible(banner.getByText(/New PR · Barbell Bench Press/)));
  check('the PR bonus is the API\'s', await visible(banner.getByText(/^\+\d+ pts$/)));
  await page.screenshot({ path: `${OUT}/02-pr-banner.png` });
  check('the record carries a PR pill in its row', await visible(bench.getByText('PR', { exact: true }).first()));
  if (await dismissLevelUp()) await page.screenshot({ path: `${OUT}/03-level-up.png` });

  // ---------------------------------------------------------------------
  section('Workout: editing and deleting');
  await bench.getByRole('button', { name: 'Edit set' }).first().click();
  const sheet = page.getByRole('dialog');
  await sheet.getByText('Edit set').waitFor({ timeout: 10000 });
  await sheet.getByPlaceholder('Reps').fill('8');
  await sheet.getByRole('button', { name: 'Save' }).click();
  await sheet.waitFor({ state: 'detached', timeout: 15000 });
  const firstRow = await bench.getByRole('button', { name: 'Edit set' }).first().innerText();
  check('editing a logged set saves it', /× 8\b/.test(firstRow), firstRow);

  await logSet(50, 5);
  await bench.getByRole('button', { name: 'Edit set' }).last().click();
  await page.getByRole('dialog').getByRole('button', { name: 'Delete set' }).click();
  await page.waitForTimeout(1500);
  check('deleting a set removes it', (await logged()) === 2, String(await logged()));

  // An exercise picked but not logged: must survive the refresh below.
  await addExercise(page, 'Back Squat');
  check('a new exercise takes the focus',
    await ok(page.locator('.ma-card').nth(1).locator('.ma-entry').waitFor({ timeout: 15000 })));

  // ---------------------------------------------------------------------
  section('Workout: refresh mid-workout');
  await page.reload();
  await bench.getByRole('button', { name: 'Edit set' }).nth(1).waitFor({ timeout: 20000 });
  check('refresh rehydrates the live session', (await logged()) === 2);
  check('an added-but-unlogged exercise survives the refresh',
    await ok(page.getByText('Back Squat', { exact: true }).first().waitFor({ timeout: 10000 })));
  await page.waitForTimeout(600); // one timer tick after hydration
  check('rest timer survives the refresh', (await page.locator('#ma-rest[data-ma-state="on"]').count()) === 1);
  const restLeft = (await page.locator('#ma-rest-time').getAttribute('data-ma-time')) || '';
  check('rest countdown shows time left', /^\d+:\d\d$/.test(restLeft), restLeft);
  const clock = (await page.locator('[data-ma-start]').first().getAttribute('data-ma-clock')) || '';
  check('elapsed clock ticks client-side', /^\d+:\d\d/.test(clock), clock);
  await page.screenshot({ path: `${OUT}/04-live-workout.png`, fullPage: true });

  // ---------------------------------------------------------------------
  section('Workout: finish');
  await page.getByRole('button', { name: 'Finish', exact: true }).click();
  await page.getByRole('button', { name: 'Finish workout' }).click();
  await page.getByText('Workout complete').waitFor({ timeout: 15000 });
  await dismissLevelUp();
  check('finishing shows the summary', true);
  check('a short session explains the missing bonus', await visible(page.getByText(/Short session/)));
  const last = (await api('/workouts/sessions?limit=1', 'GET', null, token)).body[0];
  check('summary points match the API',
    await visible(page.locator('.ma-points-total').getByText(`+${last.points_total}`, { exact: true })),
    `api=${last.points_total}`);
  await page.screenshot({ path: `${OUT}/05-summary.png`, fullPage: true });
  // Share draws the story card in the browser; a desktop browser downloads it.
  const [card] = await Promise.all([
    page.waitForEvent('download', { timeout: 15000 }),
    page.getByRole('button', { name: 'Share' }).click(),
  ]);
  const cardPath = `${OUT}/05b-share-card.png`;
  await card.saveAs(cardPath);
  const png = readFileSync(cardPath);
  check('share makes a 1080x1920 story card',
    card.suggestedFilename().startsWith('metalarm-') && png.readUInt32BE(16) === 1080 && png.readUInt32BE(20) === 1920,
    `${card.suggestedFilename()} ${png.readUInt32BE(16)}x${png.readUInt32BE(20)}`);
  await page.getByRole('button', { name: 'Done', exact: true }).click();
  check('Done returns to the Train tab',
    await ok(page.getByRole('button', { name: 'Start empty workout' }).waitFor({ timeout: 15000 })));
  await page.goto(UI + '/progress/history');
  check('the workout is in History',
    await ok(page.getByText(/(Morning|Afternoon|Evening|Late-night) workout/).first().waitFor({ timeout: 15000 })));

  // ---------------------------------------------------------------------
  section('Weight unit is saved on the account');
  await page.goto(UI + '/profile');
  await page.getByRole('button', { name: 'lb', exact: true }).click();
  await page.waitForTimeout(1200);
  await page.goto(UI + '/progress/history');
  check('switching to lb re-renders in lb', await ok(page.getByText(/\d lb/).first().waitFor({ timeout: 15000 })));
  const fresh = await browser.newContext({ viewport: { width: 390, height: 860 } });
  const other = await fresh.newPage();
  await signIn(other);
  await other.goto(UI + '/progress/history');
  check('a fresh browser gets the account unit (lb)', await ok(other.getByText(/\d lb/).first().waitFor({ timeout: 15000 })));
  await fresh.close();
  await page.goto(UI + '/profile');
  await page.getByRole('button', { name: 'kg', exact: true }).click();
  await page.waitForTimeout(1200);
  await page.goto(UI + '/progress/history');
  check('switching back to kg', await ok(page.getByText(/\d kg/).first().waitFor({ timeout: 15000 })));

  // ---------------------------------------------------------------------
  section('Routines');
  await page.goto(UI + '/train');
  await page.getByText('New routine', { exact: true }).first().click();
  await page.waitForURL('**/train/routine/new', { timeout: 15000 });
  await page.getByPlaceholder('Routine name').fill('E2E Legs');
  await addExercise(page, 'Back Squat');
  await page.getByRole('button', { name: 'Move down' }).first().waitFor({ timeout: 15000 });
  await page.getByRole('button', { name: 'Save routine' }).click();
  check('saving a new routine opens it',
    await ok(page.waitForURL(/\/train\/routine\/[0-9a-f-]{36}$/, { timeout: 15000 })));
  check('routine created with the picker', await visible(page.getByText('Back Squat', { exact: true }).first()));
  await page.getByRole('button', { name: 'Start routine' }).click();
  await page.waitForURL(/\/train\/?$/, { timeout: 20000 });
  await page.locator('.ma-card').first().waitFor({ timeout: 15000 });
  check('starting a routine opens a workout with its targets',
    (await visible(page.getByText('Back Squat', { exact: true }))) &&
    (await page.locator('.ma-entry input').nth(1).inputValue()) === '8');
  await discardWorkout(page);
  check('discarding a workout returns to the Train tab', true);

  // ---------------------------------------------------------------------
  section('Ready-made workouts');
  const presets = page.locator('.ma-preset-card');
  await presets.first().waitFor({ timeout: 15000 });
  check('three ready-made workouts are offered', (await presets.count()) === 3);
  check('a row names its style', await visible(page.getByText(/^Powerlifter · /).first()));

  await page.locator('.ma-preset-card[data-preset="powerlifting-heavy-day"]').click();
  await page.locator('.ma-preset-demo').waitFor({ timeout: 15000 });
  check('the plan opens with a demo beside it', await visible(page.locator('.ma-preset-demo')));
  const slots = page.locator('.ma-preset-slot');
  check('the plan lists its movements', (await slots.count()) >= 3);
  check('a movement shows its sets and rest', await visible(page.getByText(/× 5 · rest/).first()));
  await page.waitForTimeout(500);
  await page.screenshot({ path: `${OUT}/06-ready-made-workout.png` });
  await page.locator('.ma-preset-slot[data-slot="Deadlift"]').click();
  await page.waitForTimeout(600);
  check('the demo follows the picked movement',
    await visible(page.locator('.ma-preset-demo').getByText('Deadlift', { exact: true })));
  await page.locator('.ma-preset-start').click();
  await page.locator('.ma-card').first().waitFor({ timeout: 20000 });
  check('starting a ready-made workout loads its plan', await visible(page.getByText('Back Squat', { exact: true })));
  check('its targets come with it', (await page.locator('.ma-entry input').nth(1).inputValue()) !== '');
  await discardWorkout(page);

  // ---------------------------------------------------------------------
  section('Progress');
  await page.goto(UI + '/progress');
  await page.locator('.recharts-surface').first().waitFor({ timeout: 15000 }).catch(() => {});
  check('the chart renders', (await page.locator('.recharts-surface').count()) >= 1);
  check('personal records listed', await ok(page.getByText(/^Heaviest · /).first().waitFor({ timeout: 15000 })));
  await page.locator('.ma-focus-row').click();
  await page.getByRole('dialog').getByText('Barbell Bench Press').first().click();
  check('one exercise on the chart',
    await ok(page.getByRole('button', { name: 'Estimated 1RM' }).waitFor({ timeout: 15000 })) &&
    await visible(page.locator('.ma-focus-row').getByText('Barbell Bench Press', { exact: true })));
  await page.goto(UI + '/progress/measurements');
  await page.getByRole('button', { name: 'Log measurement' }).click();
  await page.getByPlaceholder(/^Value/).fill('80.5');
  await page.getByRole('button', { name: 'Save', exact: true }).click();
  check('body measurement logged', await ok(page.getByText('80.5 kg').first().waitFor({ timeout: 15000 })));

  // What to try next (double progression). The bench has history now, so a
  // second workout's card carries the hint - no set is logged, so the records
  // and rank trials the profile checks below stay as they were.
  await page.goto(UI + '/train');
  await page.getByRole('button', { name: 'Start empty workout' }).click();
  await page.getByRole('button', { name: 'Add exercise' }).waitFor({ timeout: 15000 });
  await addExercise(page, 'Barbell Bench Press');
  check('the card suggests what to try next', await ok(page.getByText(/Try .* x \d+/).waitFor({ timeout: 15000 })));
  await discardWorkout(page);

  // ---------------------------------------------------------------------
  section('Profile and parties');
  await page.goto(UI + '/profile');
  await page.getByText('Badges', { exact: true }).click();
  check('workout badges are on the profile', await ok(page.getByText('Iron Initiate').waitFor({ timeout: 15000 })));
  await page.getByRole('dialog').getByRole('button', { name: 'Close' }).click();
  check('profile shows lifetime training', await visible(page.getByText('Lifted', { exact: true })));
  // The 80.5 kg bodyweight logged above sets every trial's target.
  await page.getByText('Rank trials', { exact: true }).click();
  check('the bench trial targets 1x bodyweight', await ok(page.getByText(/of 80\.5 kg/).first().waitFor({ timeout: 15000 })));
  await page.getByRole('dialog').getByRole('button', { name: 'Close' }).click();
  await page.getByText('Character stats', { exact: true }).click();
  check('character stats are scored', await ok(page.getByText(/lifted in four weeks/).first().waitFor({ timeout: 15000 })));
  await page.getByRole('dialog').getByRole('button', { name: 'Close' }).click();

  await page.getByText('Training path', { exact: true }).click();
  const pathCards = page.locator('.ma-path-card');
  await pathCards.first().waitFor({ timeout: 15000 });
  check('all three training paths are offered', (await pathCards.count()) === 3);
  check('a path says how it trains', await visible(page.getByText(/1-6 reps · heavy · long rests/)));
  await page.locator('.ma-path-card[data-path="powerlifter"]').click();
  check('picking a path shows it in Settings',
    await ok(page.getByText('Powerlifter', { exact: true }).first().waitFor({ timeout: 15000 })));
  await page.reload();
  check('the chosen path stuck', await ok(page.getByText('Powerlifter', { exact: true }).first().waitFor({ timeout: 15000 })));

  // A Strong export dropped on the profile becomes history.
  const strongCsv = 'Date,Workout Name,Duration,Exercise Name,Set Order,Weight,Reps,Distance,Seconds,Notes,Workout Notes,RPE\n'
    + '2026-09-01 18:00:00,Imported Push,45m,Bench Press (Barbell),1,60,5,0,0,,,\n'
    + '2026-09-01 18:00:00,Imported Push,45m,Bench Press (Barbell),2,62.5,5,0,0,,,\n';
  await page.locator('input[type=file]').first().setInputFiles({ name: 'strong.csv', mimeType: 'text/csv', buffer: Buffer.from(strongCsv) });
  check('a Strong export imports from the profile',
    await ok(page.getByText(/Imported 1 workout \(2 sets\) from Strong/).waitFor({ timeout: 15000 })));

  const party = await api('/parties', 'POST', { name: 'E2E Crew' }, token);
  check('party created', party.status === 201);
  await page.goto(UI + '/parties');
  await page.getByText('Workout board', { exact: true }).waitFor({ timeout: 15000 });
  check('party page shows the workout leaderboard', await visible(page.getByText(/\d+ pts$/).first()));
  check('party page shows the party raid', await visible(page.getByText('Party raid', { exact: true })));
  check('the page shows this week\'s league', await visible(page.getByText('League', { exact: true })));
  check('the league says where you stand', await visible(page.getByText(/You're \d+ of \d+ with \d+ points/)));
  check('the raid shows the boss HP', await visible(page.getByText(/[\d,]+ \/ [\d,]+ HP/).first()));
  check('a new party\'s boss has no hits yet', await visible(page.getByText('No hits yet', { exact: false })));
  await page.getByRole('button', { name: 'All time', exact: true }).click();
  await page.waitForTimeout(800);
  check('leaderboard period toggles', await visible(page.getByText(/\d+ workouts?$/).first()));

  check('no uncaught errors during the journey', pageErrors.length === 0, pageErrors.slice(0, 3).join(' | '));

  // ---------------------------------------------------------------------
  section('Every page, phone and desktop');
  const routes = ['/home', '/train', '/train/exercises', '/progress', '/progress/history', '/profile', '/parties',
    '/duels', '/rewards', '/quests', '/leaderboard'];
  for (const [label, viewport] of [['phone', { width: 360, height: 800 }], ['desktop', { width: 1280, height: 900 }]]) {
    const sweep = await browser.newContext({ viewport });
    const p = await sweep.newPage();
    const errors = [];
    p.on('pageerror', (e) => errors.push(String(e)));
    await signIn(p);
    for (const route of routes) {
      await p.goto(UI + route);
      await p.waitForLoadState('networkidle').catch(() => {});
      await p.waitForTimeout(700);
      await p.screenshot({ path: `${OUT}/sweep-${label}-${route.slice(1).replace(/\//g, '-')}.png`, fullPage: true });
      check(`${label} ${route}: no "Built with Reflex" badge`, (await p.getByText('Built with Reflex').count()) === 0);
      const overflow = await p.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
      check(`${label} ${route}: no horizontal overflow`, overflow <= 1, `${overflow}px`);
    }
    check(`${label}: no uncaught errors across every page`, errors.length === 0, errors.slice(0, 3).join(' | '));
    await sweep.close();
  }

  // The five-tab app's URLs still land somewhere.
  for (const [from, to] of [['/workout', '/train'], ['/library', '/train'], ['/explore', '/train/exercises'],
    ['/you', '/progress'], ['/dashboard', '/home'], ['/gallery', '/design-system']]) {
    await page.goto(UI + from);
    check(`${from} redirects to ${to}`, await ok(page.waitForURL(new RegExp(`${to}/?$`), { timeout: 15000 })),
      page.url());
  }
} catch (err) {
  failed.push(`aborted: ${err.message.split('\n')[0]}`);
  console.log('  ABORT', err.message.split('\n').slice(0, 6).join('\n'));
} finally {
  await browser.close();
}

console.log(`\n${failed.length ? `${failed.length} FAILED` : 'ALL PASSED'} (${passed} passed) - screenshots in ${OUT}`);
for (const f of failed) console.log('  -', f);
process.exit(failed.length ? 1 : 0);
