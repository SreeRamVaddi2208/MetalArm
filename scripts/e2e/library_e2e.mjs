// The Library tab, end to end, once per training path - and once with none.
//
//   node library_e2e.mjs [screenshot-dir]
//
// Against a RUNNING stack. For each path a fresh account picks it, opens the
// Library, and checks that what it leads with is exactly the server's
// recommendation, in the server's order. Then it opens a recommended workout,
// starts it, logs sets across several exercises, finishes, and checks that the
// summary's points are the API's. The powerlifter run also follows a program
// and sees it move on. A last account with no path gets the choose-your-path
// prompt and all three paths, never an empty screen.

import { mkdirSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { chromium } from 'playwright-core';

const API = process.env.METALARM_API || 'http://localhost:8000/api/v1';
const UI = process.env.METALARM_UI || 'http://localhost:3000';
const OUT = process.argv[2] || join(tmpdir(), 'metalarm-library-e2e');
mkdirSync(OUT, { recursive: true });

let passed = 0;
const failed = [];
function check(label, ok, detail = '') {
  if (ok) { passed++; console.log('  PASS', label); }
  else { failed.push(label); console.log('  FAIL', label, detail); }
}
const section = (name) => console.log(`\n${name}`);
const ok = (p) => p.then(() => true).catch(() => false);

async function api(path, method = 'GET', body, token) {
  const r = await fetch(API + path, {
    method,
    headers: { 'Content-Type': 'application/json', ...(token ? { Authorization: `Bearer ${token}` } : {}) },
    body: body ? JSON.stringify(body) : undefined,
  });
  const text = await r.text();
  return { status: r.status, body: text ? JSON.parse(text) : null };
}

async function account(path) {
  const email = `library-${path || 'none'}-${Date.now()}@metalarm.dev`;
  const password = 'library-e2e-passphrase';
  await api('/auth/signup', 'POST', { email, password, display_name: 'Library Lifter', timezone: 'UTC' });
  const token = (await api('/auth/login', 'POST', { email, password })).body.access_token;
  if (path) await api('/auth/me', 'PATCH', { character_class: path }, token);
  return { email, password, token };
}

async function signIn(page, who) {
  await page.goto(`${UI}/login`);
  await page.locator('input').first().fill(who.email);
  await page.locator('input[type=password]').fill(who.password);
  await page.getByRole('button', { name: 'Sign in' }).click();
  await page.waitForURL('**/home', { timeout: 30000 });
}

// Log one set on whichever card is in focus, opening the next exercise first
// when nothing is.
async function logOne(page) {
  const log = page.getByRole('button', { name: 'Log set' });
  if (!(await log.isVisible().catch(() => false))) {
    await page.getByText(/^(Log next set|Start this exercise)$/).first().click();
  }
  const entry = page.locator('.ma-entry').first();
  const inputs = entry.locator('input');
  // Library targets carry reps, never a weight: the lifter picks the load.
  if (!(await inputs.nth(0).inputValue())) await inputs.nth(0).fill('20');
  if (!(await inputs.nth(1).inputValue())) await inputs.nth(1).fill('10');
  const before = await page.getByRole('button', { name: 'Edit set' }).count();
  await page.getByRole('button', { name: 'Log set' }).click();
  await page.getByRole('button', { name: 'Edit set' }).nth(before).waitFor({ timeout: 15000 });
  const cont = page.getByRole('button', { name: 'Continue' });
  if (await cont.isVisible().catch(() => false)) await cont.click();
}

async function finishAndCheckPoints(page, token, label) {
  await page.getByRole('button', { name: 'Finish', exact: true }).click();
  await page.getByRole('button', { name: 'Finish workout' }).click();
  await page.getByText('Workout complete').waitFor({ timeout: 20000 });
  const cont = page.getByRole('button', { name: 'Continue' });
  if (await ok(cont.waitFor({ timeout: 2500 }))) await cont.click();
  const last = (await api('/workouts/sessions?limit=1', 'GET', null, token)).body[0];
  check(`${label}: summary points are the API's (+${last.points_total})`,
    await ok(page.locator('.ma-points-total').getByText(`+${last.points_total}`, { exact: true })
      .waitFor({ timeout: 10000 })));
  return last;
}

const launch = process.env.CHROME_PATH
  ? { executablePath: process.env.CHROME_PATH, headless: true }
  : { channel: 'chrome', headless: true };
const browser = await chromium.launch(launch);

try {
  for (const path of ['athlete', 'bodybuilder', 'powerlifter']) {
    section(`Path: ${path}`);
    const who = await account(path);
    const ctx = await browser.newContext({ viewport: { width: 390, height: 860 }, deviceScaleFactor: 2,
      isMobile: true, hasTouch: true });
    const page = await ctx.newPage();
    const errors = [];
    page.on('pageerror', (e) => errors.push(String(e)));
    await signIn(page, who);

    // --- What the Library leads with -------------------------------------
    const home = (await api('/library/home', 'GET', null, who.token)).body;
    await page.goto(`${UI}/library`);
    await page.locator('.ma-shelf .ma-program-card').first().waitFor({ timeout: 20000 });
    const shownPrograms = await page.locator('.ma-shelf .ma-program-card').evaluateAll(
      (cards) => cards.map((c) => c.getAttribute('data-program')));
    check('recommended programs are the server\'s, in its order',
      JSON.stringify(shownPrograms) === JSON.stringify(home.recommended_programs.map((p) => p.slug)),
      `${shownPrograms} vs ${home.recommended_programs.map((p) => p.slug)}`);
    check('every one is for this path', home.recommended_programs.every((p) => p.category === path && p.recommended));
    const shownWorkouts = await page.locator('.ma-recommended-workouts .ma-workout-card').evaluateAll(
      (rows) => rows.map((r) => r.getAttribute('data-workout')));
    check('recommended workouts are the server\'s, in its order',
      JSON.stringify(shownWorkouts) === JSON.stringify(home.recommended_workouts.map((w) => w.slug)));
    check('the other two paths are offered',
      (await page.locator('.ma-other-path').count()) === 2);
    const heights = await page.locator('.ma-workout-card').evaluateAll((rows) =>
      rows.map((r) => r.getBoundingClientRect().height));
    check('workout rows are at least 48 px tall', heights.length > 0 && heights.every((h) => h >= 48),
      heights.join(','));
    await page.screenshot({ path: join(OUT, `${path}-01-home.png`), fullPage: true });

    // --- Open a workout, start it ------------------------------------------
    const workout = home.recommended_workouts[0];
    await page.locator(`.ma-workout-card[data-workout="${workout.slug}"]`).click();
    await page.waitForURL(`**/library/workout/${workout.slug}`, { timeout: 15000 });
    await page.locator('.ma-library-exercise').first().waitFor({ timeout: 15000 });
    check('the workout lists its exercises with targets',
      (await page.locator('.ma-library-exercise').count()) === workout.exercise_count
      && await page.getByText(/\d+ × \d+(–\d+)? · \d+s rest/).first().isVisible());
    await page.screenshot({ path: join(OUT, `${path}-02-workout.png`), fullPage: true });
    await page.getByRole('button', { name: 'Start workout' }).click();
    await page.waitForURL(/\/train\/?$/, { timeout: 20000 });
    await page.locator('.ma-card').first().waitFor({ timeout: 20000 });
    check('Start opens the workout with every exercise loaded',
      (await page.locator('.ma-card').count()) === workout.exercise_count);

    // --- Log across several exercises, finish ---------------------------------
    for (let card = 0; card < 3; card++) {
      const target = page.locator('.ma-card').nth(card);
      if (!(await target.locator('.ma-entry').count())) {
        await target.getByText(/^(Log next set|Start this exercise)$/).click();
      }
      await logOne(page);
    }
    const live = (await api('/workouts/sessions/active', 'GET', null, who.token)).body.session;
    const logged = live.exercises.filter((e) => e.sets.length > 0).length;
    check('sets logged on three different exercises', logged >= 3, String(logged));
    await page.screenshot({ path: join(OUT, `${path}-03-logging.png`), fullPage: true });
    await finishAndCheckPoints(page, who.token, path);
    await page.getByRole('button', { name: 'Done', exact: true }).click();

    // --- Follow a program (once) ----------------------------------------------
    if (path === 'powerlifter') {
      await page.goto(`${UI}/library/program/linear-strength-base`);
      await page.getByRole('button', { name: 'Follow program' }).click();
      const next = page.getByRole('button', { name: /^Start next: / });
      check('following offers the next workout', await ok(next.waitFor({ timeout: 15000 })));
      await page.screenshot({ path: join(OUT, `${path}-04-program.png`), fullPage: true });
      await next.click();
      await page.waitForURL(/\/train\/?$/, { timeout: 20000 });
      await page.locator('.ma-card').first().waitFor({ timeout: 20000 });
      await logOne(page);
      await finishAndCheckPoints(page, who.token, 'program day');
      await page.getByRole('button', { name: 'Done', exact: true }).click();
      await page.goto(`${UI}/library`);
      const card = page.locator('.ma-your-program');
      check('"Your program" sits on top and has moved on',
        await ok(card.getByText('Week 1 · Day 3').waitFor({ timeout: 15000 })));
      check('its Start is the only accent-filled button',
        (await page.locator('.ma-button-primary:visible').count()) === 1);
      await page.screenshot({ path: join(OUT, `${path}-05-your-program.png`), fullPage: true });
    }

    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
    check('no horizontal overflow', overflow <= 1, `${overflow}px`);
    check('no uncaught errors', errors.length === 0, errors.slice(0, 3).join(' | '));
    await ctx.close();
  }

  // --- No path set --------------------------------------------------------------
  section('No path set');
  const who = await account('');
  const ctx = await browser.newContext({ viewport: { width: 390, height: 860 }, deviceScaleFactor: 2 });
  const page = await ctx.newPage();
  await signIn(page, who);
  await page.goto(`${UI}/library`);
  check('a choose-your-path prompt appears',
    await ok(page.getByRole('button', { name: 'Choose your path' }).waitFor({ timeout: 20000 })));
  check('all three paths are offered, with equal weight', (await page.locator('.ma-other-path').count()) === 3);
  await page.screenshot({ path: join(OUT, 'none-01-home.png'), fullPage: true });
  await page.getByRole('button', { name: 'Choose your path' }).click();
  await page.locator('.ma-path-card[data-path="bodybuilder"]').click();
  check('picking a path fills "Recommended for you"',
    await ok(page.getByText('Recommended for you').waitFor({ timeout: 15000 })));
  await ctx.close();
} catch (err) {
  failed.push(`aborted: ${err.message.split('\n')[0]}`);
  console.log('  ABORT', err.message.split('\n').slice(0, 6).join('\n'));
} finally {
  await browser.close();
}

console.log(`\n${failed.length ? `${failed.length} FAILED` : 'ALL PASSED'} (${passed} passed) - screenshots in ${OUT}`);
for (const f of failed) console.log('  -', f);
process.exit(failed.length ? 1 : 0);
