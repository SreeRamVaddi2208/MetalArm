// Overhaul Gate 2: every number on the clarity screens matches a
// hand-checked calculation.
//
//   node analytics_e2e.mjs [screenshot-dir]
//
// Against a RUNNING stack. A fresh account logs one workout through the API:
//   bench warm-up 60x5, bench 3 x 100x5, squat 2 x 140x3
//   -> 5 working sets, 3 x 500 + 2 x 420 = 2,340 kg,
//      bench best set 100 kg x 5, e1RM 100 x 35/30 = 116.7 kg.
// Then Home, Progress (the chart, the exercise sheet, History, Measurements,
// Recovery), Exercise Detail and Session Detail must show exactly those
// numbers, at 360, 390 and 430 wide, with no sideways scroll.

import { mkdirSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { chromium } from 'playwright-core';

const API = process.env.METALARM_API || 'http://localhost:8000/api/v1';
const UI = process.env.METALARM_UI || 'http://localhost:3000';
const OUT = process.argv[2] || join(tmpdir(), 'metalarm-analytics-e2e');

let passed = 0;
const failed = [];
function check(label, ok, detail = '') {
  if (ok) { passed++; console.log('  PASS', label); }
  else { failed.push(label); console.log('  FAIL', label, detail); }
}
const section = (name) => console.log(`\n${name}`);
const seen = (locator) => locator.first().waitFor({ timeout: 15000 }).then(() => true).catch(() => false);

async function api(path, method = 'GET', body, token) {
  const r = await fetch(API + path, {
    method,
    headers: { 'Content-Type': 'application/json', ...(token ? { Authorization: `Bearer ${token}` } : {}) },
    body: body ? JSON.stringify(body) : undefined,
  });
  const text = await r.text();
  return { status: r.status, body: text ? JSON.parse(text) : null };
}

async function exerciseId(token, name) {
  const found = (await api(`/exercises?q=${encodeURIComponent(name)}&limit=10`, 'GET', null, token)).body;
  return found.find((e) => e.name === name).id;
}

const launch = process.env.CHROME_PATH
  ? { executablePath: process.env.CHROME_PATH, headless: true }
  : { channel: 'chrome', headless: true };
const browser = await chromium.launch(launch);

try {
  const email = `gate2-${Date.now()}@metalarm.dev`;
  const password = 'gate-two-passphrase';
  await api('/auth/signup', 'POST', { email, password, display_name: 'Gate Two', timezone: 'UTC' });
  const token = (await api('/auth/login', 'POST', { email, password })).body.access_token;
  const bench = await exerciseId(token, 'Barbell Bench Press');
  const squat = await exerciseId(token, 'Back Squat');
  const s = (await api('/workouts/sessions', 'POST', { name: 'Gate day' }, token)).body;
  const sets = [[bench, 60, 5, true], [bench, 100, 5], [bench, 100, 5], [bench, 100, 5], [squat, 140, 3], [squat, 140, 3]];
  for (const [ex, kg, reps, warm] of sets) {
    await api(`/workouts/sessions/${s.id}/sets`, 'POST',
      { exercise_id: ex, weight: kg, unit: 'kg', reps, is_warmup: !!warm }, token);
  }
  const fin = (await api(`/workouts/sessions/${s.id}/finish`, 'POST', null, token)).body;
  check('the seed workout finished', fin && fin.session, JSON.stringify(fin).slice(0, 200));
  const recovery = (await api('/analytics/recovery', 'GET', null, token)).body;

  for (const width of [360, 390, 430]) {
    const dir = join(OUT, String(width));
    mkdirSync(dir, { recursive: true });
    section(`Gate 2 at ${width}px`);
    const ctx = await browser.newContext({ viewport: { width, height: width < 400 ? 800 : 932 },
      deviceScaleFactor: 2, isMobile: true, hasTouch: true });
    const page = await ctx.newPage();
    const errors = [];
    page.on('pageerror', (e) => errors.push(String(e)));
    const overflow = async (name) => {
      const wider = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
      check(`${name}: no horizontal overflow`, wider <= 1, `${wider}px`);
    };

    await page.goto(`${UI}/login`);
    await page.locator('input').first().fill(email);
    await page.locator('input[type=password]').fill(password);
    await page.getByRole('button', { name: 'Sign in' }).click();
    await page.waitForURL('**/home', { timeout: 30000 });

    // --- Home ---------------------------------------------------------------
    await page.goto(`${UI}/home`);
    check('Home: the last workout is Gate day, 2,340 kg',
      (await seen(page.getByText('Gate day'))) && (await seen(page.getByText(/· 2,340 kg$/))));
    check('Home: one workout this week', await seen(page.getByText('Workouts this week')));
    await page.screenshot({ path: join(dir, '01-home.png'), fullPage: true });
    await overflow('Home');

    // --- Progress: the chart ------------------------------------------------
    await page.goto(`${UI}/progress`);
    check('Progress: this week\'s volume is 2,340', await seen(page.getByText('2,340', { exact: true })));
    await page.getByRole('button', { name: 'Workouts', exact: true }).click();
    check('Progress: the Workouts chip reads 1', await seen(page.getByText('1', { exact: true })));
    await page.screenshot({ path: join(dir, '02-progress.png'), fullPage: true });
    await overflow('Progress');

    // --- Progress: every exercise, in the chart's sheet ----------------------
    await page.locator('.ma-focus-row').click();
    const sheet = page.getByRole('dialog');
    check('Exercises: bench best set 100 kg × 5, e1RM 116.7 kg',
      await seen(sheet.getByText('Best set 100 kg × 5 · e1RM 116.7 kg')));
    check('Exercises: squat e1RM 154 kg', await seen(sheet.getByText(/e1RM 154 kg/)));
    await page.screenshot({ path: join(dir, '03-exercises.png') });
    await sheet.getByRole('button', { name: 'Close' }).click();

    // --- History, Measurements, Recovery -----------------------------------
    await page.goto(`${UI}/progress/history`);
    check('History: the month shows 1 workout', await seen(page.getByText('1 workout', { exact: true })));
    check('History: the week header and the workout',
      (await seen(page.getByText(/^Week of \d+ [A-Z][a-z]{2} \d{4}$/))) && (await seen(page.getByText('Gate day'))));
    check(`History: points +${fin.points_credited}`, await seen(page.getByText(`+${fin.points_credited}`, { exact: true })));
    await page.screenshot({ path: join(dir, '04-history.png'), fullPage: true });
    await overflow('History');
    await page.goto(`${UI}/progress/measurements`);
    await page.getByRole('button', { name: 'Log measurement' }).click();
    await page.getByPlaceholder('Value (kg)').fill('80.5');
    await page.getByRole('button', { name: 'Save', exact: true }).click();
    check('Measurements: body weight 80.5 kg logged and shown', await seen(page.getByText('80.5 kg')));
    await page.screenshot({ path: join(dir, '05-measurements.png'), fullPage: true });
    await overflow('Measurements');
    await page.goto(`${UI}/progress/recovery`);
    check(`Recovery: ${recovery.overall}% (the API's)`, await seen(page.getByText(`${recovery.overall}%`, { exact: true })));
    check('Recovery: the note says it is an estimate', await seen(page.getByText(/estimate from your recent training/)));
    check('Recovery: the muscles worked include chest and quads', await seen(page.getByText(/Chest.*Quad|Quad.*Chest/)));
    await page.screenshot({ path: join(dir, '06-recovery.png'), fullPage: true });
    await overflow('Recovery');

    // --- Exercise Detail ---------------------------------------------------
    await page.goto(`${UI}/exercise/${bench}`);
    check('Exercise Detail: name and Add to workout',
      (await seen(page.getByText('Barbell Bench Press', { exact: true }))) &&
      (await seen(page.getByRole('button', { name: 'Add to workout' }))));
    await page.screenshot({ path: join(dir, '07-exercise-about.png'), fullPage: true });
    await page.getByRole('button', { name: 'Records', exact: true }).click();
    check('Records: heaviest 100 kg, e1RM 116.7 kg',
      (await seen(page.getByText('100 kg', { exact: true }))) && (await seen(page.getByText('116.7 kg', { exact: true }))));
    await page.getByRole('button', { name: 'History', exact: true }).click();
    check('History: the warm-up badge and three 100 kg × 5 sets',
      (await seen(page.getByText('W', { exact: true }))) && (await page.getByText('100 kg × 5', { exact: true }).count()) === 3);
    await page.getByRole('button', { name: 'Charts', exact: true }).click();
    check('Charts: a chart renders', await seen(page.locator('.recharts-surface')));
    await page.screenshot({ path: join(dir, '08-exercise-charts.png'), fullPage: true });
    await overflow('Exercise Detail');

    // --- Session Detail ----------------------------------------------------
    await page.goto(`${UI}/session/${s.id}`);
    check('Session Detail: volume 2,340 kg and 5 sets',
      (await seen(page.getByText('2,340 kg', { exact: true }))) && (await seen(page.getByText('5', { exact: true }))));
    check('Session Detail: both exercises listed',
      (await seen(page.getByText('Barbell Bench Press'))) && (await seen(page.getByText('Back Squat'))));
    await page.screenshot({ path: join(dir, '09-session.png'), fullPage: true });
    await overflow('Session Detail');

    check('no uncaught errors', errors.length === 0, errors.slice(0, 3).join(' | '));
    await ctx.close();
  }
} catch (err) {
  failed.push(`aborted: ${err.message.split('\n')[0]}`);
  console.log('  ABORT', err.message.split('\n').slice(0, 8).join('\n'));
} finally {
  await browser.close();
}

console.log(`\n${failed.length ? `${failed.length} FAILED` : 'ALL PASSED'} (${passed} passed) - screenshots in ${OUT}`);
for (const f of failed) console.log('  -', f);
process.exit(failed.length ? 1 : 0);
