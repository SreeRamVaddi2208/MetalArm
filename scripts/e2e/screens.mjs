// Screenshot sweep for the overhaul's design gates: /gallery and every tab at
// the two phone sizes the spec names (375x812, 430x932), plus a check that no
// page scrolls sideways - the commonest way a mobile layout breaks.
//
//   node screens.mjs <out-dir> <email> <password>
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
const SIZES = [{ width: 375, height: 812 }, { width: 430, height: 932 }];
const PAGES = ['/home', '/explore', '/workout', '/library', '/you', '/progress', '/duels',
  '/parties', '/rewards', '/about/credits'];

const launch = process.env.CHROME_PATH
  ? { executablePath: process.env.CHROME_PATH, headless: true }
  : { channel: 'chrome', headless: true };
const browser = await chromium.launch(launch);
const overflow = [];

try {
  // The gallery lays both phone widths side by side: capture it wide.
  const wide = await browser.newPage({ viewport: { width: 1100, height: 900 } });
  await wide.goto(`${UI}/gallery/`);
  await wide.waitForLoadState('networkidle').catch(() => {});
  await wide.waitForTimeout(1500);
  mkdirSync(OUT, { recursive: true });
  await wide.screenshot({ path: join(OUT, 'gallery.png'), fullPage: true });
  await wide.close();

  for (const size of SIZES) {
    const context = await browser.newContext({ viewport: size, deviceScaleFactor: 2, isMobile: true, hasTouch: true });
    const page = await context.newPage();
    await page.goto(`${UI}/login`);
    await page.locator('input').first().fill(EMAIL);
    await page.locator('input[type=password]').fill(PASSWORD);
    await page.getByText('ENTER', { exact: true }).click();
    await page.waitForURL('**/home', { timeout: 30000 });
    const dir = join(OUT, String(size.width));
    mkdirSync(dir, { recursive: true });
    for (const path of PAGES) {
      await page.goto(UI + path);
      await page.waitForLoadState('networkidle').catch(() => {});
      await page.waitForTimeout(1200);
      const wider = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
      if (wider > 1) overflow.push(`${path} @${size.width}: ${wider}px too wide`);
      const name = path.replace(/^\//, '').replace(/\//g, '-') || 'root';
      await page.screenshot({ path: join(dir, `${name}.png`), fullPage: true });
      console.log(`  ${size.width}  ${path}${wider > 1 ? `  OVERFLOW ${wider}px` : ''}`);
    }
    await context.close();
  }
} finally {
  await browser.close();
}

if (overflow.length) {
  console.log(`\nhorizontal overflow:\n  ${overflow.join('\n  ')}`);
  process.exit(1);
}
console.log(`\nno horizontal overflow; screenshots in ${OUT}`);
