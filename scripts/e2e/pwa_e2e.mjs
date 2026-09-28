// The installable web app: manifest, service worker, offline shell, and the
// queue that keeps a set logged without a signal.
//
//   docker compose up -d && scripts/dev.sh web
//   cd scripts/e2e && node pwa_e2e.mjs
//
// Chrome is driven with a persistent profile because a service worker needs a
// real origin and a real storage bucket - an incognito context registers one
// and then throws it away, which is not what a phone does.

import { mkdtempSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { chromium } from 'playwright-core';

const UI = process.env.METALARM_UI || 'http://localhost:3000';
const API = process.env.METALARM_API || 'http://localhost:8000/api/v1';
const password = 'e2e-test-passphrase';
const email = `pwa-${Date.now()}@metalarm.dev`;

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

const signup = await api('/auth/signup', 'POST',
  { email, password, display_name: 'PWA', timezone: 'UTC' });
if (signup.status !== 201) {
  console.error(`signup failed (${signup.status}). If it is 429: scripts/dev.sh unlimit`);
  process.exit(1);
}

const profile = mkdtempSync(join(tmpdir(), 'metalarm-pwa-'));
const context = await chromium.launchPersistentContext(profile, {
  channel: 'chrome', headless: true, viewport: { width: 400, height: 860 },
});
const page = context.pages()[0] || await context.newPage();

try {
  section('The manifest');
  const manifest = await (await fetch(`${UI}/manifest.webmanifest`)).json();
  check('names the app', manifest.name === 'MetalArm');
  check('opens standalone, not in a tab', manifest.display === 'standalone');
  check('starts somewhere useful', manifest.start_url === '/dashboard', manifest.start_url);
  const sizes = manifest.icons.map((i) => i.sizes);
  check('carries the 192 and 512 Android asks for',
        sizes.includes('192x192') && sizes.includes('512x512'), sizes.join(' '));
  check('has a maskable icon, so the launcher can crop it',
        manifest.icons.some((i) => i.purpose === 'maskable'));
  for (const icon of manifest.icons) {
    const r = await fetch(UI + icon.src);
    check(`icon ${icon.src} is really there`, r.ok && r.headers.get('content-type') === 'image/png');
  }

  section('The service worker');
  await page.goto(`${UI}/login`, { waitUntil: 'networkidle' });
  await page.locator('input').first().fill(email);
  await page.locator('input[type=password]').fill(password);
  await page.getByText('ENTER', { exact: true }).click();
  await page.waitForURL('**/dashboard', { timeout: 20000 });
  await page.waitForTimeout(2500);

  const registered = await page.evaluate(async () => {
    const reg = await navigator.serviceWorker.getRegistration();
    return { scope: reg?.scope || null, active: !!reg?.active };
  });
  check('registers, and takes the whole origin',
        registered.active && registered.scope?.endsWith('/'), JSON.stringify(registered));

  section('Offline');
  await page.reload({ waitUntil: 'networkidle' });
  await page.waitForTimeout(1200);
  await context.setOffline(true);
  const offline = await page.goto(`${UI}/dashboard`, { waitUntil: 'domcontentloaded' })
    .then((r) => r?.status() ?? 0).catch(() => 0);
  const text = await page.locator('body').innerText().catch(() => '');
  check('the app still opens with no connection', offline > 0 && text.length > 0,
        `status ${offline}, ${text.length} chars`);
  check('and it is MetalArm, not a browser error page', /METALARM|QUESTS|WORKOUT/i.test(text),
        text.slice(0, 120));
  await page.screenshot({ path: join(tmpdir(), 'metalarm-pwa-offline.png') });

  section('A set logged with no signal');
  const queued = await page.evaluate(async () => {
    // Straight at the worker, the way the app's own POST would arrive.
    const r = await fetch('/api/v1/workouts/sessions/00000000-0000-4000-8000-000000000001/sets', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ exercise_id: 'x', weight_kg: 80, reps: 8, client_set_id: 'test-set-1' }),
    });
    return { status: r.status, body: await r.json().catch(() => null) };
  });
  check('is kept rather than lost', queued.status === 202 && queued.body?.queued === true,
        JSON.stringify(queued));

  const stored = await page.evaluate(() => new Promise((resolve) => {
    const open = indexedDB.open('metalarm-queue', 1);
    open.onsuccess = () => {
      const db = open.result;
      const all = db.transaction('sets', 'readonly').objectStore('sets').getAll();
      all.onsuccess = () => resolve(all.result.map((e) => e.clientSetId));
      all.onerror = () => resolve(['error']);
    };
    open.onerror = () => resolve(['error']);
  }));
  check('and it survives in the queue, keyed by its client id',
        stored.includes('test-set-1'), JSON.stringify(stored));

  await context.setOffline(false);
} catch (err) {
  failed.push(`aborted: ${err.message.split('\n')[0]}`);
  console.log('  ABORT', err.message.split('\n')[0]);
} finally {
  await context.close();
}

console.log(`\n${failed.length ? `${failed.length} FAILED` : 'ALL PASSED'} (${passed} passed)`);
for (const f of failed) console.log('  -', f);
process.exit(failed.length ? 1 : 0);
