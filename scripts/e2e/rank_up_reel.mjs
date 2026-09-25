// Records the rank-up escalation in a real browser, against a RUNNING stack.
//
//   docker compose up -d && scripts/dev.sh web      # serve the CURRENT frontend
//   cd scripts/e2e && node rank_up_reel.mjs [out-dir]
//
// Walks the five promotions through ?celebrate=<rank> (the dev trigger in
// QuestState.preview_celebration) and lets each sequence play out, so the
// escalation reads: Novice is a flourish in steel, World Class is a crowned,
// jewelled, four-and-a-half second event with dust still drifting afterwards.
//
// Playwright records webm; ffmpeg turns it into an mp4 that sits beside the
// iOS tour. Nothing is asserted here - rank_up_e2e.mjs is the test, this is
// the camera.

import { execFileSync } from 'node:child_process';
import { mkdirSync, readdirSync, renameSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { chromium } from 'playwright-core';

const API = process.env.METALARM_API || 'http://localhost:8000/api/v1';
const UI = process.env.METALARM_UI || 'http://localhost:3000';
const today = new Date().toISOString().slice(0, 10);
const OUT = process.argv[2] || join(process.env.HOME, 'Desktop', 'MetalArm Recordings', today);
mkdirSync(OUT, { recursive: true });
const raw = join(tmpdir(), `metalarm-reel-${Date.now()}`);
mkdirSync(raw, { recursive: true });

const email = `reel-${Date.now()}@metalarm.dev`;
const password = 'e2e-test-passphrase';

// Ascending, with how long each one runs (rank_tiers.py) so the reel holds on
// the settled card instead of cutting while the dust is still falling.
const TIERS = [
  { rank: 'D', title: 'Novice', duration: 1700 },
  { rank: 'C', title: 'Intermediate', duration: 2300 },
  { rank: 'B', title: 'Advanced', duration: 2900 },
  { rank: 'A', title: 'Elite', duration: 3600 },
  { rank: 'S', title: 'World Class', duration: 4400 },
];

async function signIn(page) {
  await page.goto(UI + '/login');
  await page.locator('input').first().fill(email);
  await page.locator('input[type=password]').fill(password);
  await page.getByText('ENTER', { exact: true }).click();
  await page.waitForURL('**/dashboard', { timeout: 20000 });
}

const signup = await fetch(API + '/auth/signup', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ email, password, display_name: 'MetalArm', timezone: 'UTC' }),
});
if (signup.status !== 201) {
  console.error(`signup failed (${signup.status}). If it is 429, run: scripts/dev.sh unlimit`);
  process.exit(1);
}

const launchOptions = process.env.CHROME_PATH
  ? { executablePath: process.env.CHROME_PATH, headless: true }
  : { channel: 'chrome', headless: true };
const browser = await chromium.launch(launchOptions);
const context = await browser.newContext({
  viewport: { width: 400, height: 860 },
  recordVideo: { dir: raw, size: { width: 400, height: 860 } },
});
const page = await context.newPage();

try {
  await signIn(page);
  await page.waitForTimeout(1500); // open on the dashboard, not mid-load

  for (const tier of TIERS) {
    console.log(`  ${tier.rank}  ${tier.title}`);
    await page.goto(`${UI}/dashboard?celebrate=${tier.rank}`);
    await page.locator('.lf-celebrate').waitFor({ state: 'visible', timeout: 15000 });
    // The whole sequence, then a beat on the settled card.
    await page.waitForTimeout(tier.duration + 1600);
    await page.getByText('CONTINUE', { exact: true }).click();
    await page.locator('.lf-celebrate').waitFor({ state: 'detached', timeout: 10000 });
    await page.waitForTimeout(700);
  }
} finally {
  // Closing the context is what finalises the video file.
  await context.close();
  await browser.close();
}

const webm = readdirSync(raw).find((f) => f.endsWith('.webm'));
if (!webm) { console.error('No video was recorded'); process.exit(1); }
const mp4 = join(OUT, 'metalarm-rank-up.mp4');
execFileSync('ffmpeg', ['-v', 'error', '-y', '-i', join(raw, webm),
  '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-movflags', '+faststart', mp4]);
rmSync(raw, { recursive: true, force: true });
console.log(`\nwrote ${mp4}`);
