// Reduced motion: with the system setting, or with the app's own (Profile >
// App > Reduce motion), nothing moves.
//
//   node motion_e2e.mjs [screenshot-dir]
//
// Against a RUNNING stack. A fresh account opens the main screens, a sheet,
// and a live workout with a set logged (rest bar, PR banner), and asks the
// browser for every running animation and transition. Allowed: the two that
// only time something out without moving it - the toast's and the PR
// banner's reduced variants (opacity steps, no transform).

import { mkdirSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { chromium } from 'playwright-core';

const API = process.env.METALARM_API || 'http://localhost:8000/api/v1';
const UI = process.env.METALARM_UI || 'http://localhost:3000';
const OUT = process.argv[2] || join(tmpdir(), 'metalarm-motion-e2e');
mkdirSync(OUT, { recursive: true });
const STILL = ['ma-toast-still', 'ma-pr-banner'];

let passed = 0;
const failed = [];
function check(label, ok, detail = '') {
  if (ok) { passed++; console.log('  PASS', label); }
  else { failed.push(label); console.log('  FAIL', label, detail); }
}
async function api(path, method = 'GET', body, token) {
  const r = await fetch(API + path, {
    method,
    headers: { 'Content-Type': 'application/json', ...(token ? { Authorization: `Bearer ${token}` } : {}) },
    body: body ? JSON.stringify(body) : undefined,
  });
  const text = await r.text();
  return { status: r.status, body: text ? JSON.parse(text) : null };
}

// Every animation still running after the page settles, longer than a frame.
async function moving(page) {
  await page.waitForTimeout(600);
  return page.evaluate((still) => document.getAnimations()
    .filter((a) => a.playState === 'running')
    .map((a) => ({ name: a.animationName || a.transitionProperty || 'script',
      ms: Number(a.effect?.getComputedTiming?.().duration) || 0,
      target: a.effect?.target?.className?.toString?.().slice(0, 40) || '' }))
    .filter((a) => a.ms > 1 && !still.includes(a.name))
    .map((a) => `${a.name} ${Math.round(a.ms)}ms on ${a.target}`), STILL);
}

const email = `motion-${Date.now()}@metalarm.dev`;
const password = 'motion-passphrase';
await api('/auth/signup', 'POST', { email, password, display_name: 'Still Life', timezone: 'UTC' });

const launch = process.env.CHROME_PATH
  ? { executablePath: process.env.CHROME_PATH, headless: true }
  : { channel: 'chrome', headless: true };
const browser = await chromium.launch(launch);

async function sweep(label, page) {
  console.log(`\n${label}`);
  for (const path of ['/home', '/train', '/train/exercises', '/progress', '/profile', '/quests', '/design-system']) {
    await page.goto(UI + path);
    await page.waitForLoadState('networkidle').catch(() => {});
    const found = await moving(page);
    check(`${path}: nothing moves`, found.length === 0, found.join(', '));
  }
  // A sheet opening, and a live workout with a set just logged.
  await page.goto(UI + '/train');
  await page.getByRole('button', { name: 'Start empty workout' }).click();
  await page.getByRole('button', { name: 'Add exercise' }).click();
  check('the picker sheet opens without moving', (await moving(page)).length === 0);
  await page.getByPlaceholder('Search exercises…').fill('Barbell Bench Press');
  await page.getByRole('checkbox', { name: 'Barbell Bench Press' }).first().click();
  await page.getByRole('button', { name: /^Add \d+ exercise/ }).click();
  const fields = page.locator('.ma-entry input');
  await fields.first().waitFor({ timeout: 15000 });
  await fields.nth(0).fill('60');
  await fields.nth(1).fill('5');
  await page.getByRole('button', { name: 'Log set' }).click();
  await page.getByRole('button', { name: 'Edit set' }).first().waitFor({ timeout: 15000 });
  const cont = page.getByRole('button', { name: 'Continue' });
  if (await cont.isVisible().catch(() => false)) await cont.click();
  const found = await moving(page);
  check('a live workout with the rest bar up: nothing moves', found.length === 0, found.join(', '));
  await page.screenshot({ path: join(OUT, `${label.split(' ')[0]}-workout.png`) });
  await page.getByRole('button', { name: 'Finish', exact: true }).click();
  await page.getByRole('button', { name: 'Discard workout' }).click();
  await page.getByRole('button', { name: 'Discard', exact: true }).click();
  await page.getByRole('button', { name: 'Start empty workout' }).waitFor({ timeout: 15000 });
}

async function signIn(page) {
  await page.goto(`${UI}/login`);
  await page.locator('input').first().fill(email);
  await page.locator('input[type=password]').fill(password);
  await page.getByRole('button', { name: 'Sign in' }).click();
  await page.waitForURL('**/home', { timeout: 30000 });
}

try {
  // 1. The system setting.
  const sys = await browser.newContext({ viewport: { width: 390, height: 860 }, reducedMotion: 'reduce' });
  const a = await sys.newPage();
  await signIn(a);
  await sweep('system reduced motion', a);
  await sys.close();

  // 2. The app's own setting, with the system setting off.
  const app = await browser.newContext({ viewport: { width: 390, height: 860 }, reducedMotion: 'no-preference' });
  const b = await app.newPage();
  await signIn(b);
  // Control: with motion allowed, the check does see the skeleton shimmer.
  await b.goto(`${UI}/design-system`);
  const control = await moving(b);
  check('control: with motion allowed, the check sees it', control.some((x) => x.startsWith('ma-shimmer')),
    control.join(', '));
  await b.goto(`${UI}/profile`);
  await b.getByRole('switch', { name: 'Reduce motion' }).click();
  await b.waitForTimeout(600);
  check('the switch marks the page at once',
    (await b.evaluate(() => document.documentElement.getAttribute('data-ma-reduce'))) === '1');
  await b.reload();
  await b.waitForTimeout(800);
  check('and it holds across a reload',
    (await b.evaluate(() => document.documentElement.getAttribute('data-ma-reduce'))) === '1');
  await sweep('app setting', b);
  await b.goto(`${UI}/profile`);
  await b.getByRole('switch', { name: 'Reduce motion' }).click();
  await b.waitForTimeout(600);
  check('turning it off restores motion',
    (await b.evaluate(() => document.documentElement.getAttribute('data-ma-reduce'))) === null);
  await app.close();
} catch (err) {
  failed.push(`aborted: ${err.message.split('\n')[0]}`);
  console.log('  ABORT', err.message.split('\n').slice(0, 6).join('\n'));
} finally {
  await browser.close();
}

console.log(`\n${failed.length ? `${failed.length} FAILED` : 'ALL PASSED'} (${passed} passed)`);
for (const f of failed) console.log('  -', f);
process.exit(failed.length ? 1 : 0);
