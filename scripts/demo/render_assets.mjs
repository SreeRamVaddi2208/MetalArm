// Renders everything the demo film needs besides the screen recordings:
// a voice clip per chapter (macOS `say`), a caption strip per chapter, and
// the title and end cards - all from narration.json.
//
//   node scripts/demo/render_assets.mjs <assets-dir> [--narration <file>]
//
// --narration picks another script (default narration.json beside this file);
// a file may carry "cards" (title / end: eyebrow, headline, line) and "labels"
// (part -> the caption's part name).
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
const narrationArg = process.argv.indexOf('--narration');
const narrationFile = narrationArg > -1 ? process.argv[narrationArg + 1] : join(here, 'narration.json');
const narration = JSON.parse(readFileSync(narrationFile, 'utf8'));
const PARTS = Object.keys(narration).filter((k) => Array.isArray(narration[k]));
const LABELS = { web: 'WEB', ios: 'IPHONE', ...(narration.labels || {}) };
const CARDS = {
  title: { eyebrow: 'A STRENGTH TRACKER THAT PLAYS LIKE A GAME', headline: 'METALARM', line: 'Full product tour · web and iPhone' },
  end: { eyebrow: 'THANKS FOR WATCHING', headline: 'METALARM', line: 'Lift. Level. Repeat.' },
  ...(narration.cards || {}),
};
const VOICE = process.env.DEMO_VOICE || 'Samantha';
const RATE = process.env.DEMO_RATE || '182';

// MetalArm's tokens (frontend/metalarm/theme.py): flat near-black, one accent.
const FONT = "-apple-system, BlinkMacSystemFont, 'SF Pro Display', 'Helvetica Neue', Helvetica, Arial, sans-serif"; // single-quoted names: it goes inside a double-quoted style attribute
const BG = '#0E0E10', TEXT = '#F4F4F2', MUTED = '#A1A1A8', BORDER = '#2A2A2F', ACCENT = '#FF6B2C';

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
<div style="width:1920px;height:1080px;background:${BG};
  display:flex;flex-direction:column;align-items:center;justify-content:center;gap:28px;font-family:${FONT}">
  <div style="font-size:24px;letter-spacing:.5em;color:${ACCENT};font-weight:800">${eyebrow}</div>
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

for (const part of PARTS) {
  const chapters = narration[part];
  mkdirSync(join(OUT, part), { recursive: true });
  durations[part] = {};
  for (const [i, ch] of chapters.entries()) {
    const aiff = join(OUT, part, `${ch.id}.aiff`);
    execFileSync('say', ['-v', VOICE, '-r', RATE, '-o', aiff, ch.voice]);
    durations[part][ch.id] = seconds(aiff);
    await page.setViewportSize({ width: 1920, height: 120 });
    await page.setContent(caption(LABELS[part] || part.toUpperCase(), i + 1, chapters.length, ch.caption));
    await page.screenshot({ path: join(OUT, part, `${ch.id}.png`) });
  }
  console.log(`${part}: ${chapters.length} chapters, ${Object.values(durations[part]).reduce((a, b) => a + b, 0).toFixed(0)}s of narration`);
}

await page.setViewportSize({ width: 1920, height: 1080 });
await page.setContent(card(CARDS.title.eyebrow, CARDS.title.headline, CARDS.title.line));
await page.screenshot({ path: join(OUT, 'title.png') });
await page.setContent(card(CARDS.end.eyebrow, CARDS.end.headline, CARDS.end.line));
await page.screenshot({ path: join(OUT, 'end.png') });
await browser.close();

writeFileSync(join(OUT, 'durations.json'), JSON.stringify(durations, null, 1));
console.log(`assets in ${OUT}`);
