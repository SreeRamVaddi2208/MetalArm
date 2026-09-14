// Renders metalarm-icon.svg into the iOS app icon and the web favicons, using
// the locally installed Chrome through scripts/e2e's playwright-core.
//
//   node scripts/icon/render_icon.mjs              # write the icons into the repo
//   node scripts/icon/render_icon.mjs --preview D  # write them plus a preview sheet to D
//
// Renders go through JPEG and are converted with sips, so every PNG is opaque:
// App Store Connect rejects an app icon with an alpha channel.

import { execFileSync } from 'node:child_process';
import { mkdirSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const here = dirname(fileURLToPath(import.meta.url));
const repo = resolve(here, '../..');
const { chromium } = createRequire(join(here, '../e2e/package.json'))('playwright-core');

const previewIndex = process.argv.indexOf('--preview');
const previewDir = previewIndex > -1 ? resolve(process.argv[previewIndex + 1]) : null;
const appIconDir = join(repo, 'ios/MetalARM/Assets.xcassets/AppIcon.appiconset');
const webAssets = join(repo, 'frontend/assets');

const outputs = [
  { file: 'AppIcon-1024.png', dir: appIconDir, size: 1024 },
  { file: 'AppIcon-tinted-1024.png', dir: appIconDir, size: 1024, tinted: true },
  { file: 'apple-touch-icon.png', dir: webAssets, size: 180 },
  { file: 'favicon.png', dir: webAssets, size: 64 },
];

// The page is rendered from a string (no file origin), so Chrome would refuse the
// SVG's relative font URL; inline the bundled TTF instead.
const fontPath = join(repo, 'ios/MetalARM/Fonts/SpaceGrotesk-Bold.ttf');
const svg = readFileSync(join(here, 'metalarm-icon.svg'), 'utf8').replace(
  /url\("[^"]*SpaceGrotesk-Bold\.ttf"\)/,
  `url("data:font/ttf;base64,${readFileSync(fontPath).toString('base64')}")`,
);

// The tinted (iOS 18) variant: grayscale artwork on black, no coloured glow.
function page(tinted) {
  return `<!doctype html><html><head><base href="${pathToFileURL(here + '/').href}">
<style>
  html, body { margin: 0; background: #000; }
  svg { display: block; width: 100vw; height: 100vh; }
  ${tinted ? '#glowLayer { display: none; } #bg { fill: #000; } svg { filter: grayscale(1) contrast(1.15); }' : ''}
</style></head><body>${svg}</body></html>`;
}

const launchOptions = process.env.CHROME_PATH
  ? { executablePath: process.env.CHROME_PATH, headless: true }
  : { channel: 'chrome', headless: true };
const browser = await chromium.launch(launchOptions);

try {
  const written = [];
  for (const output of outputs) {
    const dir = previewDir ?? output.dir;
    mkdirSync(dir, { recursive: true });
    const context = await browser.newContext({ viewport: { width: output.size, height: output.size }, deviceScaleFactor: 1 });
    const tab = await context.newPage();
    await tab.setContent(page(output.tinted), { waitUntil: 'load' });
    await tab.evaluate(() => document.fonts.ready);
    if (!(await tab.evaluate(() => document.fonts.check('600px SpaceGroteskIcon')))) {
      throw new Error('Space Grotesk did not load - check the @font-face path in metalarm-icon.svg');
    }
    const jpeg = join(dir, output.file.replace(/\.png$/, '.jpg'));
    await tab.screenshot({ path: jpeg, type: 'jpeg', quality: 100 });
    execFileSync('sips', ['-s', 'format', 'png', jpeg, '--out', join(dir, output.file)], { stdio: 'ignore' });
    rmSync(jpeg);
    await context.close();
    written.push(join(dir, output.file));
  }

  if (previewDir) {
    // Home-screen sizes use Apple's ~22.37% corner radius as a squircle stand-in.
    const tile = (size, file = 'AppIcon-1024.png') =>
      `<figure><img src="${file}" style="width:${size}px;height:${size}px;border-radius:${size * 0.2237}px"><figcaption>${size}px</figcaption></figure>`;
    const sheet = `<!doctype html><html><head><base href="${pathToFileURL(previewDir + '/').href}"><style>
      body { margin: 0; padding: 40px; background: #1c1f26; color: #c9ced8; font: 14px -apple-system, sans-serif; }
      h2 { font-weight: 600; margin: 28px 0 14px; }
      .row { display: flex; gap: 32px; align-items: flex-end; flex-wrap: wrap; }
      figure { margin: 0; text-align: center; } figcaption { margin-top: 8px; opacity: .7; }
      .tab { display: inline-flex; gap: 8px; align-items: center; background: #f1f3f4; color: #202124; padding: 8px 14px; border-radius: 8px 8px 0 0; }
      .tab.dark { background: #35363a; color: #e8eaed; }
    </style></head><body>
      <h2>App icon</h2>
      <div class="row">${tile(360)}${tile(180)}${tile(120)}${tile(60)}
        <figure><img src="AppIcon-tinted-1024.png" style="width:180px;height:180px;border-radius:${180 * 0.2237}px"><figcaption>tinted</figcaption></figure></div>
      <h2>Web</h2>
      <div class="row"><span class="tab"><img src="favicon.png" width="16" height="16"> MetalArm</span>
        <span class="tab dark"><img src="favicon.png" width="16" height="16"> MetalArm</span>
        <figure><img src="favicon.png" width="32" height="32"><figcaption>32px</figcaption></figure>
        <figure><img src="apple-touch-icon.png" style="width:90px;height:90px;border-radius:20px"><figcaption>apple-touch</figcaption></figure></div>
    </body></html>`;
    // Opened from a file so its file:// images are allowed to load.
    const sheetPath = join(previewDir, 'preview.html');
    writeFileSync(sheetPath, sheet);
    const context = await browser.newContext({ viewport: { width: 1180, height: 760 }, deviceScaleFactor: 2 });
    const tab = await context.newPage();
    await tab.goto(pathToFileURL(sheetPath).href, { waitUntil: 'load' });
    await tab.screenshot({ path: join(previewDir, 'preview.png'), fullPage: true });
    await context.close();
    written.push(join(previewDir, 'preview.png'));
  }
  console.log(written.join('\n'));
} finally {
  await browser.close();
}
