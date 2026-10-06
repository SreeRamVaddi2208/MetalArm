// Overhaul Gate 1: log a real routine end to end through the new Active
// Workout, Summary and Library - and count the taps each set takes.
//
//   node logging_e2e.mjs [screenshot-dir]
//
// Against a RUNNING stack. A fresh account gets a five-exercise upper day
// with two supersets (API), starts it from the Library (UI), logs every set,
// changes a set type, reorders, notes, refreshes mid-workout, finishes, and
// saves the workout back as a routine. Screenshots at 375 and 430 wide.
// Exits non-zero on a failed check, or if any set took more than three taps.

import { mkdirSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { chromium } from 'playwright-core';

const API = process.env.METALARM_API || 'http://localhost:8000/api/v1';
const UI = process.env.METALARM_UI || 'http://localhost:3000';
const OUT = process.argv[2] || join(tmpdir(), 'metalarm-logging-e2e');
const MAX_TAPS = 3;

let passed = 0;
const failed = [];
function check(label, ok, detail = '') {
  if (ok) { passed++; console.log('  PASS', label); }
  else { failed.push(label); console.log('  FAIL', label, detail); }
}
const section = (name) => console.log(`\n${name}`);
const visible = (locator) => locator.isVisible().catch(() => false);

async function api(path, method = 'GET', body, token) {
  const r = await fetch(API + path, {
    method,
    headers: { 'Content-Type': 'application/json', ...(token ? { Authorization: `Bearer ${token}` } : {}) },
    body: body ? JSON.stringify(body) : undefined,
  });
  const text = await r.text();
  return { status: r.status, body: text ? JSON.parse(text) : null };
}

const ids = {};
async function exerciseId(token, name) {
  if (ids[name]) return ids[name];
  const found = (await api(`/exercises?q=${encodeURIComponent(name)}&limit=10`, 'GET', null, token)).body;
  const hit = found.find((e) => e.name === name);
  if (!hit) throw new Error(`no exercise ${name}`);
  ids[name] = hit.id;
  return hit.id;
}

// The upper day: (sets, reps, kg); bench+row and curl+pushdown are supersets.
const PLAN = [
  ['Barbell Bench Press', 3, 8, 60, 1],
  ['Dumbbell Row', 3, 10, 24, 1],
  ['Overhead Press', 2, 8, 35, null],
  ['Hammer Curl', 2, 12, 12, 2],
  ['Tricep Pushdown', 2, 12, 25, 2],
];

const launch = process.env.CHROME_PATH
  ? { executablePath: process.env.CHROME_PATH, headless: true }
  : { channel: 'chrome', headless: true };
const browser = await chromium.launch(launch);

try {
  for (const width of [375, 430]) {
    const dir = join(OUT, String(width));
    mkdirSync(dir, { recursive: true });
    const email = `gate1-${width}-${Date.now()}@metalarm.dev`;
    const password = 'gate-one-passphrase';
    section(`Gate 1 at ${width}px`);
    await api('/auth/signup', 'POST', { email, password, display_name: 'Gate One', timezone: 'UTC' });
    const token = (await api('/auth/login', 'POST', { email, password })).body.access_token;

    const exercises = [];
    for (const [name, sets, reps, kg, group] of PLAN) {
      exercises.push({ exercise_id: await exerciseId(token, name), target_sets: sets, target_reps: reps,
        target_weight_kg: kg, rest_seconds: 60, superset_group: group });
    }
    const routine = await api('/routines', 'POST', { name: 'Upper Day', exercises }, token);
    check('routine created', routine.status === 201, JSON.stringify(routine.body));

    const ctx = await browser.newContext({ viewport: { width, height: width === 375 ? 812 : 932 },
      deviceScaleFactor: 2, isMobile: true, hasTouch: true });
    const page = await ctx.newPage();
    const errors = [];
    page.on('pageerror', (e) => errors.push(String(e)));

    await page.goto(`${UI}/login`);
    await page.locator('input').first().fill(email);
    await page.locator('input[type=password]').fill(password);
    await page.getByText('ENTER', { exact: true }).click();
    await page.waitForURL('**/home', { timeout: 30000 });

    // --- Library -> start --------------------------------------------------
    await page.goto(`${UI}/library`);
    await page.getByText('Upper Day').first().waitFor({ timeout: 20000 });
    check('the routine is in the Library', true);
    await page.screenshot({ path: join(dir, '01-library.png'), fullPage: true });
    await page.getByText('Upper Day').first().click();
    await page.getByText('Edit routine').waitFor({ timeout: 15000 });
    check('a routine opens in the editor with its supersets',
      (await page.getByText('Superset 1').count()) === 2 && (await page.getByText('Superset 2').count()) === 2);
    await page.screenshot({ path: join(dir, '02-routine-editor.png'), fullPage: true });
    // The picker opens over the editor sheet.
    await page.getByText('Add exercise', { exact: true }).click();
    await page.getByPlaceholder('Search exercises…').fill('Cable Lateral Raise');
    await page.getByText('Cable Lateral Raise', { exact: true }).first().click();
    await page.getByRole('button', { name: /^Add \d+ exercise/ }).click();
    await page.getByText('Cable Lateral Raise', { exact: true }).first().waitFor({ timeout: 15000 });
    await page.waitForTimeout(800);
    const slots = await page.getByRole('button', { name: 'Move down' }).count();
    check('the picker adds an exercise to the routine', slots === PLAN.length + 1, `${slots} slots`);
    await page.getByText('Cancel', { exact: true }).click();
    await page.getByText('Upper Day').first().click();
    await page.getByText('Edit routine').waitFor({ timeout: 15000 });
    await page.getByText('Start workout').click();
    await page.waitForURL('**/workout', { timeout: 20000 });
    const cards = page.locator('.ma-card');
    await cards.first().waitFor({ timeout: 20000 });
    check('the workout opens with one card per exercise', (await cards.count()) === PLAN.length, String(await cards.count()));
    check('targets are pre-filled', (await cards.first().locator('input').first().inputValue()) === '60');

    // --- First set of the bench is a warm-up: one extra tap ----------------
    await cards.first().getByRole('button', { name: 'Set type' }).last().click();
    await page.waitForTimeout(400);
    check('tapping SET cycles to a warm-up badge', await visible(cards.first().getByText('W', { exact: true })));

    // --- Log every set, counting taps --------------------------------------
    const taps = [];
    for (let i = 0; i < PLAN.length; i++) {
      const card = cards.nth(i);
      for (let s = 0; s < PLAN[i][1]; s++) {
        let n = 0;
        const before = await card.getByRole('button', { name: 'Edit set' }).count();
        await card.getByRole('button', { name: 'Log set' }).click(); n++;
        await card.getByRole('button', { name: 'Edit set' }).nth(before).waitFor({ timeout: 15000 });
        if (i === 0 && s === 0) n++; // the warm-up badge tap above
        taps.push(n);
        // Dismiss a PR or level-up moment if one appears; it is not a set tap.
        for (const label of ['KEEP LIFTING', 'CONTINUE']) {
          const b = page.getByText(label, { exact: true });
          if (await visible(b)) await b.click();
        }
      }
    }
    const worst = Math.max(...taps);
    check(`every set took ${MAX_TAPS} taps or fewer (worst ${worst}, ${taps.length} sets)`, worst <= MAX_TAPS, taps.join(','));
    check('inline points appear after a set', (await page.locator('.ma-points-fade').count()) > 0);
    await page.screenshot({ path: join(dir, '03-active-workout.png'), fullPage: true });

    // --- Card menu: notes and reorder --------------------------------------
    await cards.nth(2).getByRole('button', { name: 'Exercise options' }).click();
    await cards.nth(2).getByPlaceholder('Notes for this exercise').fill('Strict, no leg drive');
    await cards.nth(2).getByText('Move up').click();
    await page.waitForTimeout(1200);
    check('Move up reorders the cards',
      await visible(cards.nth(1).getByText('Overhead Press', { exact: true })));

    // --- Refresh mid-workout -------------------------------------------------
    await page.reload();
    await cards.first().waitFor({ timeout: 20000 });
    check('a refresh keeps every logged set',
      (await page.getByRole('button', { name: 'Edit set' }).count()) === taps.length);
    await page.waitForTimeout(1500);
    await page.screenshot({ path: join(dir, '03b-after-refresh.png'), fullPage: true });
    const kept = await page.getByText('Strict, no leg drive').first().waitFor({ timeout: 15000 }).then(() => true).catch(() => false);
    check('a refresh keeps the new order and the note',
      kept && (await visible(cards.nth(1).getByText('Overhead Press', { exact: true }))));

    // --- Finish -> summary ---------------------------------------------------
    await page.getByText('Finish', { exact: true }).click();
    await page.getByText('Workout complete').waitFor({ timeout: 20000 });
    const last = (await api('/workouts/sessions?limit=1', 'GET', null, token)).body[0];
    check('summary points match the API',
      await visible(page.getByText(`+${last.points_total}`, { exact: true }).first()), `api=${last.points_total}`);
    check('summary shows the muscles worked', await visible(page.getByText('Muscles worked')));
    check('summary counts working sets, not the warm-up',
      await visible(page.getByText(String(taps.length - 1), { exact: true }).first()));
    await page.screenshot({ path: join(dir, '04-summary.png'), fullPage: true });
    await page.getByText('Save as routine').click();
    await page.getByText('Saved to your Library').waitFor({ timeout: 15000 });
    const routines = (await api('/routines', 'GET', null, token)).body;
    check('Save as routine adds it to the Library', routines.length === 2);
    await page.getByText('Done', { exact: true }).click();

    // --- Library after --------------------------------------------------------
    await page.goto(`${UI}/library`);
    await page.getByText('Routines', { exact: true }).first().waitFor({ timeout: 15000 });
    await page.waitForTimeout(800);
    await page.getByRole('button', { name: 'Show as a list' }).click();
    await page.waitForTimeout(500);
    await page.screenshot({ path: join(dir, '05-library-list.png'), fullPage: true });
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
    check('no horizontal overflow', overflow <= 1, `${overflow}px`);
    check('no uncaught errors', errors.length === 0, errors.slice(0, 3).join(' | '));
    await ctx.close();
  }
} catch (err) {
  failed.push(`aborted: ${err.message.split('\n')[0]}`);
  console.log('  ABORT', err.message.split('\n').slice(0, 12).join('\n'));
} finally {
  await browser.close();
}

console.log(`\n${failed.length ? `${failed.length} FAILED` : 'ALL PASSED'} (${passed} passed) - screenshots in ${OUT}`);
for (const f of failed) console.log('  -', f);
process.exit(failed.length ? 1 : 0);
