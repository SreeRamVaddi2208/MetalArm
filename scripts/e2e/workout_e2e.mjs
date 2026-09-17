// Browser end-to-end test for MetalArm, against a RUNNING compose stack.
//
// Drives the real UI in the locally installed Chrome (headless, via
// playwright-core - no browser download) at phone width, then sweeps every
// page at phone and desktop width for uncaught errors and screenshots.
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
  await page.getByText('ENTER', { exact: true }).click();
  await page.waitForURL('**/dashboard', { timeout: 20000 });
}

// Scroll through the page so scroll-linked reveals play before a full-page
// screenshot; a full-page capture never scrolls on its own.
async function revealAll(page) {
  await page.evaluate(async () => {
    for (let y = 0; y < document.body.scrollHeight; y += 300) {
      window.scrollTo(0, y);
      await new Promise((r) => setTimeout(r, 60));
    }
    window.scrollTo(0, 0);
  });
  await page.waitForTimeout(500);
}

const launchOptions = process.env.CHROME_PATH
  ? { executablePath: process.env.CHROME_PATH, headless: true }
  : { channel: 'chrome', headless: true };
const browser = await chromium.launch(launchOptions);

try {
  const signup = await api('/auth/signup', 'POST', { email, password, display_name: 'E2E Lifter', timezone: 'UTC' });
  check('signup via API', signup.status === 201, JSON.stringify(signup.body));
  const token = (await api('/auth/login', 'POST', { email, password })).body.access_token;

  const ctx = await browser.newContext({ viewport: { width: 400, height: 860 }, deviceScaleFactor: 2 });
  const page = await ctx.newPage();
  const pageErrors = [];
  page.on('pageerror', (e) => pageErrors.push(String(e)));

  // ---------------------------------------------------------------------
  section('Workout: logging loop');
  await signIn(page);
  check('signed in through the form', page.url().endsWith('/dashboard'));

  await page.goto(UI + '/workout');
  await page.getByText('START EMPTY WORKOUT').click();
  await page.getByText('IN PROGRESS').waitFor({ timeout: 15000 });
  check('blank workout started', true);
  check('HUD shows the game layer', await visible(page.getByText('LEVEL 1')));
  check('a blank workout is named by time of day', await visible(page.getByText(/(Morning|Afternoon|Evening|Late-night) workout/).first()));

  await page.getByText('+ ADD EXERCISE').click();
  await page.getByPlaceholder('Search exercises…').fill('Barbell Bench');
  await page.getByText('Barbell Bench Press', { exact: true }).first().click();
  await page.getByText('First time - this sets your baseline').waitFor({ timeout: 15000 });
  check('exercise added from the picker', true);

  const nums = page.locator('input[type=number]');
  await nums.nth(0).fill('60');
  await nums.nth(1).fill('5');
  await page.getByText('LOG SET', { exact: true }).click();
  await page.getByText('60 kg × 5').waitFor({ timeout: 15000 });
  check('set logged and rendered', true);
  check('first-ever set is a baseline, not a PR moment',
    (await visible(page.getByText('BASELINE SET'))) && !(await visible(page.getByText('PERSONAL RECORD'))));
  check('a baseline set carries no PR badge', (await page.getByText('PR', { exact: true }).count()) === 0);
  await page.waitForTimeout(400);
  check('rest timer started (client-side)', (await page.locator('#ma-rest[data-ma-state="on"]').count()) === 1);
  check('entry pre-filled for the next set', (await nums.nth(0).inputValue()) === '60');
  await page.screenshot({ path: `${OUT}/01-first-set.png` });

  await page.getByRole('button', { name: '+', exact: true }).first().click();
  await page.waitForTimeout(600);
  check('weight stepper adds 2.5 kg', (await nums.nth(0).inputValue()) === '62.5', await nums.nth(0).inputValue());

  await nums.nth(0).fill('65');
  await page.getByText('LOG SET', { exact: true }).click();
  await page.getByText('PERSONAL RECORD').waitFor({ timeout: 15000 });
  check('a heavier set raises the PR moment (not a toast)', true);
  check('PR moment says what was beaten', await visible(page.getByText('+5 kg')));
  check('PR bonus shown from the API', await visible(page.getByText(/\+\d+ PR BONUS/)));
  await page.waitForTimeout(700); // let the entrance animation settle
  await page.screenshot({ path: `${OUT}/02-pr-moment.png` });
  await page.getByText('KEEP LIFTING').click();
  const leveled = await page.getByText('LEVEL UP', { exact: true }).waitFor({ timeout: 6000 }).then(() => true).catch(() => false);
  check('level-up follows once the PR moment is dismissed', leveled);
  if (leveled) {
    await page.waitForTimeout(700);
    await page.screenshot({ path: `${OUT}/03-level-up.png` });
    await page.getByText('CONTINUE', { exact: true }).click();
  }

  // ---------------------------------------------------------------------
  section('Workout: editing and deleting');
  await page.getByRole('button', { name: 'Edit set' }).first().click();
  await page.getByText('EDIT SET').waitFor({ timeout: 10000 });
  // The edit form renders above the card's own entry fields.
  await page.locator('input[type=number]').nth(1).fill('8');
  await page.getByText('SAVE', { exact: true }).click();
  await page.getByText('60 kg × 8').waitFor({ timeout: 15000 });
  check('editing a logged set saves it', !(await visible(page.getByText('60 kg × 5'))));

  await nums.nth(0).fill('50');
  await page.getByText('LOG SET', { exact: true }).click();
  await page.getByText('50 kg × 5').waitFor({ timeout: 15000 });
  await page.getByRole('button', { name: 'Delete set' }).last().click();
  await page.getByText('50 kg × 5').waitFor({ state: 'detached', timeout: 15000 }).catch(() => {});
  check('deleting a set removes it', !(await visible(page.getByText('50 kg × 5'))));

  // An exercise picked but not logged: must survive the refresh below.
  await page.getByText('+ ADD EXERCISE').click();
  await page.getByPlaceholder('Search exercises…').fill('Back Squat');
  await page.getByText('Back Squat', { exact: true }).first().click();
  await page.getByText('Back Squat', { exact: true }).first().waitFor({ timeout: 15000 });

  // ---------------------------------------------------------------------
  section('Workout: refresh mid-workout');
  await page.reload();
  await page.getByText('65 kg × 5').waitFor({ timeout: 20000 });
  check('refresh rehydrates the live session', await visible(page.getByText('60 kg × 8')));
  check('an added-but-unlogged exercise survives the refresh',
    await page.getByText('Back Squat', { exact: true }).first().waitFor({ timeout: 10000 }).then(() => true).catch(() => false));
  await page.waitForTimeout(600); // one timer tick after hydration
  check('rest timer survives the refresh', (await page.locator('#ma-rest[data-ma-state="on"]').count()) === 1);
  const restLeft = (await page.locator('#ma-rest-time').getAttribute('data-ma-time')) || '';
  check('rest countdown shows time left', /^\d+:\d\d$/.test(restLeft), restLeft);
  const clock = (await page.locator('[data-ma-start]').getAttribute('data-ma-clock')) || '';
  check('elapsed clock ticks client-side', /^\d+:\d\d/.test(clock), clock);
  await revealAll(page);
  await page.screenshot({ path: `${OUT}/04-live-workout.png`, fullPage: true });

  // ---------------------------------------------------------------------
  section('Workout: finish');
  await page.getByText('FINISH WORKOUT').click();
  await page.getByText('WORKOUT COMPLETE').waitFor({ timeout: 15000 });
  check('finishing shows the summary', true);
  check('a short session explains the missing bonus', await visible(page.getByText(/Short session/)));
  const last = (await api('/workouts/sessions?limit=1', 'GET', null, token)).body[0];
  check('summary points match the API',
    await visible(page.getByText(`+${last.points_total}`, { exact: true }).first()), `api=${last.points_total}`);
  await page.screenshot({ path: `${OUT}/05-summary.png`, fullPage: true });
  // SHARE draws the story card in the browser; a desktop browser downloads it.
  const [card] = await Promise.all([
    page.waitForEvent('download', { timeout: 15000 }),
    page.getByText('SHARE', { exact: true }).click(),
  ]);
  const cardPath = `${OUT}/05b-share-card.png`;
  await card.saveAs(cardPath);
  const png = readFileSync(cardPath);
  check('share makes a 1080x1920 story card',
    card.suggestedFilename().startsWith('metalarm-') && png.readUInt32BE(16) === 1080 && png.readUInt32BE(20) === 1920,
    `${card.suggestedFilename()} ${png.readUInt32BE(16)}x${png.readUInt32BE(20)}`);
  await page.getByText('DONE', { exact: true }).click();
  await page.getByText('START EMPTY WORKOUT').waitFor({ timeout: 15000 });
  await page.getByText(/\d+ sets · /).first().waitFor({ timeout: 10000 }).catch(() => {});
  check('back to the start screen, with the workout in RECENT', await visible(page.getByText(/\d+ sets · /).first()));

  // ---------------------------------------------------------------------
  section('Weight unit is saved on the account');
  await page.getByRole('button', { name: 'LB', exact: true }).click();
  await page.getByText(/ lb$/).first().waitFor({ timeout: 15000 }).catch(() => {});
  check('switching to lb re-renders in lb', await visible(page.getByText(/\d lb$/).first()));
  const fresh = await browser.newContext({ viewport: { width: 400, height: 860 } });
  const other = await fresh.newPage();
  await signIn(other);
  await other.goto(UI + '/workout');
  await other.getByText('START EMPTY WORKOUT').waitFor({ timeout: 15000 });
  await other.getByText(/\d+ sets · /).first().waitFor({ timeout: 10000 }).catch(() => {});
  check('a fresh browser gets the account unit (lb)', await visible(other.getByText(/\d lb$/).first()));
  await fresh.close();
  await page.getByRole('button', { name: 'KG', exact: true }).click();
  await page.getByText(/\d kg$/).first().waitFor({ timeout: 15000 }).catch(() => {});
  check('switching back to kg', await visible(page.getByText(/\d kg$/).first()));

  // ---------------------------------------------------------------------
  section('Routines');
  await page.goto(UI + '/routines');
  await page.getByText('+ NEW ROUTINE').click();
  await page.getByPlaceholder('Routine name, e.g. Push day').fill('E2E Legs');
  await page.getByText('+ ADD EXERCISE').click();
  await page.getByPlaceholder('Search exercises…').fill('Back Squat');
  await page.getByText('Back Squat', { exact: true }).first().click();
  await page.locator('input[type=number]').first().waitFor({ timeout: 15000 });
  await page.getByText('SAVE ROUTINE').click();
  await page.getByText('Saved E2E Legs.').waitFor({ timeout: 15000 });
  check('routine created with the picker', true);
  await page.getByText('START', { exact: true }).first().click();
  await page.waitForURL('**/workout', { timeout: 20000 });
  await page.getByText('TARGET', { exact: false }).first().waitFor({ timeout: 15000 });
  check('starting a routine opens a workout with its targets', await visible(page.getByText('Back Squat', { exact: true })));
  await page.getByText('DISCARD', { exact: true }).click();
  // The confirm row replaces the button; clicking `.last()` before it renders
  // hit the same button again and the test stalled.
  await page.getByText('Discard this workout?').waitFor({ timeout: 15000 });
  await page.getByText('DISCARD', { exact: true }).last().click();
  await page.getByText('START EMPTY WORKOUT').waitFor({ timeout: 15000 });
  check('discarding a workout returns to the start screen', true);

  // ---------------------------------------------------------------------
  section('Progress');
  await page.goto(UI + '/progress');
  await page.getByText('EXERCISE PROGRESS').waitFor({ timeout: 15000 });
  await page.locator('.recharts-surface').first().waitFor({ timeout: 15000 }).catch(() => {});
  check('exercise chart renders', (await page.locator('.recharts-surface').count()) >= 1);
  check('personal records listed', await visible(page.getByText('HEAVIEST').first()));
  await page.getByPlaceholder('Value').fill('80.5');
  await page.getByText('ADD', { exact: true }).click();
  await page.getByText('80.5 kg').waitFor({ timeout: 15000 });
  check('body measurement logged', true);

  // What to try next (double progression). The bench has history now, so a
  // second workout's card carries the hint - no set is logged, so the records
  // and rank trials the profile checks below stay as they were.
  await page.goto(UI + '/workout');
  await page.getByText('START EMPTY WORKOUT').click();
  await page.getByText('IN PROGRESS').waitFor({ timeout: 15000 });
  await page.getByText('+ ADD EXERCISE').click();
  await page.getByPlaceholder('Search exercises…').fill('Barbell Bench');
  await page.getByText('Barbell Bench Press', { exact: true }).first().click();
  const hint = await page.getByText(/Try .* x \d+/).waitFor({ timeout: 15000 }).then(() => true).catch(() => false);
  check('the card suggests what to try next', hint);

  // ---------------------------------------------------------------------
  section('Profile and parties');
  await page.goto(UI + '/profile');
  // Wait on DATA, not on a static label: "TRAINING" renders before the
  // profile has loaded, so waiting on it raced the badge list.
  const badgesLoaded = await page.getByText('Iron Initiate').waitFor({ timeout: 15000 }).then(() => true).catch(() => false);
  check('workout badges are on the profile', badgesLoaded);
  check('profile shows training stats', await visible(page.getByText('VOLUME LIFTED')));
  // The 80.5 kg bodyweight logged above sets every trial's target.
  // The trials are a second request, so they can land after the badges.
  // exact: the import panel's copy also says "rank trials", and a plain
  // string match is case-insensitive and would hit both.
  const trialsLoaded = await page.getByText('RANK TRIALS', { exact: true }).waitFor({ timeout: 15000 }).then(() => true).catch(() => false);
  check('profile shows the rank trials', trialsLoaded);
  check('the bench trial targets 1x bodyweight', await visible(page.getByText(/of 80\.5 kg/)));

  // The character sheet: three stats, and a class that only highlights them.
  check('profile shows the character sheet', await visible(page.getByText('CHARACTER', { exact: true })));
  check('character stats are scored', await visible(page.getByText(/lifted in four weeks/)));
  await page.getByText('POWERLIFTER', { exact: true }).click();
  const classPicked = await page.getByText('Powerlifter', { exact: true }).waitFor({ timeout: 15000 }).then(() => true).catch(() => false);
  check('picking a class shows it on the sheet', classPicked);

  // A Strong export dropped on the profile becomes history.
  const strongCsv = 'Date,Workout Name,Duration,Exercise Name,Set Order,Weight,Reps,Distance,Seconds,Notes,Workout Notes,RPE\n'
    + '2026-09-01 18:00:00,Imported Push,45m,Bench Press (Barbell),1,60,5,0,0,,,\n'
    + '2026-09-01 18:00:00,Imported Push,45m,Bench Press (Barbell),2,62.5,5,0,0,,,\n';
  await page.locator('input[type=file]').first().setInputFiles({ name: 'strong.csv', mimeType: 'text/csv', buffer: Buffer.from(strongCsv) });
  const imported = await page.getByText(/Imported 1 workout \(2 sets\) from Strong/).waitFor({ timeout: 15000 }).then(() => true).catch(() => false);
  check('a Strong export imports from the profile', imported);

  const party = await api('/parties', 'POST', { name: 'E2E Crew' }, token);
  check('party created', party.status === 201);
  await page.goto(UI + '/parties');
  await page.getByText('WORKOUT BOARD').waitFor({ timeout: 15000 });
  check('party page shows the workout leaderboard', await visible(page.getByText(/\d+ PTS/).first()));
  // This week's party boss (backend core/raids.py): the workouts above already hit it.
  check('party page shows the party raid', await visible(page.getByText('PARTY RAID')));
  check('the raid shows the boss HP', await visible(page.getByText(/[\d,]+ \/ [\d,]+ HP/).first()));
  // The party was made after this run's workouts, and only a member's workouts hit it.
  check('a new party\'s boss has no hits yet', await visible(page.getByText('No hits yet', { exact: false })));
  await page.getByText('ALL TIME', { exact: true }).click();
  await page.waitForTimeout(800);
  check('leaderboard period toggles', await visible(page.getByText(/\d+ workouts?$/).first()));

  check('no uncaught errors during the journey', pageErrors.length === 0, pageErrors.slice(0, 3).join(' | '));

  // ---------------------------------------------------------------------
  section('Every page, phone and desktop');
  const routes = ['/dashboard', '/workout', '/routines', '/progress', '/parties', '/rewards', '/profile'];
  for (const [label, viewport] of [['phone', { width: 400, height: 860 }], ['desktop', { width: 1280, height: 900 }]]) {
    const sweep = await browser.newContext({ viewport });
    const p = await sweep.newPage();
    const errors = [];
    p.on('pageerror', (e) => errors.push(String(e)));
    await signIn(p);
    for (const route of routes) {
      await p.goto(UI + route);
      await p.waitForLoadState('networkidle').catch(() => {});
      await p.waitForTimeout(700);
      await revealAll(p);
      await p.screenshot({ path: `${OUT}/sweep-${label}-${route.slice(1)}.png`, fullPage: true });
      check(`${label} ${route}: no "Built with Reflex" badge`, (await p.getByText('Built with Reflex').count()) === 0);
      const overflow = await p.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
      check(`${label} ${route}: no horizontal overflow`, overflow <= 1, `${overflow}px`);
    }
    check(`${label}: no uncaught errors across every page`, errors.length === 0, errors.slice(0, 3).join(' | '));
    await sweep.close();
  }

  const signedOut = await browser.newContext({ viewport: { width: 400, height: 860 } });
  const lp = await signedOut.newPage();
  for (const route of ['/login', '/signup']) {
    await lp.goto(UI + route);
    await lp.waitForTimeout(800);
    await lp.screenshot({ path: `${OUT}/sweep-phone-${route.slice(1)}.png`, fullPage: true });
  }
  await signedOut.close();
} catch (err) {
  failed.push(`aborted: ${err.message.split('\n')[0]}`);
  console.log('  ABORT', err.message.split('\n')[0]);
} finally {
  await browser.close();
}

console.log(`\n${failed.length ? `${failed.length} FAILED` : 'ALL PASSED'} (${passed} passed) - screenshots in ${OUT}`);
for (const f of failed) console.log('  -', f);
process.exit(failed.length ? 1 : 0);
