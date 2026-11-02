// Turn the SVGs scripts/exercise_diagrams.py drew into transparent PNGs in
// frontend/assets, using the locally installed Chrome.
//     node scripts/e2e/rasterise_figures.mjs <build directory>
import { mkdirSync, readFileSync, readdirSync } from 'node:fs';
import { dirname, join, relative } from 'node:path';
import { fileURLToPath } from 'node:url';
import { chromium } from 'playwright-core';

const SIZE = 480;
const assets = join(dirname(fileURLToPath(import.meta.url)), '..', '..', 'frontend', 'assets');
const build = process.argv[2];
if (!build) {
  console.error('usage: node rasterise_figures.mjs <build directory>');
  process.exit(2);
}

const browser = await chromium.launch({ channel: 'chrome' });
const page = await browser.newPage({ viewport: { width: SIZE, height: SIZE } });
let count = 0;
for (const entry of readdirSync(build, { recursive: true, withFileTypes: true })) {
  if (!entry.name.endsWith('.svg')) continue;
  const source = join(entry.parentPath, entry.name);
  const out = join(assets, relative(build, source)).replace(/\.svg$/, '.png');
  mkdirSync(dirname(out), { recursive: true });
  await page.setContent(`<!doctype html><style>html,body{margin:0;background:transparent}svg{display:block;width:${SIZE}px;height:${SIZE}px}</style>${readFileSync(source, 'utf8')}`);
  await page.screenshot({ path: out, omitBackground: true });
  count += 1;
}
await browser.close();
console.log(`${count} PNGs in ${assets}`);
