// Overhaul Gate 5: installable, works offline, logs sets without a signal,
// and the Monthly Summary shows the month as the API counted it.
//
//   node pwa_e2e.mjs <screenshot-dir> <demo-email> <demo-password>
//
// Against a RUNNING stack seeded by scripts/demo/seed_fresh.sh (the demo
// account has last month's workouts). Installability is Chrome's own check
// (CDP Page.getInstallabilityErrors) - what Lighthouse's PWA audit ran on
// before Lighthouse 12 removed the category.

import { mkdirSync, mkdtempSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { chromium } from 'playwright-core';

const API = process.env.METALARM_API || 'http://localhost:8000/api/v1';
const UI = process.env.METALARM_UI || 'http://localhost:3000';
const [OUT, DEMO_EMAIL, DEMO_PASSWORD] = process.argv.slice(2);
if (!DEMO_PASSWORD) { console.error('usage: node pwa_e2e.mjs <out> <demo-email> <demo-password>'); process.exit(2); }
mkdirSync(OUT, { recursive: true });

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

async function signIn(page, email, password) {
  await page.goto(`${UI}/login`);
  await page.locator('input').first().fill(email);
  await page.locator('input[type=password]').fill(password);
  await page.getByRole('button', { name: 'Sign in' }).click();
  await page.waitForURL('**/home', { timeout: 30000 });
}

const launch = process.env.CHROME_PATH
  ? { executablePath: process.env.CHROME_PATH, headless: true }
  : { channel: 'chrome', headless: true };
const browser = await chromium.launch(launch);

try {
  // --- Installable ------------------------------------------------------------
  section('Installable');
  const manifest = await (await fetch(`${UI}/manifest.json`)).json();
  check('the manifest names the app, starts at /home, stands alone',
    manifest.name === 'MetalArm' && manifest.start_url === '/home' && manifest.display === 'standalone');
  for (const icon of manifest.icons) {
    const r = await fetch(UI + icon.src);
    check(`icon ${icon.src} (${icon.sizes}, ${icon.purpose}) is served`, r.ok && (r.headers.get('content-type') || '').startsWith('image/png'));
  }
  const email = `gate5-${Date.now()}@metalarm.dev`;
  const password = 'gate-five-passphrase';
  await api('/auth/signup', 'POST', { email, password, display_name: 'Gate Five', timezone: 'UTC' });
  const token = (await api('/auth/login', 'POST', { email, password })).body.access_token;

  // A real (persistent) profile: Chrome never offers to install from incognito,
  // which is what an ordinary Playwright context is.
  const profile = mkdtempSync(join(tmpdir(), 'metalarm-pwa-'));
  const ctx = await chromium.launchPersistentContext(profile, {
    ...launch, viewport: { width: 390, height: 844 }, deviceScaleFactor: 2,
  });
  const page = ctx.pages()[0] || await ctx.newPage();
  const errors = [];
  page.on('pageerror', (e) => errors.push(String(e)));
  await signIn(page, email, password);
  const controlled = await page.evaluate(async () => {
    const reg = await navigator.serviceWorker.ready;
    return !!reg.active;
  }).catch(() => false);
  check('the service worker is active', controlled);
  const cdp = await ctx.newCDPSession(page);
  const { installabilityErrors } = await cdp.send('Page.getInstallabilityErrors');
  check('Chrome finds no installability errors', installabilityErrors.length === 0, JSON.stringify(installabilityErrors));
  const { url: manifestUrl, errors: manifestErrors } = await cdp.send('Page.getAppManifest');
  check('Chrome parses the manifest cleanly', manifestUrl.endsWith('/manifest.json') && manifestErrors.length === 0,
    JSON.stringify(manifestErrors));

  // --- Offline set logging ---------------------------------------------------------
  section('Logging a set with no connection');
  const bench = (await api('/exercises/browse?q=Barbell%20Bench%20Press&limit=5', 'GET', null, token)).body
    .items.find((e) => e.name === 'Barbell Bench Press').id;
  const routine = (await api('/routines', 'POST', { name: 'Offline day', exercises: [
    { exercise_id: bench, target_sets: 3, target_reps: 5, target_weight_kg: 80 }] }, token)).body;
  const session = (await api('/workouts/sessions', 'POST', { routine_id: routine.id }, token)).body;
  await page.goto(`${UI}/train`);
  const card = page.locator('.ma-card').first();
  await card.waitFor({ timeout: 20000 });
  await page.waitForTimeout(1500);       // let the worker cache this page
  await ctx.setOffline(true);
  await page.waitForTimeout(500);
  check('going offline says so', await seen(page.locator('#ma-offline[data-ma-online="0"]'), 5000));
  const logButton = card.getByRole('button', { name: 'Log set' });
  await logButton.click();
  await logButton.click();
  await page.waitForTimeout(600);
  const waiting = await page.locator('#ma-offline').getAttribute('data-ma-count');
  check('two taps queue two sets', waiting === '2 sets waiting for a connection', waiting);
  check('the card shows them as queued', (await card.getAttribute('data-ma-queued')) === '2 queued - sent when you reconnect');
  await page.screenshot({ path: join(OUT, '01-offline-queued.png'), fullPage: true });
  const offlineReload = await ctx.newPage();
  await offlineReload.goto(`${UI}/home`).catch(() => {});
  check('an app page still opens offline (from the cache)',
    (await offlineReload.title()).includes('MetalArm'), await offlineReload.title());
  await offlineReload.close();

  await ctx.setOffline(false);
  const logged = await card.getByRole('button', { name: 'Edit set' }).nth(1).waitFor({ timeout: 30000 })
    .then(() => true).catch(() => false);
  check('back online, both sets are logged and shown', logged);
  const live = (await api(`/workouts/sessions/${session.id}`, 'GET', null, token)).body;
  const sets = live.exercises.flatMap((e) => e.sets);
  check('the server has exactly two sets, 80 kg x 5', sets.length === 2 && sets.every((s) => s.weight_kg === 80 && s.reps === 5),
    JSON.stringify(sets.map((s) => [s.weight_kg, s.reps])));
  check('and the queue is empty', (await page.evaluate(() => localStorage.getItem('ma_offline_sets'))) === '[]');
  await page.waitForTimeout(5000);   // one more flush tick: nothing doubles
  const again = (await api(`/workouts/sessions/${session.id}`, 'GET', null, token)).body;
  check('nothing is logged twice', again.exercises.flatMap((e) => e.sets).length === 2);
  await page.screenshot({ path: join(OUT, '02-back-online.png'), fullPage: true });
  check('no uncaught errors', errors.length === 0, errors.slice(0, 3).join(' | '));
  await ctx.close();

  // --- Monthly Summary on the seeded demo account ------------------------------
  section('Monthly Summary');
  const demoToken = (await api('/auth/login', 'POST', { email: DEMO_EMAIL, password: DEMO_PASSWORD })).body.access_token;
  const summary = (await api('/analytics/monthly-summary', 'GET', null, demoToken)).body;
  check(`last month (${summary.month}) has the seeded workouts`, summary.workouts > 0, String(summary.workouts));
  for (const width of [360, 390, 430]) {
    const c = await browser.newContext({ viewport: { width, height: width < 400 ? 800 : 932 }, deviceScaleFactor: 2,
      isMobile: true, hasTouch: true });
    const p = await c.newPage();
    await signIn(p, DEMO_EMAIL, DEMO_PASSWORD);
    await p.goto(`${UI}/summary/${summary.month}`);
    const slide = p.locator('.ma-slide');
    await slide.waitFor({ timeout: 20000 });
    const texts = [];
    for (let i = 0; i < 7; i++) {
      await p.waitForTimeout(400);
      texts.push(await slide.innerText());
      await p.screenshot({ path: join(OUT, `summary-${width}-${i + 1}.png`) });
      const wider = await p.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
      if (wider > 1) check(`${width}: slide ${i + 1} fits`, false, `${wider}px`);
      if (i < 6) await p.locator('.ma-next').click({ position: { x: 150, y: 400 } });
    }
    if (width === 360) {
      const vol = Math.round(summary.volume_kg).toLocaleString('en-US');
      check(`slide 1: ${summary.workouts} workouts`, texts[0].includes(String(summary.workouts)));
      check(`slide 2: ${vol} kg and "${summary.volume_comparison}"`,
        texts[1].includes(`${vol} kg`) && texts[1].includes(summary.volume_comparison));
      check(`slide 3: ${summary.muscles[0]?.display_name} most trained`, texts[2].includes(summary.muscles[0]?.display_name || 'No lifting'));
      check(`slide 4: ${summary.record_count} records`, texts[3].includes(String(summary.record_count)));
      check(`slide 5: ${summary.points} points`, texts[4].includes(String(summary.points)));
      check(`slide 6: ${summary.duels_won} of ${summary.duels_played} duels`,
        texts[5].includes(`${summary.duels_won} of ${summary.duels_played} duels won`));
      check('slide 7: the share card, with Share and Done',
        texts[6].includes('Workouts') && (await p.getByRole('button', { name: 'Share' }).count()) === 1);
      // Back goes back.
      await p.locator('[aria-label="Previous"]').click({ position: { x: 40, y: 120 } });
      await p.waitForTimeout(400);
      check('tapping the left goes back a slide', (await slide.innerText()).includes('duels won'));
    }
    await c.close();
  }
  const hero = (await api('/analytics/monthly-summary/latest', 'GET', null, demoToken)).body;
  const homeCtx = await browser.newContext({ viewport: { width: 390, height: 860 } });
  const home = await homeCtx.newPage();
  await signIn(home, DEMO_EMAIL, DEMO_PASSWORD);
  await home.goto(`${UI}/progress`);
  const shown = await seen(home.getByText(/ workouts · see your month$/), 8000);
  check(`Progress shows last month's card exactly when the API says (${hero.show})`, shown === hero.show);
  await homeCtx.close();
} catch (err) {
  failed.push(`aborted: ${err.message.split('\n')[0]}`);
  console.log('  ABORT', err.message.split('\n').slice(0, 8).join('\n'));
} finally {
  await browser.close();
}

console.log(`\n${failed.length ? `${failed.length} FAILED` : 'ALL PASSED'} (${passed} passed) - screenshots in ${OUT}`);
for (const f of failed) console.log('  -', f);
process.exit(failed.length ? 1 : 0);
