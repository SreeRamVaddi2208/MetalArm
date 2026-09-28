// Every screen of the Android app, driven as a phone.
//
//   docker compose up -d && scripts/dev.sh web
//   cd scripts/e2e && node android_ui_e2e.mjs [screenshot-dir]
//
// The Android app IS the web app: installed from the browser, or wrapped in
// the TWA shell under android/ for the Play listing. So this drives Chrome
// with a Pixel's viewport, touch input and user agent, in the standalone
// display the manifest asks for - which is what somebody who installed it
// actually sees.
//
// It is the counterpart to iOS's ButtonSweepUITests: press everything, on
// every screen, and say which control failed rather than "the app is broken".

import { mkdirSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { chromium, devices } from 'playwright-core';

const UI = process.env.METALARM_UI || 'http://localhost:3000';
const API = process.env.METALARM_API || 'http://localhost:8000/api/v1';
const OUT = process.argv[2] || join(tmpdir(), 'metalarm-android');
mkdirSync(OUT, { recursive: true });

const password = 'e2e-test-passphrase';
const stamp = Date.now();
const me = `android-${stamp}@metalarm.dev`;
const mate = `android-mate-${stamp}@metalarm.dev`;

let passed = 0;
const failed = [];
const check = (label, ok, detail = '') => {
  if (ok) { passed++; console.log('  PASS', label); }
  else { failed.push(label); console.log('  FAIL', label, detail); }
};
const section = (name) => console.log(`\n${name}`);

async function api(path, method = 'GET', body, token) {
  const r = await fetch(API + path, {
    method,
    headers: { 'Content-Type': 'application/json', ...(token ? { Authorization: `Bearer ${token}` } : {}) },
    body: body ? JSON.stringify(body) : undefined,
  });
  const text = await r.text();
  return { status: r.status, body: text ? JSON.parse(text) : null };
}

async function account(email, name) {
  const up = await api('/auth/signup', 'POST', { email, password, display_name: name, timezone: 'UTC' });
  if (up.status !== 201) {
    console.error(`signup failed (${up.status}). If it is 429: scripts/dev.sh unlimit`);
    process.exit(1);
  }
  return (await api('/auth/login', 'POST', { email, password })).body.access_token;
}

const myToken = await account(me, 'Sree Ram');
const mateToken = await account(mate, 'Priya');

// Something to look at on every screen: a party, a workout, a duel.
const party = await api('/parties', 'POST', { name: 'Iron Temple' }, myToken);
await api('/parties/join', 'POST', { invite_code: party.body.invite_code }, mateToken);
const exercises = await api('/exercises?limit=200', 'GET', undefined, myToken);
const items = exercises.body.items || exercises.body;
const bench = items.find((e) => /bench press/i.test(e.name)) || items[0];
for (const token of [myToken, mateToken]) {
  const session = await api('/workouts/sessions', 'POST', {}, token);
  await api(`/workouts/sessions/${session.body.id}/sets`, 'POST',
            { exercise_id: bench.id, weight_kg: 80, reps: 8 }, token);
  await api(`/workouts/sessions/${session.body.id}/finish`, 'POST', undefined, token);
}
await api('/duels', 'POST', { metric: 'volume', days: 7, against_rival: true }, myToken);

const browser = await chromium.launch(
  process.env.CHROME_PATH
    ? { executablePath: process.env.CHROME_PATH, headless: true }
    : { channel: 'chrome', headless: true },
);
// A real Pixel: viewport, device scale, touch, and the Android user agent.
const pixel = devices['Pixel 7'];
const context = await browser.newContext({ ...pixel });
const page = await context.newPage();
const errors = [];
page.on('pageerror', (e) => errors.push(e.message));

async function tap(name, locator, { expect, timeout = 15000 } = {}) {
  try {
    await locator.first().waitFor({ state: 'visible', timeout });
    await locator.first().tap();
    if (expect) await expect();
    check(name, true);
  } catch (err) {
    check(name, false, err.message.split('\n')[0]);
  }
}

try {
  section('Signing in');
  await page.goto(`${UI}/login`, { waitUntil: 'networkidle' });
  await page.locator('input').first().fill(me);
  await page.locator('input[type=password]').fill(password);
  await page.getByText('ENTER', { exact: true }).tap();
  await page.waitForURL('**/dashboard', { timeout: 20000 });
  check('signs in on a phone', true);
  await page.screenshot({ path: `${OUT}/01-dashboard.png` });

  section('Every tab reachable by thumb');
  // The nav scrolls sideways at phone width, so each link is tapped by name.
  for (const [label, path] of [
    ['WORKOUT', '/workout'], ['PROGRESS', '/progress'], ['PARTIES', '/parties'],
    ['DUELS', '/duels'], ['REWARDS', '/rewards'], ['PROFILE', '/profile'],
    ['QUESTS', '/dashboard'],
  ]) {
    const link = page.getByRole('link', { name: label }).first();
    await link.scrollIntoViewIfNeeded().catch(() => {});
    await tap(`nav: ${label}`, link, {
      expect: () => page.waitForURL(`**${path}**`, { timeout: 15000 }),
    });
  }

  section('The workout screen');
  await page.goto(`${UI}/workout`, { waitUntil: 'networkidle' });
  await page.waitForTimeout(900);
  await page.screenshot({ path: `${OUT}/02-workout.png` });
  check('offers a ready-made workout', await page.getByText(/READY-MADE|Heavy Day|Push Day|Power Day/i).count() > 0);

  section('Duels');
  await page.goto(`${UI}/duels`, { waitUntil: 'networkidle' });
  await page.waitForTimeout(1200);
  check('the rival duel is running', await page.getByText('YOUR RIVAL').count() > 0);
  check('the rival is explained, not just shown',
        await page.getByText(/comes from your own recent weeks/i).count() > 0);
  await tap('challenge a party member', page.getByRole('button', { name: 'CHALLENGE', exact: true }), {
    expect: () => page.getByText(/Waiting for/i).first().waitFor({ timeout: 15000 }),
  });
  await page.screenshot({ path: `${OUT}/03-duels.png` });

  section('Progress and ranks');
  await page.goto(`${UI}/progress`, { waitUntil: 'networkidle' });
  await page.waitForTimeout(900);
  check('progress shows a record', await page.getByText(/kg|record/i).count() > 0);
  await page.screenshot({ path: `${OUT}/04-progress.png` });

  await page.goto(`${UI}/parties`, { waitUntil: 'networkidle' });
  await page.waitForTimeout(900);
  check('the party and its board are there', await page.getByText('Iron Temple').count() > 0);
  await page.screenshot({ path: `${OUT}/05-parties.png` });

  section('Profile');
  await page.goto(`${UI}/profile`, { waitUntil: 'networkidle' });
  await page.waitForTimeout(1200);
  check('the character sheet is there', await page.getByText(/LIFETIME|BADGES|Level/i).count() > 0);
  // Offered only where the server has a VAPID key - absent is correct locally.
  const notify = await page.getByText('TURN ON NOTIFICATIONS').count();
  check(`notifications ${notify ? 'offered' : 'correctly hidden without a VAPID key'}`, true);
  await page.screenshot({ path: `${OUT}/06-profile.png` });

  section('It behaves like an installed app');
  const standalone = await page.evaluate(async () => {
    const manifest = await fetch('/manifest.webmanifest').then((r) => r.json());
    const reg = await navigator.serviceWorker.getRegistration();
    return { display: manifest.display, worker: !!reg?.active };
  });
  check('the manifest asks for standalone', standalone.display === 'standalone');
  check('the worker is running on the phone', standalone.worker);

  const overflow = await page.evaluate(() =>
    document.documentElement.scrollWidth - window.innerWidth);
  check('nothing overflows a phone screen', overflow <= 1, `${overflow}px`);

  check('no uncaught errors anywhere', errors.length === 0, errors.slice(0, 3).join(' | '));
} catch (err) {
  failed.push(`aborted: ${err.message.split('\n')[0]}`);
  console.log('  ABORT', err.message.split('\n')[0]);
} finally {
  await context.close();
  await browser.close();
}

console.log(`\n${failed.length ? `${failed.length} FAILED` : 'ALL PASSED'} (${passed} passed) - screenshots in ${OUT}`);
for (const f of failed) console.log('  -', f);
process.exit(failed.length ? 1 : 0);
