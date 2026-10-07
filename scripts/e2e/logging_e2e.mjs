// Gate: log a real routine end to end through Train, the active workout and
// the summary - and count the taps each set takes.
//
//   node logging_e2e.mjs [screenshot-dir]
//
// Against a RUNNING stack. A fresh account gets a five-exercise upper day
// with two supersets (API), opens it from the Train tab and starts it (UI),
// logs every set, makes one a warm-up, reorders, notes, refreshes
// mid-workout, finishes, and saves the workout back as a routine. At 360, 390
// and 430 wide. Exits non-zero on a failed check, if any set took more than
// two taps, or if any control on the workout screen is under the tap-target
// minimum.

import { mkdirSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { chromium } from 'playwright-core';

const API = process.env.METALARM_API || 'http://localhost:8000/api/v1';
const UI = process.env.METALARM_UI || 'http://localhost:3000';
const OUT = process.argv[2] || join(tmpdir(), 'metalarm-logging-e2e');
const MAX_TAPS = 2;
// 48 px for buttons, steppers and fields; 44 px is the IconButton's size.
const MIN_TARGET = 48;
const MIN_ICON = 44;

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

// The upper day: (sets, reps, kg, superset); bench+row and curl+pushdown pair up.
const PLAN = [
  ['Barbell Bench Press', 3, 8, 60, 1],
  ['Dumbbell Row', 3, 10, 24, 1],
  ['Overhead Press', 2, 8, 35, null],
  ['Hammer Curl', 2, 12, 12, 2],
  ['Tricep Pushdown', 2, 12, 25, 2],
];
const TOTAL = PLAN.reduce((n, p) => n + p[1], 0);

async function dismissMoments(page) {
  // A level-up is a takeover by design; the PR banner is not.
  const cont = page.getByRole('button', { name: 'Continue' });
  if (await visible(cont)) await cont.click();
}

async function smallTargets(page) {
  return page.evaluate(([minTarget, minIcon]) => {
    const out = [];
    const root = document.querySelector('.ma-card')?.parentElement?.parentElement || document.body;
    root.querySelectorAll('button, input, textarea, [role=button], [role=checkbox]').forEach((el) => {
      const r = el.getBoundingClientRect();
      if (!r.width || !r.height || el.closest('[role=dialog]')) return;
      const icon = el.getAttribute('role') === 'button' && !el.textContent.trim();
      const min = icon ? minIcon : minTarget;
      if (r.height < min - 0.5 || r.width < min - 0.5) {
        out.push(`${el.getAttribute('aria-label') || el.textContent.trim().slice(0, 24) || el.tagName} ` +
                 `${Math.round(r.width)}x${Math.round(r.height)}`);
      }
    });
    return out;
  }, [MIN_TARGET, MIN_ICON]);
}

const launch = process.env.CHROME_PATH
  ? { executablePath: process.env.CHROME_PATH, headless: true }
  : { channel: 'chrome', headless: true };
const browser = await chromium.launch(launch);

try {
  for (const width of [360, 390, 430]) {
    const dir = join(OUT, String(width));
    mkdirSync(dir, { recursive: true });
    const email = `gate1-${width}-${Date.now()}@metalarm.dev`;
    const password = 'gate-one-passphrase';
    section(`Logging at ${width}px`);
    await api('/auth/signup', 'POST', { email, password, display_name: 'Gate One', timezone: 'UTC' });
    const token = (await api('/auth/login', 'POST', { email, password })).body.access_token;

    const exercises = [];
    for (const [name, sets, reps, kg, group] of PLAN) {
      exercises.push({ exercise_id: await exerciseId(token, name), target_sets: sets, target_reps: reps,
        target_weight_kg: kg, rest_seconds: 60, superset_group: group });
    }
    const routine = await api('/routines', 'POST', { name: 'Upper Day', exercises }, token);
    check('routine created', routine.status === 201, JSON.stringify(routine.body));

    const ctx = await browser.newContext({ viewport: { width, height: width < 400 ? 800 : 932 },
      deviceScaleFactor: 2, isMobile: true, hasTouch: true });
    const page = await ctx.newPage();
    const errors = [];
    page.on('pageerror', (e) => errors.push(String(e)));

    await page.goto(`${UI}/login`);
    await page.locator('input').first().fill(email);
    await page.locator('input[type=password]').fill(password);
    await page.getByRole('button', { name: 'Sign in' }).click();
    await page.waitForURL('**/home', { timeout: 30000 });

    // --- Train -> routine -> start ----------------------------------------
    await page.goto(`${UI}/train`);
    await page.getByText('Upper Day').first().waitFor({ timeout: 20000 });
    check('the routine is on the Train tab', true);
    await page.screenshot({ path: join(dir, '01-train.png'), fullPage: true });
    await page.getByText('Upper Day').first().click();
    await page.waitForURL('**/train/routine/**', { timeout: 15000 });
    await page.getByText(/^Superset 1/).first().waitFor({ timeout: 15000 });
    check('the routine shows its supersets',
      (await page.getByText(/^Superset 1/).count()) === 2 && (await page.getByText(/^Superset 2/).count()) === 2);
    await page.screenshot({ path: join(dir, '02-routine.png'), fullPage: true });

    // Edit: the picker adds an exercise; Cancel throws the change away.
    await page.getByRole('button', { name: 'Edit' }).click();
    await page.getByText('Edit routine').waitFor({ timeout: 15000 });
    await page.getByRole('button', { name: 'Add exercises' }).click();
    await page.getByPlaceholder('Search exercises…').fill('Cable Lateral Raise');
    await page.getByRole('checkbox', { name: 'Cable Lateral Raise' }).first().click();
    await page.getByRole('button', { name: /^Add \d+ exercise/ }).click();
    await page.waitForTimeout(1200);
    const slots = await page.getByRole('button', { name: 'Move down' }).count();
    check('the picker adds an exercise to the routine', slots === PLAN.length + 1, `${slots} slots`);
    await page.screenshot({ path: join(dir, '02b-routine-editor.png'), fullPage: true });
    await page.getByRole('button', { name: 'Cancel' }).click();
    await page.getByRole('button', { name: 'Start routine' }).click();
    await page.waitForURL(/\/train\/?$/, { timeout: 20000 });
    const cards = page.locator('.ma-card');
    await cards.first().waitFor({ timeout: 20000 });
    check('the workout opens with one card per exercise', (await cards.count()) === PLAN.length,
      String(await cards.count()));
    check('only one Log set on screen', (await page.getByRole('button', { name: 'Log set' }).count()) === 1);
    check('targets are pre-filled', (await cards.first().locator('.ma-entry input').first().inputValue()) === '60');
    const small = await smallTargets(page);
    check('every control on the workout screen meets the tap-target minimum', small.length === 0, small.join(', '));

    // --- The first set of the bench is a warm-up: one extra tap -----------
    await page.getByRole('button', { name: 'Set type' }).click();
    await page.waitForTimeout(400);
    check('tapping Set marks a warm-up', await visible(cards.first().locator('.ma-entry').getByText('W', { exact: true })));

    // --- Log every set, following the focus, counting taps ----------------
    const taps = [];
    for (let k = 0; k <= TOTAL; k++) {
      let n = k === 0 ? 1 : 0; // the warm-up tap above
      const log = page.getByRole('button', { name: 'Log set' });
      if (!(await visible(log))) {
        // Nothing in focus: tap the next exercise open.
        const next = page.getByText(/^(Log next set|Start this exercise)$/).first();
        if (!(await visible(next))) break;
        await next.click(); n++;
      }
      const before = await page.getByRole('button', { name: 'Edit set' }).count();
      await page.getByRole('button', { name: 'Log set' }).click(); n++;
      await page.getByRole('button', { name: 'Edit set' }).nth(before).waitFor({ timeout: 15000 });
      taps.push(n);
      await dismissMoments(page);
      if (taps.length === TOTAL + 1) break; // the plan, plus the warm-up
    }
    const worst = Math.max(...taps);
    check(`logged the plan plus the warm-up (${taps.length} sets)`, taps.length === TOTAL + 1);
    check(`every set took ${MAX_TAPS} taps or fewer (worst ${worst})`, worst <= MAX_TAPS, taps.join(','));
    await page.screenshot({ path: join(dir, '03-active-workout.png'), fullPage: true });

    // --- Options sheet: notes and reorder ---------------------------------
    await cards.nth(2).getByRole('button', { name: 'Exercise options' }).click();
    const sheet = page.getByRole('dialog');
    await sheet.getByPlaceholder('Notes for this exercise').fill('Strict, no leg drive');
    await sheet.getByPlaceholder('Notes for this exercise').blur();
    await page.waitForTimeout(600);
    await sheet.getByText('Move up', { exact: true }).click();
    await page.waitForTimeout(1200);
    check('Move up reorders the cards', await visible(cards.nth(1).getByText('Overhead Press', { exact: true })));

    // --- Refresh mid-workout -------------------------------------------------
    await page.reload();
    await cards.first().waitFor({ timeout: 20000 });
    await page.waitForTimeout(1500);
    check('a refresh keeps every logged set',
      (await page.getByRole('button', { name: 'Edit set' }).count()) === taps.length);
    const kept = await page.getByText('Strict, no leg drive').first().waitFor({ timeout: 15000 }).then(() => true)
      .catch(() => false);
    check('a refresh keeps the new order and the note',
      kept && (await visible(cards.nth(1).getByText('Overhead Press', { exact: true }))));
    await page.screenshot({ path: join(dir, '03b-after-refresh.png'), fullPage: true });

    // --- Finish -> summary ---------------------------------------------------
    await page.getByRole('button', { name: 'Finish', exact: true }).click();
    await page.getByRole('button', { name: 'Finish workout' }).click();
    await page.getByText('Workout complete').waitFor({ timeout: 20000 });
    await dismissMoments(page);
    const last = (await api('/workouts/sessions?limit=1', 'GET', null, token)).body[0];
    check('summary points match the API',
      await visible(page.locator('.ma-points-total').getByText(`+${last.points_total}`, { exact: true })),
      `api=${last.points_total}`);
    check('summary shows the muscles worked', await visible(page.getByText('Muscles worked')));
    check('summary counts working sets, not the warm-up',
      await visible(page.getByText(String(TOTAL), { exact: true }).first()));
    check('one primary on the summary', (await page.locator('.ma-button-primary:visible').count()) === 1);
    await page.screenshot({ path: join(dir, '04-summary.png'), fullPage: true });
    await page.getByRole('button', { name: 'Save as routine' }).click();
    await page.getByText('Saved to your routines').waitFor({ timeout: 15000 });
    const routines = (await api('/routines', 'GET', null, token)).body;
    check('Save as routine adds a routine', routines.length === 2);
    await page.getByRole('button', { name: 'Done', exact: true }).click();
    await page.getByRole('button', { name: 'Start empty workout' }).waitFor({ timeout: 15000 });
    check('Done returns to the Train tab', true);
    await page.screenshot({ path: join(dir, '05-train-after.png'), fullPage: true });

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
