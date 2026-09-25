// Duels and the activity feed, driven in a real browser against a RUNNING stack.
//
//   docker compose up -d && scripts/dev.sh web
//   cd scripts/e2e && node duels_e2e.mjs [screenshot-dir]
//
// Two accounts in one party: one challenges the other, the other accepts, and
// both see the feed. Then a rival duel, which needs nobody. Exercises the
// websocket events and the client-side state the pytest suite cannot reach.

import { mkdirSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { chromium } from 'playwright-core';

const API = process.env.METALARM_API || 'http://localhost:8000/api/v1';
const UI = process.env.METALARM_UI || 'http://localhost:3000';
const OUT = process.argv[2] || join(tmpdir(), 'metalarm-duels');
mkdirSync(OUT, { recursive: true });

const password = 'e2e-test-passphrase';
const stamp = Date.now();
const alice = `duel-a-${stamp}@metalarm.dev`;
const bob = `duel-b-${stamp}@metalarm.dev`;

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

async function signUp(email, name) {
  const r = await api('/auth/signup', 'POST', { email, password, display_name: name, timezone: 'UTC' });
  if (r.status !== 201) {
    console.error(`signup failed (${r.status}). If it is 429: scripts/dev.sh unlimit`);
    process.exit(1);
  }
  const login = await api('/auth/login', 'POST', { email, password });
  return login.body.access_token;
}

async function signIn(page, email) {
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
  section('Two lifters in one party');
  const aliceToken = await signUp(alice, 'Alice');
  const bobToken = await signUp(bob, 'Bob');
  const party = await api('/parties', 'POST', { name: 'Duellists' }, aliceToken);
  check('party created', party.status === 201, JSON.stringify(party.body));
  const joined = await api('/parties/join', 'POST', { invite_code: party.body.invite_code }, bobToken);
  check('second lifter joined', joined.status === 200, JSON.stringify(joined.body));

  const context = await browser.newContext({ viewport: { width: 420, height: 900 } });
  const page = await context.newPage();
  const errors = [];
  page.on('pageerror', (e) => errors.push(e.message));

  section('Challenging a party member');
  await signIn(page, alice);
  await page.goto(UI + '/duels');
  await page.getByText('CHALLENGE YOUR RIVAL').waitFor({ timeout: 20000 });
  check('the rival is described as your own pace',
        (await page.getByText('comes from your own recent weeks').count()) > 0);
  // Wait for it: the panel's heading is static, while the member list arrives
  // with the state delta a moment later.
  await page.getByText('OR CHALLENGE SOMEONE IN YOUR PARTY').waitFor({ timeout: 20000 });
  await page.getByText('Bob', { exact: false }).first().waitFor({ timeout: 20000 });
  check('party members are offered', true);

  await page.getByRole('button', { name: 'CHALLENGE', exact: true }).first().click();
  await page.getByText('Waiting for Bob').waitFor({ timeout: 20000 });
  check('the challenge is waiting on the other lifter', true);
  await page.screenshot({ path: `${OUT}/duel-pending.png`, fullPage: true });

  section('Accepting');
  const bobContext = await browser.newContext({ viewport: { width: 420, height: 900 } });
  const bobPage = await bobContext.newPage();
  bobPage.on('pageerror', (e) => errors.push(e.message));
  await signIn(bobPage, bob);
  await bobPage.goto(UI + '/duels');
  await bobPage.getByText('Alice challenged you').waitFor({ timeout: 20000 });
  check('the challenge reaches the other lifter', true);
  await bobPage.getByRole('button', { name: 'ACCEPT' }).click();
  await bobPage.getByText('RUNNING').waitFor({ timeout: 20000 });
  check('accepting starts it', true);
  await bobPage.screenshot({ path: `${OUT}/duel-running.png`, fullPage: true });

  section('The rival');
  await page.goto(UI + '/duels');
  await page.getByText('CHALLENGE YOUR RIVAL').click();
  await page.getByText('YOUR RIVAL').first().waitFor({ timeout: 20000 });
  check('a rival duel starts immediately', true);
  check('the rival has no account', (await page.getByText('YOUR RIVAL').count()) > 0);
  await page.screenshot({ path: `${OUT}/duel-rival.png`, fullPage: true });

  section('The feed');
  // A finished workout is a feed event; drive it through the API, since the
  // workout UI is covered by workout_e2e.mjs.
  const session = await api('/workouts/sessions', 'POST', {}, bobToken);
  const exercises = await api('/exercises?limit=1', 'GET', undefined, bobToken);
  const first = (exercises.body.items || exercises.body)[0];
  await api(`/workouts/sessions/${session.body.id}/sets`, 'POST',
            { exercise_id: first.id, weight_kg: 60, reps: 8 }, bobToken);
  const finished = await api(`/workouts/sessions/${session.body.id}/finish`, 'POST', undefined, bobToken);
  check('workout finished', finished.status === 200, JSON.stringify(finished.body).slice(0, 120));

  await page.goto(UI + '/duels');
  await page.getByText('ACTIVITY').waitFor({ timeout: 20000 });
  await page.waitForTimeout(1200);
  const feedText = await page.locator('body').innerText();
  check("a party member's workout reaches the feed", /Bob/.test(feedText), feedText.slice(0, 200));
  await page.screenshot({ path: `${OUT}/duel-feed.png`, fullPage: true });

  check('no uncaught errors', errors.length === 0, errors.slice(0, 3).join(' | '));
  await context.close();
  await bobContext.close();
} catch (err) {
  failed.push(`aborted: ${err.message.split('\n')[0]}`);
  console.log('  ABORT', err.message.split('\n')[0]);
} finally {
  await browser.close();
}

console.log(`\n${failed.length ? `${failed.length} FAILED` : 'ALL PASSED'} (${passed} passed) - screenshots in ${OUT}`);
for (const f of failed) console.log('  -', f);
process.exit(failed.length ? 1 : 0);
