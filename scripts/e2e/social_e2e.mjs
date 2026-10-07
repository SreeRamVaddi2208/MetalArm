// Overhaul Gate 4: two accounts follow each other, see each other's workouts,
// react, and duel - through the UI, one browser each.
//
//   node social_e2e.mjs [screenshot-dir]
//
// Against a RUNNING stack. Avery and Blake are fresh accounts:
//   Blake finishes a followers-only workout and a private one (API);
//   Avery finds Blake in Explore -> People and follows;
//   Avery's Home feed shows Blake's followers-only workout, never the private one,
//   with its numbers; Avery spots it;
//   Blake's bell shows the follow and the spot; Blake follows back from the
//   notification;
//   Avery challenges Blake (friends, no party) and Blake accepts;
//   the friends leaderboard has both. Screenshots at 375 and 430.

import { mkdirSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { chromium } from 'playwright-core';

const API = process.env.METALARM_API || 'http://localhost:8000/api/v1';
const UI = process.env.METALARM_UI || 'http://localhost:3000';
const OUT = process.argv[2] || join(tmpdir(), 'metalarm-social-e2e');

let passed = 0;
const failed = [];
function check(label, ok, detail = '') {
  if (ok) { passed++; console.log('  PASS', label); }
  else { failed.push(label); console.log('  FAIL', label, detail); }
}
const section = (name) => console.log(`\n${name}`);
const seen = (locator, timeout = 15000) => locator.first().waitFor({ timeout }).then(() => true).catch(() => false);

async function api(path, method = 'GET', body, token) {
  const r = await fetch(API + path, {
    method,
    headers: { 'Content-Type': 'application/json', ...(token ? { Authorization: `Bearer ${token}` } : {}) },
    body: body ? JSON.stringify(body) : undefined,
  });
  const text = await r.text();
  return { status: r.status, body: text ? JSON.parse(text) : null };
}

async function account(name, email, password) {
  const me = (await api('/auth/signup', 'POST', { email, password, display_name: name, timezone: 'UTC' })).body;
  const token = (await api('/auth/login', 'POST', { email, password })).body.access_token;
  return { id: me.id, token, email, password, name };
}

async function workout(who, name, visibility) {
  const bench = (await api('/exercises/browse?q=Barbell%20Bench%20Press&limit=5', 'GET', null, who.token)).body
    .items.find((e) => e.name === 'Barbell Bench Press').id;
  const s = (await api('/workouts/sessions', 'POST', { name, visibility }, who.token)).body;
  for (let i = 0; i < 3; i++) {
    await api(`/workouts/sessions/${s.id}/sets`, 'POST', { exercise_id: bench, weight: 100, unit: 'kg', reps: 5 }, who.token);
  }
  await api(`/workouts/sessions/${s.id}/finish`, 'POST', null, who.token);
  return s.id;
}

async function signIn(ctx, who) {
  const page = await ctx.newPage();
  await page.goto(`${UI}/login`);
  await page.locator('input').first().fill(who.email);
  await page.locator('input[type=password]').fill(who.password);
  await page.getByText('ENTER', { exact: true }).click();
  await page.waitForURL('**/home', { timeout: 30000 });
  return page;
}

const launch = process.env.CHROME_PATH
  ? { executablePath: process.env.CHROME_PATH, headless: true }
  : { channel: 'chrome', headless: true };
const browser = await chromium.launch(launch);

try {
  const stamp = Date.now().toString(36);
  const avery = await account(`Avery ${stamp}`, `avery-${stamp}@metalarm.dev`, 'gate-four-passphrase');
  const blake = await account(`Blake ${stamp}`, `blake-${stamp}@metalarm.dev`, 'gate-four-passphrase');
  await workout(blake, 'Blake private', 'private');
  await workout(blake, 'Blake push day', 'followers');

  for (const width of [375, 430]) {
    const dir = join(OUT, String(width));
    mkdirSync(dir, { recursive: true });
    section(`Gate 4 at ${width}px`);
    const viewport = { width, height: width === 375 ? 812 : 932 };
    const ctxA = await browser.newContext({ viewport, deviceScaleFactor: 2, isMobile: true, hasTouch: true });
    const ctxB = await browser.newContext({ viewport, deviceScaleFactor: 2, isMobile: true, hasTouch: true });
    const errors = [];
    const a = await signIn(ctxA, avery);
    a.on('pageerror', (e) => errors.push(String(e)));
    const overflow = async (page, name) => {
      const wider = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
      check(`${name}: no horizontal overflow`, wider <= 1, `${wider}px`);
    };

    if (width === 375) {
      // --- Find and follow ------------------------------------------------------
      check('Home: an empty feed asks you to find friends', await seen(a.getByText('Follow friends to see their workouts')));
      await a.screenshot({ path: join(dir, '01-home-empty.png'), fullPage: true });
      await a.goto(`${UI}/explore?tab=people`);
      await a.getByPlaceholder('Search people by name').fill(`Blake ${stamp}`);
      const row = a.locator('.ma-person').filter({ hasText: `Blake ${stamp}` });
      await row.waitFor({ timeout: 15000 });
      check('People search finds Blake', true);
      await row.getByText('Follow', { exact: true }).click();
      check('the button turns to Following', await seen(row.getByText('Following', { exact: true })));
      await a.screenshot({ path: join(dir, '02-people.png'), fullPage: true });

      // --- The feed ---------------------------------------------------------------
      await a.goto(`${UI}/home`);
      const card = a.locator('.ma-feed-card').filter({ hasText: 'Blake push day' });
      check("Avery's feed shows Blake's followers-only workout", await seen(card));
      check('never the private one', (await a.getByText('Blake private').count()) === 0);
      check('the card carries its numbers', (await card.innerText()).includes('1,500 kg') && (await card.innerText()).includes('3 × Barbell Bench Press'));
      await card.getByRole('button', { name: 'Spotted' }).click();
      check('spotting counts', await seen(card.getByRole('button', { name: 'Spotted' }).getByText('1', { exact: true })));
      await a.screenshot({ path: join(dir, '03-feed.png'), fullPage: true });
      await overflow(a, 'Home feed');

      // --- Blake hears about it, follows back ------------------------------------
      const b = await signIn(ctxB, blake);
      b.on('pageerror', (e) => errors.push(String(e)));
      check("Blake's bell has unread notifications",
        await seen(b.getByRole('button', { name: 'Notifications' }).locator('div').last(), 8000)
          .then(() => true).catch(() => false));
      await b.goto(`${UI}/notifications`);
      check('Blake is told Avery followed', await seen(b.getByText(`Avery ${stamp} followed you`)));
      check('and that Avery spotted the workout', await seen(b.getByText(`Avery ${stamp} spotted your workout Blake push day`)));
      await b.screenshot({ path: join(dir, '04-notifications.png'), fullPage: true });
      await b.getByText(`Avery ${stamp} followed you`).click();
      await b.waitForURL('**/u/**', { timeout: 15000 });
      await b.getByText('Follow back', { exact: true }).click();
      check('following back makes them friends', await seen(b.getByText('Friends: you follow each other.')));
      await b.screenshot({ path: join(dir, '05-profile.png'), fullPage: true });

      // --- Duel ---------------------------------------------------------------------
      await a.goto(`${UI}/duels`);
      const challengeRow = a.getByText(`Blake ${stamp}`, { exact: true }).first().locator('xpath=..');
      await challengeRow.getByRole('button', { name: 'CHALLENGE', exact: true }).click();
      await a.getByText(`CHALLENGE BLAKE ${stamp}`.toUpperCase()).waitFor({ timeout: 15000 });
      await a.locator('[role=button][aria-disabled=false]').filter({ hasText: /^Volume/ }).first().click();
      let challenged = false;
      for (let i = 0; i < 20 && !challenged; i++) {
        await a.waitForTimeout(500);
        const sent = await api('/duels', 'GET', null, avery.token);
        challenged = (sent.body.pending || []).some((d) => d.opponent && d.opponent.user_id === blake.id);
      }
      check('Avery challenged Blake - friends, no shared party', challenged);
      await b.goto(`${UI}/duels`);
      await b.getByRole('button', { name: 'ACCEPT', exact: true }).first().click();
      await b.waitForTimeout(1500);
      const live = await api('/duels', 'GET', null, blake.token);
      check('Blake accepted - the duel is live', (live.body.active || []).length === 1);
      await b.screenshot({ path: join(dir, '06-duel.png'), fullPage: true });

      // --- Leaderboard ----------------------------------------------------------------
      await a.goto(`${UI}/home`);
      await a.getByRole('button', { name: 'Switch view' }).click();
      await a.getByText('Leaderboard', { exact: true }).click();
      check('the friends leaderboard has both, Blake first',
        await seen(a.locator('a[href^="/u/"]').first().filter({ hasText: `Blake ${stamp}` })));
      await a.screenshot({ path: join(dir, '07-leaderboard.png'), fullPage: true });
      await b.close();
    } else {
      for (const [path, name] of [['/home', 'Home'], [`/u/${blake.id}`, 'Profile'], ['/notifications', 'Notifications'],
        ['/explore?tab=people', 'People']]) {
        await a.goto(UI + path);
        await a.waitForLoadState('networkidle').catch(() => {});
        await a.waitForTimeout(1200);
        await a.screenshot({ path: join(dir, `${name.toLowerCase()}.png`), fullPage: true });
        await overflow(a, name);
      }
    }
    check('no uncaught errors', errors.length === 0, errors.slice(0, 3).join(' | '));
    await ctxA.close();
    await ctxB.close();
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
