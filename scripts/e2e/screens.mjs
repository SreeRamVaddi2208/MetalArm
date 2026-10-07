// Screenshot sweep for the design gates: /design-system and every screen at
// phone widths (default 360, 390, 430), plus a check that no page scrolls
// sideways - the commonest way a mobile layout breaks.
//
//   node screens.mjs <out-dir> <email> <password> [--widths 360,390,430]
//
// Besides the fixed routes it captures the id-based pages (an exercise, the
// latest workout, a friend's profile, last month's story, a routine, a curated
// program), found through the API, and the signed-out pages.
//
// Against a RUNNING stack. Writes <out-dir>/<width>/<page>.png full-page
// captures for side-by-side review, and exits non-zero if any page overflows
// horizontally at either width.

import { mkdirSync } from 'node:fs';
import { join } from 'node:path';
import { chromium } from 'playwright-core';

const [OUT, EMAIL, PASSWORD] = process.argv.slice(2);
if (!PASSWORD) { console.error('usage: node screens.mjs <out> <email> <password>'); process.exit(2); }
const UI = process.env.METALARM_UI || 'http://localhost:3000';
const widthArg = process.argv.indexOf('--widths');
const WIDTHS = widthArg > -1 ? process.argv[widthArg + 1].split(',').map(Number) : [360, 390, 430];
const SIZES = WIDTHS.map((width) => ({ width, height: width < 400 ? 800 : 932 }));
const API = process.env.METALARM_API || 'http://localhost:8000/api/v1';
const PAGES = (process.env.SCREEN_ROUTES ||
  '/design-system,/home,/leaderboard,/notifications,/train,/train/exercises,/train/routine/new,/progress,' +
  '/progress/history,/progress/measurements,/progress/recovery,/profile,/profile/people,/quests,/duels,/parties,' +
  '/rewards,/about/credits,/welcome'
).split(',');
async function get(path, token) {
  const r = await fetch(API + path, { headers: token ? { Authorization: `Bearer ${token}` } : {} });
  return r.ok ? r.json() : null;
}
{
  // The id-based pages, from the account's own data.
  const login = await fetch(`${API}/auth/login`, { method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email: EMAIL, password: PASSWORD }) }).then((r) => r.json());
  const token = login.access_token;
  const mine = await get('/me/exercises?limit=1', token);
  if (mine?.items?.[0]) PAGES.push(`/exercise/${mine.items[0].exercise_id}`);
  const history = await get('/history?limit=1', token);
  const last = history?.months?.[0]?.sessions?.[0];
  if (last) PAGES.push(`/session/${last.id}`);
  const people = await get('/users/search?q=a', token);
  if (people?.items?.[0]) PAGES.push(`/u/${people.items[0].id}`);
  const hero = await get('/analytics/monthly-summary/latest', token);
  if (hero?.month) PAGES.push(`/summary/${hero.month}`);
  const routines = await get('/routines', token);
  const firstRoutine = (routines?.items || routines)?.[0];
  if (firstRoutine) PAGES.push(`/train/routine/${firstRoutine.id}`);
  const curated = await get('/programs/curated', token);
  if (curated?.[0]) PAGES.push(`/train/program/${curated[0].slug}`);
}
const SIGNED_OUT = ['/login', '/signup'];

const launch = process.env.CHROME_PATH
  ? { executablePath: process.env.CHROME_PATH, headless: true }
  : { channel: 'chrome', headless: true };
const browser = await chromium.launch(launch);
const overflow = [];

try {
  mkdirSync(OUT, { recursive: true });
  for (const size of SIZES) {
    const context = await browser.newContext({ viewport: size, deviceScaleFactor: 2, isMobile: true, hasTouch: true });
    const page = await context.newPage();
    await page.goto(`${UI}/login`);
    await page.locator('input').first().fill(EMAIL);
    await page.locator('input[type=password]').fill(PASSWORD);
    await page.getByRole('button', { name: 'Sign in' }).click();
    await page.waitForURL('**/home', { timeout: 30000 });
    const dir = join(OUT, String(size.width));
    mkdirSync(dir, { recursive: true });
    for (const path of PAGES) {
      await page.goto(UI + path);
      await page.waitForLoadState('networkidle').catch(() => {});
      await page.waitForTimeout(1200);
      const wider = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
      if (wider > 1) overflow.push(`${path} @${size.width}: ${wider}px too wide`);
      const name = path.replace(/^\//, '').replace(/\//g, '-').replace(/-[0-9a-f]{8}-[0-9a-f-]{27}$/, '') || 'root';
      await page.screenshot({ path: join(dir, `${name}.png`), fullPage: true });
      console.log(`  ${size.width}  ${path}${wider > 1 ? `  OVERFLOW ${wider}px` : ''}`);
    }
    await context.close();
    const anon = await browser.newContext({ viewport: size, deviceScaleFactor: 2, isMobile: true, hasTouch: true });
    const out = await anon.newPage();
    for (const path of SIGNED_OUT) {
      await out.goto(UI + path);
      await out.waitForTimeout(1200);
      await out.screenshot({ path: join(dir, `${path.slice(1)}.png`), fullPage: true });
      console.log(`  ${size.width}  ${path}`);
    }
    await anon.close();
  }
} finally {
  await browser.close();
}

if (overflow.length) {
  console.log(`\nhorizontal overflow:\n  ${overflow.join('\n  ')}`);
  process.exit(1);
}
console.log(`\nno horizontal overflow; screenshots in ${OUT}`);
