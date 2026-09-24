// The rank-up celebration, driven in a real browser against a RUNNING stack.
//
//   docker compose up -d
//   cd scripts/e2e && npm install && node rank_up_e2e.mjs [screenshot-dir]
//
// Plays every promotion through ?celebrate=<rank> (the dev trigger, see
// QuestState.preview_celebration) and checks what the tier table promises:
// the particle count, the ornament, that the overlay refuses to be dismissed
// until it has played, and that it always becomes dismissible afterwards.
// Then the same thing with Reduce Motion, which must strip the motion and open
// immediately without losing what happened.
//
// This is the only check that runs the CSS and the script for real - pytest
// covers the tier table, smoke_test.py the served stylesheet.

import { mkdirSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { chromium } from 'playwright-core';

const API = process.env.METALARM_API || 'http://localhost:8000/api/v1';
const UI = process.env.METALARM_UI || 'http://localhost:3000';
const OUT = process.argv[2] || join(tmpdir(), 'metalarm-rankup');
mkdirSync(OUT, { recursive: true });

const email = `rankup-${Date.now()}@metalarm.dev`;
const password = 'e2e-test-passphrase';

// Mirrors frontend/metalarm/rank_tiers.py. Duplicated on purpose: if the table
// changes, this test should have to be updated too.
const TIERS = [
  { rank: 'D', title: 'NOVICE', particles: 16, duration: 1700, ornament: null },
  { rank: 'C', title: 'INTERMEDIATE', particles: 36, duration: 2300, ornament: '.lf-laurel' },
  { rank: 'B', title: 'ADVANCED', particles: 60, duration: 2900, ornament: '.lf-gem' },
  { rank: 'A', title: 'ELITE', particles: 66, duration: 3600, ornament: '.lf-crown' },
  { rank: 'S', title: 'WORLD CLASS', particles: 72, duration: 4400, ornament: '.lf-filigree' },
];

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

async function signIn(page) {
  await page.goto(UI + '/login');
  await page.locator('input').first().fill(email);
  await page.locator('input[type=password]').fill(password);
  await page.getByText('ENTER', { exact: true }).click();
  await page.waitForURL('**/dashboard', { timeout: 20000 });
}

const launchOptions = process.env.CHROME_PATH
  ? { executablePath: process.env.CHROME_PATH, headless: true }
  : { channel: 'chrome', headless: true };
const browser = await chromium.launch(launchOptions);

try {
  section('Account');
  const signup = await api('/auth/signup', 'POST', { email, password, display_name: 'Rank Up', timezone: 'UTC' });
  check('signup via API', signup.status === 201, JSON.stringify(signup.body));

  const context = await browser.newContext({ viewport: { width: 400, height: 860 } });
  const page = await context.newPage();
  const errors = [];
  page.on('pageerror', (e) => errors.push(e.message));
  await signIn(page);

  for (const tier of TIERS) {
    section(`Promotion into ${tier.title}`);
    await page.goto(`${UI}/dashboard?celebrate=${tier.rank}`);
    const veil = page.locator('.lf-celebrate');
    await veil.waitFor({ state: 'visible', timeout: 15000 });

    check(`${tier.rank}: the tier is named`, (await page.locator('.lf-badge.lf-rank').innerText()).trim() === tier.title,
          await page.locator('.lf-badge.lf-rank').innerText());
    check(`${tier.rank}: throws ${tier.particles} particles`,
          (await page.locator('.lf-celebrate .lf-p').count()) === tier.particles,
          String(await page.locator('.lf-celebrate .lf-p').count()));
    if (tier.ornament) {
      check(`${tier.rank}: wears its ${tier.ornament.slice(1)}`, (await page.locator(tier.ornament).count()) > 0);
    } else {
      check('D: no ornament on the first rung', (await page.locator('.lf-laurel').count()) === 0);
    }
    check(`${tier.rank}: duration is the tier's`,
          (await veil.getAttribute('data-ma-duration')) === String(tier.duration),
          await veil.getAttribute('data-ma-duration'));

    // Not dismissible while it plays: the click must not reach the veil.
    check(`${tier.rank}: ignores taps mid-sequence`, (await veil.getAttribute('data-ma-ready')) === null);
    await page.mouse.click(10, 10);
    check(`${tier.rank}: still up after a tap`, await veil.isVisible());

    await page.waitForTimeout(Math.round(tier.duration * 0.55));
    await page.screenshot({ path: `${OUT}/rankup-${tier.rank}-${tier.title.replace(/\s+/g, '-').toLowerCase()}.png` });

    // ...and always dismissible once it has played.
    await veil.locator('..').page().waitForFunction(
      () => document.querySelector('.lf-celebrate')?.hasAttribute('data-ma-ready'),
      null, { timeout: tier.duration + 6000 });
    check(`${tier.rank}: opens up when it is done`, (await veil.getAttribute('data-ma-ready')) === '1');
    const counted = (await page.locator('.lf-count').getAttribute('data-ma-count')) || '';
    check(`${tier.rank}: the level counter ticked to its end`, counted === '15', counted);

    await page.getByText('CONTINUE', { exact: true }).click();
    await veil.waitFor({ state: 'detached', timeout: 10000 });
    check(`${tier.rank}: CONTINUE dismisses it`, (await page.locator('.lf-celebrate').count()) === 0);
  }

  section('Reduce Motion');
  const calm = await browser.newContext({ viewport: { width: 400, height: 860 }, reducedMotion: 'reduce' });
  const calmPage = await calm.newPage();
  calmPage.on('pageerror', (e) => errors.push(e.message));
  await signIn(calmPage);
  await calmPage.goto(`${UI}/dashboard?celebrate=S`);
  const calmVeil = calmPage.locator('.lf-celebrate');
  await calmVeil.waitFor({ state: 'visible', timeout: 15000 });
  // The particles are in the DOM but display:none, and nothing waits.
  check('reduced motion hides the burst', !(await calmPage.locator('.lf-celebrate .lf-p').first().isVisible()));
  check('reduced motion still names the tier',
        (await calmPage.locator('.lf-badge.lf-rank').innerText()).trim() === 'WORLD CLASS');
  check('reduced motion still reads the promotion',
        (await calmPage.locator('.lf-ladder').innerText()).includes('World Class'));
  await calmPage.waitForFunction(
    () => document.querySelector('.lf-celebrate')?.hasAttribute('data-ma-ready'), null, { timeout: 5000 });
  check('reduced motion opens immediately', (await calmVeil.getAttribute('data-ma-ready')) === '1');
  await calmPage.screenshot({ path: `${OUT}/rankup-reduced-motion.png` });
  await calm.close();

  check('no uncaught errors during any celebration', errors.length === 0, errors.slice(0, 3).join(' | '));
  await context.close();
} catch (err) {
  failed.push(`aborted: ${err.message.split('\n')[0]}`);
  console.log('  ABORT', err.message.split('\n')[0]);
} finally {
  await browser.close();
}

console.log(`\n${failed.length ? `${failed.length} FAILED` : 'ALL PASSED'} (${passed} passed) - screenshots in ${OUT}`);
for (const f of failed) console.log('  -', f);
process.exit(failed.length ? 1 : 0);
