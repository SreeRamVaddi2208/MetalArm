// Records the Android app working, as a phone sees it.
//
//   docker compose up -d && scripts/dev.sh web
//   cd scripts/e2e && node android_reel.mjs [out-dir]
//
// The Android app IS the web app - installed from the browser, or wrapped in
// the TWA shell under android/ for the Play listing. So this drives Chrome
// with a Pixel 7's viewport, scale factor, touch input and user agent, which
// is what somebody who installed it actually sees. It is not an emulator: this
// machine has no Android SDK, and the recording says so in the chapter file
// rather than implying otherwise.

import { execFileSync } from 'node:child_process';
import { mkdirSync, readdirSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { chromium, devices } from 'playwright-core';

const UI = process.env.METALARM_UI || 'http://localhost:3000';
const API = process.env.METALARM_API || 'http://localhost:8000/api/v1';
const today = new Date().toISOString().slice(0, 10);
const OUT = process.argv[2] || join(process.env.HOME, 'Desktop', 'MetalArm Recordings', today);
mkdirSync(OUT, { recursive: true });
const raw = join(tmpdir(), `metalarm-android-${Date.now()}`);
mkdirSync(raw, { recursive: true });

const password = 'demo-passphrase-1';
const stamp = Date.now();
const me = `android-reel-${stamp}@metalarm.dev`;
const mate = `android-mate-${stamp}@metalarm.dev`;
const marks = [];
const mark = (name) => { marks.push([name, Date.now()]); console.log('  ', name); };

async function api(path, method = 'GET', body, token) {
  const r = await fetch(API + path, {
    method,
    headers: { 'Content-Type': 'application/json', ...(token ? { Authorization: `Bearer ${token}` } : {}) },
    body: body ? JSON.stringify(body) : undefined,
  });
  const text = await r.text();
  return { status: r.status, body: text ? JSON.parse(text) : null };
}

async function account(email, name) {
  const up = await api('/auth/signup', 'POST', { email, password, display_name: name, timezone: 'Asia/Kolkata' });
  if (up.status !== 201) { console.error(`signup ${up.status}; try scripts/dev.sh unlimit`); process.exit(1); }
  return (await api('/auth/login', 'POST', { email, password })).body.access_token;
}

// A populated account, so the recording shows a working app rather than empty
// screens: a party, real workouts on the big lifts, a duel, a quest.
const myToken = await account(me, 'Sree Ram');
const mateToken = await account(mate, 'Priya');
const party = await api('/parties', 'POST', { name: 'Iron Temple' }, myToken);
await api('/parties/join', 'POST', { invite_code: party.body.invite_code }, mateToken);
const exercises = await api('/exercises?limit=200', 'GET', undefined, myToken);
const items = exercises.body.items || exercises.body;
const picks = ['Barbell Back Squat', 'Barbell Bench Press', 'Deadlift', 'Conventional Deadlift']
  .map((name) => items.find((e) => e.name === name)).filter(Boolean).slice(0, 3);
for (const [token, base] of [[myToken, 100], [mateToken, 80]]) {
  for (const bump of [0, 5]) {
    const session = await api('/workouts/sessions', 'POST', {}, token);
    for (const [i, exercise] of picks.entries()) {
      await api(`/workouts/sessions/${session.body.id}/sets`, 'POST',
                { exercise_id: exercise.id, weight_kg: base + bump + i * 10, reps: 5 }, token);
    }
    await api(`/workouts/sessions/${session.body.id}/finish`, 'POST', undefined, token);
  }
}
await api('/duels', 'POST', { metric: 'volume', days: 7, against_rival: true }, myToken);
const board = await api(`/parties/${party.body.id}/leaderboard`, 'GET', undefined, myToken);
const mateId = board.body.entries.find((e) => !e.is_me)?.user_id;
if (mateId) await api('/duels', 'POST', { metric: 'sets', days: 7, opponent_id: mateId }, myToken);
const quest = await api('/quests', 'POST',
  { title: 'Train three times', xp_reward: 120, points_reward: 15, recurrence: 'weekly' }, myToken);
await api(`/quests/${quest.body.id}/complete`, 'POST', undefined, myToken);

const pixel = devices['Pixel 7'];
const browser = await chromium.launch(
  process.env.CHROME_PATH
    ? { executablePath: process.env.CHROME_PATH, headless: true }
    : { channel: 'chrome', headless: true },
);
const context = await browser.newContext({
  ...pixel,
  recordVideo: { dir: raw, size: pixel.viewport },
});
const page = await context.newPage();
const start = Date.now();

async function beat(ms = 2200) { await page.waitForTimeout(ms); }
async function visit(path, name, wait = 2600) {
  await page.goto(UI + path, { waitUntil: 'networkidle' });
  mark(name);
  await beat(wait);
}

try {
  await page.goto(`${UI}/login`, { waitUntil: 'networkidle' });
  mark('signin');
  await beat(1400);
  await page.locator('input').first().fill(me);
  await beat(700);
  await page.locator('input[type=password]').fill(password);
  await beat(700);
  await page.getByText('ENTER', { exact: true }).tap();
  await page.waitForURL('**/dashboard', { timeout: 20000 });
  mark('dashboard');
  await beat(3000);

  await visit('/workout', 'workout', 3400);
  await visit('/duels', 'duels', 4200);
  // Scroll the duels page so the feed is on screen too.
  await page.evaluate(() => window.scrollBy({ top: 600, behavior: 'smooth' }));
  mark('feed');
  await beat(3000);

  await visit('/progress', 'progress', 3400);
  await visit('/parties', 'parties', 3600);
  await visit('/rewards', 'rewards', 2600);
  await visit('/profile', 'profile', 3000);
  await page.evaluate(() => window.scrollBy({ top: 700, behavior: 'smooth' }));
  mark('notifications');
  await beat(2800);

  // The rank-up, which is the thing worth watching.
  await page.goto(`${UI}/dashboard?celebrate=S`, { waitUntil: 'networkidle' });
  mark('rankup');
  await beat(6000);
  mark('end');
} finally {
  await context.close();
  await browser.close();
}

const webm = readdirSync(raw).find((f) => f.endsWith('.webm'));
if (!webm) { console.error('nothing recorded'); process.exit(1); }
const mp4 = join(OUT, 'metalarm-android.mp4');
execFileSync('ffmpeg', ['-v', 'error', '-y', '-i', join(raw, webm),
  '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-movflags', '+faststart', mp4]);
rmSync(raw, { recursive: true, force: true });

const titles = {
  signin: 'Signing in', dashboard: 'Home: level, rank, streak', workout: 'Starting a workout',
  duels: 'Duels: a rival and a party member', feed: "The party's activity feed",
  progress: 'Progress: records and charts', parties: 'The party, league and raid',
  rewards: 'Rewards', profile: 'Profile and character sheet',
  notifications: 'Turning on notifications', rankup: 'Rank up: World Class', end: 'End',
};
const lines = ['# MetalArm on Android — recorded walkthrough\n',
  `\`${mp4}\`\n`,
  'Chrome on an emulated Pixel 7 — viewport, scale, touch input and Android user',
  'agent — which is what the installed app shows. Not an emulator: this machine',
  'has no Android SDK. The TWA shell under `android/` wraps this same app for the',
  'Play listing.\n',
  '| Time | Chapter |', '|---|---|'];
for (const [name, at] of marks) {
  const off = Math.max(0, Math.round((at - start) / 1000));
  lines.push(`| ${String(Math.floor(off / 60)).padStart(2, '0')}:${String(off % 60).padStart(2, '0')} | ${titles[name] || name} |`);
}
writeFileSync(join(OUT, 'android-chapters.md'), `${lines.join('\n')}\n`);
console.log(`\nwrote ${mp4}`);
console.log(`wrote ${join(OUT, 'android-chapters.md')}`);
