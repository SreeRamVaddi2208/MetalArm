// The web half of the demo film: drives the REAL app through every feature
// at a narrated pace and records it, against a RUNNING stack seeded by
// backend/scripts/seed_demo.py.
//
//   scripts/dev.sh record web        (seeds, then runs this)
//   node web_tour.mjs <out-dir> <assets-dir> <email> <password>
//
// <assets-dir> comes from scripts/demo/render_assets.mjs: every chapter holds
// for at least its voice clip (durations.json), so the narration never runs
// past its pictures. Writes <out-dir>/web-raw.webm and <out-dir>/web-marks.json
// ({id: seconds into the video}), which scripts/demo/build_demo.py cuts by.
//
// Nothing here is asserted - workout_e2e.mjs and duels_e2e.mjs are the tests.
// But a chapter that cannot find what it is meant to show fails loudly, so a
// UI change shows up as a broken take rather than a quietly wrong film.

import { mkdirSync, readFileSync, readdirSync, renameSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { chromium } from 'playwright-core';

const [OUT, ASSETS, EMAIL, PASSWORD] = process.argv.slice(2);
if (!PASSWORD) { console.error('usage: node web_tour.mjs <out> <assets> <email> <password>'); process.exit(2); }
const UI = process.env.METALARM_UI || 'http://localhost:3000';
const durations = JSON.parse(readFileSync(join(ASSETS, 'durations.json'), 'utf8')).web;
const SHOTS = join(OUT, 'web-shots');
mkdirSync(SHOTS, { recursive: true });
const raw = join(tmpdir(), `metalarm-tour-${Date.now()}`);
mkdirSync(raw, { recursive: true });

const launch = process.env.CHROME_PATH
  ? { executablePath: process.env.CHROME_PATH, headless: true }
  : { channel: 'chrome', headless: true };
const browser = await chromium.launch(launch);
const context = await browser.newContext({
  viewport: { width: 1440, height: 900 },
  recordVideo: { dir: raw, size: { width: 1440, height: 900 } },
  // The browser's speech API cannot be scripted; the mic is shown, the typed
  // box does the talking.
  permissions: [],
});
const page = await context.newPage();
const t0 = Date.now();
const marks = {};
const missed = [];

const wait = (ms) => page.waitForTimeout(ms);
const text = (t, exact = true) => page.getByText(t, { exact }).first();

/** Click something if it is there; a missing control is logged, not fatal. */
async function tap(locator, label) {
  try {
    await locator.scrollIntoViewIfNeeded({ timeout: 4000 });
    await locator.click({ timeout: 4000 });
    await wait(450);
    return true;
  } catch {
    missed.push(label);
    console.log(`    (missed: ${label})`);
    return false;
  }
}

/** Close whatever celebration a set raised (PR card, level-up), if any. */
async function clearOverlays() {
  for (const label of ['KEEP LIFTING', 'CONTINUE']) {
    const button = page.getByText(label, { exact: true }).first();
    if (await button.isVisible().catch(() => false)) {
      await button.click().catch(() => {});
      await wait(700);
    }
  }
}

async function logSet(label) {
  await tap(text('LOG SET'), label);
  await wait(1300);
}

async function glide(y) {
  await page.evaluate((to) => window.scrollTo({ top: to, behavior: 'smooth' }), y);
  await wait(900);
}

async function chapter(id, body) {
  marks[id] = (Date.now() - t0) / 1000;
  console.log(`  ${id}`);
  const started = Date.now();
  await body();
  await page.screenshot({ path: join(SHOTS, `${id}.png`) });
  // Hold until the narration for this chapter has finished, plus a breath.
  const left = (durations[id] + 0.7) * 1000 - (Date.now() - started);
  if (left > 0) await wait(left);
}

async function go(path) {
  await page.goto(UI + path);
  await page.waitForLoadState('networkidle').catch(() => {});
  await wait(900);
}

try {
  await go('/login');

  await chapter('intro', async () => { await wait(800); });

  await chapter('login', async () => {
    await page.locator('input').first().pressSequentially(EMAIL, { delay: 35 });
    await page.locator('input[type=password]').pressSequentially(PASSWORD, { delay: 25 });
    await wait(300);
    await text('ENTER').click();
    await page.waitForURL('**/dashboard', { timeout: 30000 });
    await wait(1800);
  });

  await chapter('dashboard', async () => { await wait(1200); });

  await chapter('freeze', async () => {
    await page.getByText('Your streak was saved', { exact: false }).first()
      .waitFor({ timeout: 8000 }).catch(() => missed.push('streak notice'));
    await wait(1500);
  });

  await chapter('quests', async () => {
    const today = text('TODAY');
    await today.scrollIntoViewIfNeeded().catch(() => {});
    await wait(1600);
    await tap(page.getByRole('button', { name: /Reroll/ }).first(), 'reroll');
    await wait(1200);
  });

  await chapter('custom', async () => {
    // Acknowledge the notice first so it does not sit over the board.
    await tap(page.getByRole('button', { name: 'OK', exact: true }), 'notice OK');
    await text('YOUR QUESTS').scrollIntoViewIfNeeded().catch(() => {});
    await wait(800);
    await tap(page.getByRole('button', { name: 'COMPLETE', exact: true }).first(), 'complete quest');
    // The level-up overlay, if this crossed a level.
    await wait(3500);
    await clearOverlays();
  });

  await chapter('duel_bars', async () => {
    await glide(0);
    await wait(1500);
  });

  // --- The workout ---------------------------------------------------------
  await chapter('workout', async () => {
    await go('/workout');
    await wait(1200);
    await glide(500);
    await glide(0);
  });

  await chapter('preset', async () => {
    await tap(page.getByText('Powerlifter', { exact: false }).first(), 'open a preset');
    await wait(1500);
    await tap(page.getByText('START THIS WORKOUT', { exact: true }), 'start preset');
    await page.getByText('LOG SET', { exact: true }).first().waitFor({ timeout: 15000 });
    await wait(1500);
  });

  const plus = () => page.getByRole('button', { name: '+', exact: true });
  await chapter('logging', async () => {
    // Last time's weight, as pre-filled: an ordinary working set. Reps nudged
    // down, so it is not a rep record either.
    await tap(page.getByRole('button', { name: '−', exact: true }).nth(1), 'reps -');
    await logSet('log set 1');
    await clearOverlays();
    await logSet('log set 2');
    await clearOverlays();
  });

  await chapter('pr', async () => {
    // A clearly heavier set: the PR moment, held while it plays.
    for (let i = 0; i < 2; i++) await tap(plus().nth(0), 'weight + (pr)');
    await tap(text('LOG SET'), 'log PR set');
    await page.getByText('PERSONAL RECORD', { exact: true }).waitFor({ timeout: 8000 }).catch(() => missed.push('pr card'));
    await wait(4200);
    await clearOverlays();
  });

  await chapter('quest_chip', async () => {
    await logSet('log set (quest)');
    await clearOverlays();
    await page.evaluate(() => window.scrollTo({ top: 0, behavior: 'smooth' }));
    await wait(1800);
  });

  await chapter('typed', async () => {
    await page.getByText('Hold to talk', { exact: false }).first().scrollIntoViewIfNeeded().catch(() => {});
    await wait(1200);
    await tap(page.getByRole('button', { name: 'Type a set instead' }), 'keyboard toggle');
    const box = page.getByPlaceholder(/Type a set/);
    await box.click().catch(() => missed.push('typed box'));
    await box.pressSequentially('bench 82.5 for 5 rpe 8', { delay: 70 }).catch(() => {});
    await tap(page.getByRole('button', { name: 'PARSE', exact: true }), 'parse');
    await page.getByText('HEARD', { exact: true }).waitFor({ timeout: 10000 }).catch(() => missed.push('proposal card'));
    await wait(1500);
    await tap(page.getByRole('button', { name: '+', exact: true }).last(), 'sets +');
    await wait(800);
    await tap(page.getByRole('button', { name: /LOG 2 SETS|LOG IT/ }), 'log it');
    await wait(2500);
    await clearOverlays();
  });

  await chapter('same_again', async () => {
    const box = page.getByPlaceholder(/Type a set/);
    await box.click().catch(() => {});
    await box.pressSequentially('same again', { delay: 70 }).catch(() => {});
    await tap(page.getByRole('button', { name: 'PARSE', exact: true }), 'parse same again');
    await wait(1800);
    await tap(page.getByRole('button', { name: /LOG IT/ }), 'log same again');
    await wait(1500);
    await clearOverlays();
    await tap(page.getByRole('button', { name: /Undo/ }), 'undo');
    await wait(1500);
  });

  await chapter('edit', async () => {
    await page.evaluate(() => window.scrollTo({ top: 0, behavior: 'smooth' }));
    await wait(800);
    await tap(page.getByRole('button', { name: 'Edit set' }).first(), 'edit a set');
    await wait(1800);
    await tap(page.getByRole('button', { name: 'CANCEL', exact: true }).first(), 'cancel edit');
    await wait(800);
  });

  await chapter('finish', async () => {
    await tap(text('FINISH WORKOUT'), 'finish');
    await page.getByText('WORKOUT COMPLETE', { exact: true }).waitFor({ timeout: 15000 }).catch(() => missed.push('summary'));
    await wait(1500);
    await clearOverlays();
    await glide(500);
    await glide(1100);
  });

  await chapter('share', async () => {
    await glide(0);
    await wait(600);
    await tap(page.getByRole('button', { name: 'SHARE', exact: true }), 'share');
    await wait(2500);
  });

  // --- Everything else -----------------------------------------------------
  await chapter('progress', async () => {
    await go('/progress');
    await glide(600);
    await glide(1300);
    await glide(2100);
    await glide(0);
  });

  await chapter('parties', async () => {
    await go('/parties');
    await tap(page.getByText('Iron Syndicate', { exact: false }).first(), 'open party');
    await wait(1500);
    await tap(page.getByRole('button', { name: 'ALL TIME', exact: true }), 'board all time');
    await glide(700);
    await glide(1400);
    await glide(0);
  });

  await chapter('duels', async () => {
    await go('/duels');
    // The ended duel is judged by this read: its result screen opens.
    await wait(1500);
    await tap(page.getByText('CONTINUE', { exact: true }), 'dismiss result early');
    await glide(450);
    await tap(page.getByRole('button', { name: 'Details' }).first(), 'duel details');
    await wait(1800);
  });

  await chapter('duel_modes', async () => {
    await glide(0);
    // Sam joined this week with no history: the fair modes that need a
    // baseline come back disabled, each saying why.
    const sam = page.locator('div').filter({ has: page.getByText('Sam', { exact: true }) })
      .getByRole('button', { name: 'CHALLENGE', exact: true }).last();
    await tap(sam, 'challenge Sam');
    await page.getByText('CHALLENGE SAM', { exact: false }).waitFor({ timeout: 8000 }).catch(() => missed.push('mode picker'));
    await wait(3500);
    await tap(page.getByRole('button', { name: 'Cancel', exact: true }), 'close picker');
    await tap(page.getByRole('button', { name: 'ACCEPT', exact: true }), 'accept challenge');
    await wait(1500);
  });

  await chapter('duel_result', async () => {
    // Bring the settled duel's result back for the camera.
    await page.evaluate(() => localStorage.removeItem('ma_duel_results_seen'));
    await go('/duels');
    await page.getByText(/GOOD FIGHT|DUEL WON|DUEL DRAWN/).waitFor({ timeout: 10000 }).catch(() => missed.push('result screen'));
    await wait(4200);
    await tap(page.getByText('CONTINUE', { exact: true }), 'result continue');
  });

  await chapter('feed', async () => {
    await text('ACTIVITY').scrollIntoViewIfNeeded().catch(() => {});
    await wait(2500);
  });

  await chapter('rewards', async () => {
    await go('/rewards');
    await wait(1200);
    await tap(page.getByRole('button', { name: /REDEEM/ }).first(), 'redeem');
    await wait(1800);
    await glide(600);
  });

  await chapter('routines', async () => {
    await go('/routines');
    await wait(1500);
    await glide(500);
  });

  await chapter('profile', async () => {
    await go('/profile');
    await glide(500);
    await glide(1100);
    await glide(1800);
    await glide(2600);
  });

  await chapter('rankup', async () => {
    await go('/dashboard?celebrate=S');
    await page.locator('.lf-celebrate').waitFor({ state: 'visible', timeout: 15000 }).catch(() => missed.push('rank-up'));
    await wait(5800);
  });

  await chapter('end', async () => {
    await tap(page.getByText('CONTINUE', { exact: true }), 'rank-up continue');
    await wait(1000);
  });
} finally {
  await context.close();
  await browser.close();
}

const webm = readdirSync(raw).find((f) => f.endsWith('.webm'));
if (!webm) { console.error('No video was recorded'); process.exit(1); }
renameSync(join(raw, webm), join(OUT, 'web-raw.webm'));
rmSync(raw, { recursive: true, force: true });
writeFileSync(join(OUT, 'web-marks.json'), JSON.stringify(marks, null, 1));
const expected = Object.keys(durations);
const absent = expected.filter((id) => !(id in marks));
console.log(`\nchapters: ${Object.keys(marks).length}/${expected.length}` +
  (absent.length ? `  MISSING: ${absent.join(', ')}` : ''));
if (missed.length) console.log(`missed controls: ${missed.join('; ')}`);
console.log(`wrote ${join(OUT, 'web-raw.webm')}`);
process.exit(absent.length ? 1 : 0);
