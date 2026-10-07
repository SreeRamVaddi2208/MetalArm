// Overhaul Gate 3: Explore - and every library exercise has an illustration.
//
//   node explore_e2e.mjs [screenshot-dir]
//
// Against a RUNNING stack. A fresh bodybuilder:
//   - every library exercise's artwork is actually served (all of them, not a sample);
//   - search finds by alias ("rdl"), remembers recent searches;
//   - a muscle tile, then an equipment chip, list exactly what the API counts;
//   - Exercise Detail shows the picture;
//   - curated programs: two per path, the user's first; one saved into the
//     Library, with its routines;
//   - the workout picker adds two exercises in one go.
// Screenshots at 375 and 430, no sideways scroll, no uncaught errors.

import { mkdirSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { chromium } from 'playwright-core';

const API = process.env.METALARM_API || 'http://localhost:8000/api/v1';
const UI = process.env.METALARM_UI || 'http://localhost:3000';
const OUT = process.argv[2] || join(tmpdir(), 'metalarm-explore-e2e');

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

const launch = process.env.CHROME_PATH
  ? { executablePath: process.env.CHROME_PATH, headless: true }
  : { channel: 'chrome', headless: true };
const browser = await chromium.launch(launch);

try {
  section('Every library exercise has an illustration');
  const email = `gate3-${Date.now()}@metalarm.dev`;
  const password = 'gate-three-passphrase';
  await api('/auth/signup', 'POST', { email, password, display_name: 'Gate Three', timezone: 'UTC' });
  const token = (await api('/auth/login', 'POST', { email, password })).body.access_token;
  await api('/auth/me', 'PATCH', { character_class: 'bodybuilder' }, token);
  const all = [];
  let cursor = '';
  do {
    const page = (await api(`/exercises/browse?limit=100${cursor ? `&cursor=${cursor}` : ''}`, 'GET', null, token)).body;
    all.push(...page.items);
    cursor = page.next_cursor || '';
  } while (cursor);
  check(`the library lists ${all.length} exercises`, all.length >= 190);
  const noArt = all.filter((e) => !e.thumbnail_url).map((e) => e.name);
  check('every one names its artwork', noArt.length === 0, noArt.slice(0, 5).join(', '));
  const broken = [];
  for (const e of all) {
    const r = await fetch(UI + e.thumbnail_url);
    const type = r.headers.get('content-type') || '';
    if (!r.ok || !type.startsWith('image/')) broken.push(`${e.name} (${r.status} ${type})`);
  }
  check('and the app serves every image', broken.length === 0, broken.slice(0, 5).join(', '));
  const uncredited = all.filter((e) => !(e.media_author && e.media_license)).map((e) => e.name);
  check('every image carries its credit', uncredited.length === 0, uncredited.slice(0, 5).join(', '));

  for (const width of [375, 430]) {
    const dir = join(OUT, String(width));
    mkdirSync(dir, { recursive: true });
    section(`Gate 3 at ${width}px`);
    const ctx = await browser.newContext({ viewport: { width, height: width === 375 ? 812 : 932 },
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
    await page.getByText('ENTER', { exact: true }).click();
    await page.waitForURL('**/home', { timeout: 30000 });

    // --- Search -------------------------------------------------------------
    await page.goto(`${UI}/explore`);
    await page.getByText('Muscle Groups').waitFor({ timeout: 20000 });
    await page.screenshot({ path: join(dir, '01-explore.png'), fullPage: true });
    await overflow('Explore');
    const box = page.getByPlaceholder('Search exercises and programs');
    await box.fill('rdl');
    check('search finds Romanian Deadlift by "rdl"', await seen(page.getByText('Romanian Deadlift', { exact: true })));
    await page.screenshot({ path: join(dir, '02-search.png'), fullPage: true });
    await page.getByText('Romanian Deadlift', { exact: true }).first().click();
    await page.waitForURL('**/exercise/**', { timeout: 15000 });
    const img = page.locator('img[alt="Romanian Deadlift"]');
    await img.waitFor({ timeout: 15000 }).catch(() => {});
    check('Exercise Detail shows its picture',
      await img.evaluate((el) => el.complete && el.naturalWidth > 0).catch(() => false));
    await page.goBack();
    await box.waitFor({ timeout: 15000 });
    await box.fill('');
    await box.focus();
    check('a recent search is offered on focus', await seen(page.getByText('rdl', { exact: true }), 5000));
    await box.blur();

    // --- Muscle, then equipment ---------------------------------------------
    await page.getByText('Chest', { exact: true }).first().click();
    const chest = (await api('/exercises/browse?muscle=chest&limit=1', 'GET', null, token)).body.total;
    check(`Chest lists ${chest} exercises, as the API counts`, await seen(page.getByText(`${chest} exercises`, { exact: true })));
    await page.getByRole('button', { name: 'Dumbbell', exact: true }).click();
    const chestDb = (await api('/exercises/browse?muscle=chest&equipment=dumbbell&limit=1', 'GET', null, token)).body.total;
    check(`Chest + Dumbbell lists ${chestDb}`, await seen(page.getByText(`${chestDb} exercise${chestDb === 1 ? '' : 's'}`, { exact: true })));
    const subs = await page.locator('a[href^="/exercise/"]').allInnerTexts();
    check('every listed exercise is a dumbbell chest exercise',
      subs.length === chestDb && subs.every((s) => /Chest/.test(s) && /Dumbbell/.test(s)), `${subs.length}`);
    await page.screenshot({ path: join(dir, '03-filtered.png'), fullPage: true });
    await overflow('Filtered list');
    await page.getByText('Clear', { exact: true }).click();

    // --- Programs --------------------------------------------------------------
    await page.getByText('Programs', { exact: true }).first().click();
    const cards = page.locator('.ma-program-card');
    await cards.first().waitFor({ timeout: 15000 });
    check('six curated programs', (await cards.count()) === 6);
    const firstTwo = [await cards.nth(0).innerText(), await cards.nth(1).innerText()];
    check('the bodybuilder plans come first', firstTwo.every((x) => x.includes('Bodybuilder')));
    await page.screenshot({ path: join(dir, '04-programs.png'), fullPage: true });
    await overflow('Programs');
    if (width === 375) {
      await page.getByText('Upper / Lower Builder', { exact: true }).click();
      check('the program sheet lists its routines', await seen(page.getByText('Lower B', { exact: true })));
      await page.getByText('Save to Library', { exact: true }).click();
      check('saving says it is in your Library', await seen(page.getByText('In your Library - open it')));
      await page.screenshot({ path: join(dir, '05-program-saved.png') });
      await page.goto(`${UI}/library`);
      await page.getByText('Programs', { exact: true }).first().click();
      await page.getByText('Upper / Lower Builder').first().click();
      check('the Library has it, with four routines',
        (await seen(page.getByText('Upper A', { exact: true }))) && (await seen(page.getByText('Lower B', { exact: true }))));
      await page.screenshot({ path: join(dir, '06-library-program.png'), fullPage: true });

      // --- Picker multi-select -------------------------------------------------
      await page.goto(`${UI}/workout`);
      await page.getByText('Start New Workout', { exact: true }).first().click();
      await page.getByText('Add Exercise').waitFor({ timeout: 15000 });
      await page.getByText('Add Exercise').click();
      await page.getByPlaceholder('Search exercises…').fill('curl');
      await page.getByRole('checkbox', { name: 'Hammer Curl', exact: true }).click();
      await page.getByRole('checkbox', { name: 'EZ-Bar Curl', exact: true }).click();
      await page.screenshot({ path: join(dir, '07-picker.png') });
      await page.getByRole('button', { name: 'Add 2 exercises' }).click();
      const added = (await seen(page.locator('.ma-card').getByText('Hammer Curl', { exact: true })))
        && (await seen(page.locator('.ma-card').getByText('EZ-Bar Curl', { exact: true })));
      check('the picker adds two exercises at once, in order',
        added && (await page.locator('.ma-card').first().innerText()).includes('Hammer Curl'));
      await page.getByRole('button', { name: 'Discard workout' }).click();
      await page.getByText('Discard', { exact: true }).click();
    }

    // --- Credits ----------------------------------------------------------------
    await page.goto(`${UI}/about/credits`);
    const credited = all.filter((e) => e.media_author && e.media_author !== 'MetalArm').length;
    await page.locator('a[target="_blank"]').first().waitFor({ timeout: 15000 }).catch(() => {});
    const rows = await page.locator('a[target="_blank"]').count();
    check(`credits list all ${credited} outside images`, rows === credited, `${rows}`);
    await overflow('Credits');

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
