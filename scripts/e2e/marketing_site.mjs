// The marketing site, checked in a real browser against a served static build.
//
//   cd marketing && npm run build && npx serve out -l 4000
//   cd scripts/e2e && node marketing_site.mjs [screenshot-dir]
//
// What matters here is not that it looks nice - it is that the page is
// READABLE without JavaScript, that reduced motion gets the content with no
// motion at all, that the phone build drops the pinned sections instead of
// scroll-jacking a small screen, and that the waitlist actually posts.

import { mkdirSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { chromium } from 'playwright-core';

const SITE = process.env.SITE_URL || 'http://localhost:4000';
const OUT = process.argv[2] || join(tmpdir(), 'metalarm-site');
mkdirSync(OUT, { recursive: true });

let passed = 0;
const failed = [];
const check = (label, ok, detail = '') => {
  if (ok) { passed++; console.log('  PASS', label); }
  else { failed.push(label); console.log('  FAIL', label, detail); }
};
const section = (name) => console.log(`\n${name}`);

const browser = await chromium.launch(
  process.env.CHROME_PATH
    ? { executablePath: process.env.CHROME_PATH, headless: true }
    : { channel: 'chrome', headless: true },
);

try {
  section('Desktop');
  const desktop = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const page = await desktop.newPage();
  const errors = [];
  page.on('pageerror', (e) => errors.push(e.message));
  await page.goto(SITE, { waitUntil: 'networkidle' });

  // Words are joined with NBSP (see components/Words.js), which innerText keeps.
  const text = (await page.locator('body').innerText()).replace(/\u00a0/g, ' ');
  for (const claim of ['The gym is the game.', 'Pick how you train. Once.',
                       'Six tiers. The last one takes years.', 'Nobody trains harder alone.',
                       'Your rival never skips a session.', 'Start at Untrained.',
                       'Ninety seconds, counting.', 'Proof, not vibes.']) {
    check(`section present: "${claim.slice(0, 28)}"`, text.includes(claim), text.slice(0, 120));
  }
  // Every claim on the page has to be something that ships.
  for (const unshipped of ['prestige', 'trophy case', 'Bronze', 'Diamond']) {
    check(`no unshipped claim: ${unshipped}`, !new RegExp(unshipped, 'i').test(text));
  }
  // The captures come from a demo account, and the page has to say so - the
  // numbers are the app's own, but the lifter is not real.
  check('the page says where its screens come from',
        /capture of MetalArm itself/i.test(text) && /demo account/i.test(text));

  await page.waitForTimeout(1200);
  check('the motion layer armed itself',
        await page.evaluate(() => document.documentElement.classList.contains('ma-js')));
  await page.screenshot({ path: `${OUT}/desktop-hero.png` });

  // Scroll through, then confirm the pinned section actually pinned.
  await page.evaluate(() => window.scrollTo(0, window.innerHeight * 1.6));
  await page.waitForTimeout(1500);
  const pinnedPosition = await page.evaluate(() => {
    const pinned = document.querySelector('.ma-pin');
    return pinned ? getComputedStyle(pinned.parentElement).transform !== 'none'
      || getComputedStyle(pinned).position : 'missing';
  });
  check('a section pins on desktop', pinnedPosition !== 'missing' && pinnedPosition !== 'static',
        String(pinnedPosition));
  await page.screenshot({ path: `${OUT}/desktop-pinned.png` });

  await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight));
  await page.waitForTimeout(1500);
  await page.screenshot({ path: `${OUT}/desktop-cta.png` });
  // The numbers on the page are real captured ones, so they are worth pinning:
  // a count-up that lands on the wrong figure is a lie told smoothly.
  await page.evaluate(() => window.scrollTo(0, 0));
  await page.waitForTimeout(2200);
  const counted = await page.evaluate(() =>
    [...document.querySelectorAll('[data-count-to]')].map(
      (el) => [el.dataset.countTo, el.textContent]));
  check('every count-up lands on its real value',
        counted.every(([target, shown]) => target === shown),
        JSON.stringify(counted));

  // The chart has to finish drawing, or it reads as a broken graphic.
  await page.evaluate(() => {
    const figure = document.querySelector('[data-chart-line]')?.closest('figure');
    figure?.scrollIntoView({ block: 'center' });
  });
  await page.waitForTimeout(2600);
  const drawn = await page.evaluate(() => {
    const line = document.querySelector('[data-chart-line]');
    return line ? Math.abs(Number(getComputedStyle(line).strokeDashoffset.replace('px', ''))) : -1;
  });
  check('the chart finishes drawing', drawn >= 0 && drawn < 1, String(drawn));
  await page.screenshot({ path: `${OUT}/desktop-chart.png` });

  check('no uncaught errors', errors.length === 0, errors.slice(0, 2).join(' | '));
  await desktop.close();

  section('Phone');
  const phone = await browser.newContext({ viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true });
  const small = await phone.newPage();
  await small.goto(SITE, { waitUntil: 'networkidle' });
  await small.waitForTimeout(1200);
  const overflow = await small.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
  check('no horizontal overflow on a phone', overflow <= 1, `${overflow}px`);
  const phonePinned = await small.evaluate(() =>
    getComputedStyle(document.querySelector('.ma-pin')).position);
  check('pinned sections are dropped on a phone', phonePinned === 'static', phonePinned);
  // With the pin dropped there is no timeline to reveal the steps, so every
  // one of them has to be readable as ordinary copy. They were not: three of
  // four sat at opacity 0 on a phone until the hidden state moved into CSS
  // scoped to the width where the animation runs.
  const hiddenSteps = await small.evaluate(() =>
    [...document.querySelectorAll('[data-step]')].filter(
      (el) => Number(getComputedStyle(el).opacity) < 0.9).length);
  check('every step is readable on a phone', hiddenSteps === 0, `${hiddenSteps} hidden`);
  await small.screenshot({ path: `${OUT}/phone-hero.png` });
  await small.evaluate(() => window.scrollTo(0, window.innerHeight * 2));
  await small.waitForTimeout(800);
  await small.screenshot({ path: `${OUT}/phone-scrolled.png` });
  await phone.close();

  section('Reduced motion');
  const calm = await browser.newContext({ viewport: { width: 1440, height: 900 }, reducedMotion: 'reduce' });
  const calmPage = await calm.newPage();
  await calmPage.goto(SITE, { waitUntil: 'networkidle' });
  await calmPage.waitForTimeout(800);
  check('no motion layer at all under reduced motion',
        !(await calmPage.evaluate(() => document.documentElement.classList.contains('ma-js'))));
  const headingVisible = await calmPage.evaluate(() => {
    const word = document.querySelector('.ma-word');
    return word ? getComputedStyle(word).opacity : '0';
  });
  check('copy is fully visible under reduced motion', Number(headingVisible) === 1, headingVisible);
  // Every v2 technique needs a still form, not just the original set.
  const calmState = await calmPage.evaluate(() => {
    const line = document.querySelector('[data-chart-line]');
    const screens = [...document.querySelectorAll('[data-screen]')];
    const counts = [...document.querySelectorAll('[data-count-to]')];
    return {
      chartDrawn: line ? getComputedStyle(line).strokeDasharray : 'missing',
      screensVisible: screens.every((el) => Number(getComputedStyle(el).opacity) === 1),
      countsShown: counts.every((el) => el.textContent === el.dataset.countTo),
    };
  });
  check('the chart is simply drawn under reduced motion',
        calmState.chartDrawn === 'none', calmState.chartDrawn);
  check('every morph screen is visible under reduced motion', calmState.screensVisible);
  check('numbers are shown, not counted, under reduced motion', calmState.countsShown);
  await calmPage.screenshot({ path: `${OUT}/reduced-motion.png` });
  await calm.close();

  section('No JavaScript at all');
  const noJs = await browser.newContext({ viewport: { width: 1440, height: 900 }, javaScriptEnabled: false });
  const plain = await noJs.newPage();
  await plain.goto(SITE, { waitUntil: 'load' });
  const plainText = (await plain.locator('body').innerText()).replace(/\u00a0/g, ' ');
  check('the page still reads with JavaScript off', plainText.includes('The gym is the game.'),
        plainText.slice(0, 120));
  await plain.screenshot({ path: `${OUT}/no-javascript.png` });
  await noJs.close();

  section('Waitlist');
  const form = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const formPage = await form.newPage();
  await formPage.goto(SITE, { waitUntil: 'networkidle' });
  await formPage.locator('#waitlist-email').first().fill(`site-${Date.now()}@example.com`);
  await formPage.getByRole('button', { name: 'JOIN THE WAITLIST' }).first().click();
  await formPage.getByText("You're on the list.").first().waitFor({ timeout: 15000 });
  check('the waitlist accepts an address', true);
  await formPage.screenshot({ path: `${OUT}/waitlist-done.png` });
  await form.close();
} catch (err) {
  failed.push(`aborted: ${err.message.split('\n')[0]}`);
  console.log('  ABORT', err.message.split('\n')[0]);
} finally {
  await browser.close();
}

console.log(`\n${failed.length ? `${failed.length} FAILED` : 'ALL PASSED'} (${passed} passed) - screenshots in ${OUT}`);
for (const f of failed) console.log('  -', f);
process.exit(failed.length ? 1 : 0);
