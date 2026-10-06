// Renders everything the demo film needs besides the screen recordings:
// a voice clip per chapter (macOS `say`), a caption strip per chapter, and
// the title and end cards - all from narration.json.
//
//   node scripts/demo/render_assets.mjs <assets-dir>
//
// Captions are PNGs drawn by headless Chrome rather than ffmpeg drawtext,
// because Homebrew's ffmpeg is built without it. The film is 1920x1080: the
// app fills the top 960 pixels and the caption owns the 120-pixel band below,
// so a caption never covers what it is describing.
//
// Writes <assets-dir>/durations.json (seconds per voice clip), which the web
// tour reads so every chapter holds at least as long as its narration.

import { execFileSync } from 'node:child_process';
import { mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const here = dirname(fileURLToPath(import.meta.url));
const require = createRequire(join(here, '..', 'e2e', 'package.json'));
const { chromium } = require('playwright-core');

const OUT = process.argv[2];
if (!OUT) { console.error('usage: node render_assets.mjs <assets-dir>'); process.exit(2); }
const narration = JSON.parse(readFileSync(join(here, 'narration.json'), 'utf8'));
const VOICE = process.env.DEMO_VOICE || 'Samantha';
const RATE = process.env.DEMO_RATE || '182';

// MetalArm's palette (frontend/metalarm/theme.py) and system font stack.
const FONT = "-apple-system, BlinkMacSystemFont, 'SF Pro Display', 'Helvetica Neue', Helvetica, Arial, sans-serif"; // single-quoted names: it goes inside a double-quoted style attribute
const BG = '#0b0b0c', PANEL = '#1a1a1d', TEXT = '#f2f2f4', MUTED = '#8e8e96', BORDER = '#2a2a2f';

function seconds(file) {
  return Number(execFileSync('ffprobe', ['-v', 'error', '-show_entries', 'format=duration',
    '-of', 'csv=p=0', file]).toString().trim());
}

const caption = (part, index, total, text) => `<!doctype html><html><body style="margin:0">
<div style="width:1920px;height:120px;background:${BG};border-top:1px solid ${BORDER};
  display:flex;align-items:center;gap:28px;padding:0 64px;box-sizing:border-box;font-family:${FONT}">
  <div style="font-weight:900;letter-spacing:.32em;font-size:20px;color:${TEXT}">METALARM</div>
  <div style="width:1px;height:44px;background:${BORDER}"></div>
  <div style="flex:1;font-size:38px;font-weight:700;color:${TEXT};letter-spacing:.01em">${text}</div>
  <div style="font-size:18px;color:${MUTED};letter-spacing:.18em;font-weight:700">${part} · ${index}/${total}</div>
</div></body></html>`;

const card = (eyebrow, headline, line) => `<!doctype html><html><body style="margin:0">
<div style="width:1920px;height:1080px;background:radial-gradient(circle at 50% 42%, ${PANEL} 0%, ${BG} 62%);
  display:flex;flex-direction:column;align-items:center;justify-content:center;gap:28px;font-family:${FONT}">
  <div style="font-size:24px;letter-spacing:.5em;color:${MUTED};font-weight:800">${eyebrow}</div>
  <div style="font-size:150px;font-weight:900;letter-spacing:.12em;color:${TEXT}">${headline}</div>
  <div style="font-size:34px;color:${MUTED};letter-spacing:.06em">${line}</div>
</div></body></html>`;

mkdirSync(OUT, { recursive: true });
const durations = {};
const launch = process.env.CHROME_PATH
  ? { executablePath: process.env.CHROME_PATH, headless: true }
  : { channel: 'chrome', headless: true };
const browser = await chromium.launch(launch);
const page = await browser.newPage({ viewport: { width: 1920, height: 1080 } });

for (const part of ['web', 'ios']) {
  const chapters = narration[part];
  mkdirSync(join(OUT, part), { recursive: true });
  durations[part] = {};
  for (const [i, ch] of chapters.entries()) {
    const aiff = join(OUT, part, `${ch.id}.aiff`);
    execFileSync('say', ['-v', VOICE, '-r', RATE, '-o', aiff, ch.voice]);
    durations[part][ch.id] = seconds(aiff);
    await page.setViewportSize({ width: 1920, height: 120 });
    await page.setContent(caption(part === 'web' ? 'WEB' : 'IPHONE', i + 1, chapters.length, ch.caption));
    await page.screenshot({ path: join(OUT, part, `${ch.id}.png`) });
  }
  console.log(`${part}: ${chapters.length} chapters, ${Object.values(durations[part]).reduce((a, b) => a + b, 0).toFixed(0)}s of narration`);
}

await page.setViewportSize({ width: 1920, height: 1080 });
await page.setContent(card('A STRENGTH TRACKER THAT PLAYS LIKE A GAME', 'METALARM', 'Full product tour · web and iPhone'));
await page.screenshot({ path: join(OUT, 'title.png') });
await page.setContent(card('THANKS FOR WATCHING', 'METALARM', 'Lift. Level. Repeat.'));
await page.screenshot({ path: join(OUT, 'end.png') });
await browser.close();

writeFileSync(join(OUT, 'durations.json'), JSON.stringify(durations, null, 1));
console.log(`assets in ${OUT}`);
