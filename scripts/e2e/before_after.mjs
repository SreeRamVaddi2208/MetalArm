// Before/after sheets for a redesign: each screen's old capture beside its
// new one, as a JPEG per screen, from two screens.mjs runs.
//
//   node before_after.mjs <before-dir> <after-dir> <out-dir> [--width 390] [--height 1700]
//
// <before-dir>/<width>/<name>.png and <after-dir>/<width>/<name>.png, as
// screens.mjs writes them. Each side shows the top <height> CSS px of the
// page - the part a phone shows first and a reviewer compares. PAIRS maps
// the five-tab app's screens to where they live now; a screen with no old
// counterpart is sheeted alone.

import { existsSync, mkdirSync, readFileSync } from 'node:fs';
import { join } from 'node:path';
import { chromium } from 'playwright-core';

const [BEFORE, AFTER, OUT] = process.argv.slice(2);
if (!OUT) { console.error('usage: node before_after.mjs <before> <after> <out>'); process.exit(2); }
const arg = (name, fallback) => {
  const i = process.argv.indexOf(name);
  return i > -1 ? Number(process.argv[i + 1]) : fallback;
};
const WIDTH = arg('--width', 390);
const HEIGHT = arg('--height', 1700);

// [sheet name, before capture, after capture]
const PAIRS = [
  ['home', 'home', 'home'],
  ['train (was workout)', 'workout', 'train'],
  ['train (was library)', 'library', 'train'],
  ['exercises (was explore)', 'explore', 'train-exercises'],
  ['progress (was you)', 'you', 'progress'],
  ['progress (was progress)', 'progress', 'progress'],
  ['quests', 'quests', 'quests'],
  ['duels', 'duels', 'duels'],
  ['parties', 'parties', 'parties'],
  ['rewards', 'rewards', 'rewards'],
  ['notifications', 'notifications', 'notifications'],
  ['profile', 'profile', 'profile'],
  ['exercise detail', 'exercise', 'exercise'],
  ['session detail', 'session', 'session'],
  ['someone else', 'u', 'u'],
  ['monthly summary', 'summary-2026-09', 'summary-2026-09'],
  ['credits', 'about-credits', 'about-credits'],
  ['sign in', 'login', 'login'],
  ['create account', 'signup', 'signup'],
  ['leaderboard (new)', null, 'leaderboard'],
  ['welcome (new)', null, 'welcome'],
  ['history (new)', null, 'progress-history'],
  ['measurements (new)', null, 'progress-measurements'],
  ['recovery (new)', null, 'progress-recovery'],
  ['people (new)', null, 'profile-people'],
  ['program (new)', null, 'train-program-barbell-foundations'],
  ['design system (new)', null, 'design-system'],
];

const src = (dir, name) => {
  const path = name && join(dir, String(WIDTH), `${name}.png`);
  return path && existsSync(path) ? `data:image/png;base64,${readFileSync(path).toString('base64')}` : null;
};
const column = (label, data) => `
  <figure><figcaption>${label}</figcaption>
    <div class="frame">${data ? `<img src="${data}">` : '<p>(no capture)</p>'}</div></figure>`;

mkdirSync(OUT, { recursive: true });
const launch = process.env.CHROME_PATH
  ? { executablePath: process.env.CHROME_PATH, headless: true }
  : { channel: 'chrome', headless: true };
const browser = await chromium.launch(launch);
const page = await browser.newPage({ deviceScaleFactor: 1 });
let n = 0;
for (const [label, before, after] of PAIRS) {
  const a = src(AFTER, after);
  if (!a) { console.log(`  skip ${label}: no after capture`); continue; }
  const b = before ? src(BEFORE, before) : null;
  const cols = before ? [column('Before', b), column('After', a)] : [column('After', a)];
  await page.setViewportSize({ width: cols.length * (WIDTH + 48) + 48, height: HEIGHT + 120 });
  await page.setContent(`<!doctype html><html><body>
    <style>
      body { margin: 0; padding: 24px; background: #000; color: #ccc; font: 600 18px system-ui; }
      h1 { margin: 0 0 16px; font-size: 20px; color: #fff; }
      main { display: flex; gap: 48px; }
      figure { margin: 0; } figcaption { margin-bottom: 8px; }
      .frame { width: ${WIDTH}px; height: ${HEIGHT}px; overflow: hidden; outline: 1px solid #333; }
      img { width: ${WIDTH}px; display: block; }
    </style>
    <h1>${label} · ${WIDTH}px</h1><main>${cols.join('')}</main></body></html>`);
  await page.waitForTimeout(200);
  const file = `${String(++n).padStart(2, '0')}-${label.replace(/[^a-z0-9]+/gi, '-').replace(/-+$/, '')}.jpg`;
  await page.screenshot({ path: join(OUT, file), type: 'jpeg', quality: 72 });
  console.log(`  ${file}`);
}
await browser.close();
console.log(`\n${n} sheets in ${OUT}`);
