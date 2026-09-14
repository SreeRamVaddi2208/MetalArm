"""The story card, drawn in the browser.

The workout summary's SHARE button draws a 1080 x 1920 PNG on a <canvas> - the
same grey-steel card the iOS app renders (ios/MetalARM/Views/ShareCard.swift) -
then hands it to the system share sheet on touch screens (phones) that can
share files, or downloads it otherwise. Every word on it comes from the server's
finish response, via FinishSummary and WorkoutState.share_card.

The drawing code travels with each click (rx.call_script), so no page has to
pre-load a script for a button most people press rarely.
"""

from __future__ import annotations

import json
from typing import Any

from metalarm import theme

_DRAW = """
window.maShareCard = function (card) {
  const W = 1080, H = 1920;
  const canvas = document.createElement('canvas');
  canvas.width = W;
  canvas.height = H;
  const g = canvas.getContext('2d');
  const font = (weight, size) =>
    `${weight} ${size}px ui-sans-serif, system-ui, -apple-system, "Segoe UI", Roboto, sans-serif`;
  const spaced = (px) => { if ('letterSpacing' in g) g.letterSpacing = px + 'px'; };
  const roundRect = (x, y, w, h, r) => {
    g.beginPath();
    g.moveTo(x + r, y);
    g.arcTo(x + w, y, x + w, y + h, r);
    g.arcTo(x + w, y + h, x, y + h, r);
    g.arcTo(x, y + h, x, y, r);
    g.arcTo(x, y, x + w, y, r);
    g.closePath();
  };

  g.fillStyle = '__BG__';
  g.fillRect(0, 0, W, H);
  const glow = g.createRadialGradient(W / 2, H * 0.4, 0, W / 2, H * 0.4, 900);
  glow.addColorStop(0, 'rgba(192, 192, 200, 0.28)');
  glow.addColorStop(1, 'rgba(192, 192, 200, 0)');
  g.fillStyle = glow;
  g.fillRect(0, 0, W, H);
  g.textAlign = 'center';

  g.font = font(700, 42); g.fillStyle = '__DIM__'; spaced(18);
  g.fillText('METALARM', W / 2, 210);
  g.font = font(700, 48); g.fillStyle = '__SILVER__'; spaced(15);
  g.fillText(card.eyebrow, W / 2, 760);
  spaced(0);

  // The headline shrinks until it fits, then gets the brushed-silver fill.
  let size = 360;
  g.font = font(800, size);
  while (g.measureText(card.headline).width > W - 160 && size > 120) {
    size -= 10;
    g.font = font(800, size);
  }
  const top = 800;
  const metal = g.createLinearGradient(0, top, 0, top + size);
  metal.addColorStop(0, '#ffffff');
  metal.addColorStop(0.55, '#c0c0c8');
  metal.addColorStop(1, '#6a6a72');
  g.fillStyle = metal;
  g.shadowColor = 'rgba(255, 255, 255, 0.3)';
  g.shadowBlur = 50;
  g.textBaseline = 'top';
  g.fillText(card.headline, W / 2, top);
  g.shadowBlur = 0;
  g.textBaseline = 'alphabetic';

  g.font = font(500, 46); g.fillStyle = '__TEXT__';
  let line = '', y = top + size + 100;
  for (const word of card.caption.split(' ')) {
    const next = line ? line + ' ' + word : word;
    if (g.measureText(next).width > W - 200 && line) {
      g.fillText(line, W / 2, y);
      line = word;
      y += 62;
    } else {
      line = next;
    }
  }
  if (line) g.fillText(line, W / 2, y);

  const gap = 30, boxTop = 1530, boxH = 170;
  const boxW = (W - 144 - gap * (card.stats.length - 1)) / card.stats.length;
  card.stats.forEach((stat, i) => {
    const x = 72 + i * (boxW + gap);
    roundRect(x, boxTop, boxW, boxH, 36);
    g.fillStyle = '__CARD__'; g.fill();
    g.strokeStyle = '__BORDER__'; g.lineWidth = 3; g.stroke();
    g.fillStyle = '__TEXT__'; g.font = font(700, 50);
    g.fillText(stat.value, x + boxW / 2, boxTop + 82);
    g.fillStyle = '__DIM__'; g.font = font(500, 32);
    g.fillText(stat.label, x + boxW / 2, boxTop + 132);
  });

  g.font = font(600, 38); g.fillStyle = '__DIM__';
  g.fillText(card.footer, W / 2, 1810);

  canvas.toBlob(async (blob) => {
    const name = 'metalarm-' + card.kind + '.png';
    const file = new File([blob], name, { type: 'image/png' });
    // The share sheet only on touch screens (phones), where posting to a story
    // is the point; a desktop gets the file. Desktop Chrome can share files
    // too, but its sheet is an odd fit - and headless, it never resolves.
    const touch = window.matchMedia && window.matchMedia('(pointer: coarse)').matches;
    if (touch && navigator.canShare && navigator.canShare({ files: [file] })) {
      try {
        await navigator.share({ files: [file], title: 'MetalArm' });
        return;
      } catch (error) {
        if (error && error.name === 'AbortError') return;
      }
    }
    const link = document.createElement('a');
    link.href = URL.createObjectURL(blob);
    link.download = name;
    document.body.appendChild(link);
    link.click();
    link.remove();
    setTimeout(() => URL.revokeObjectURL(link.href), 4000);
  }, 'image/png');
};
"""

_COLOURS = {
    "__BG__": theme.BG,
    "__DIM__": theme.MUTED,
    "__SILVER__": theme.RANK_COLORS["B"],
    "__TEXT__": theme.TEXT,
    "__CARD__": theme.PANEL,
    "__BORDER__": theme.BORDER_HI,
}

_SCRIPT = _DRAW
for _token, _value in _COLOURS.items():
    _SCRIPT = _SCRIPT.replace(_token, _value)


def share_card_script(card: dict[str, Any]) -> str:
    """JavaScript that draws `card` and shares or downloads it."""
    return _SCRIPT + f"window.maShareCard({json.dumps(card)});"
