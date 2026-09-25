/**
 * The bench-press chart from the Progress screen, redrawn as SVG so it can
 * draw ITSELF as the section scrolls - a video cannot be stroked on.
 *
 * Only points the app actually shows are plotted: the capture reads "85 kg top
 * set, 12.5 kg since 2 Jun", and its personal records list gives 8 reps at
 * 80 kg on 5 Aug and 85 kg on 10 Sep. Inventing smooth intermediate points
 * would be inventing training that never happened, so there are three.
 */
const POINTS = [
  { label: '2 Jun', kg: 72.5 },
  { label: '5 Aug', kg: 80 },
  { label: '10 Sep', kg: 85 },
];

const W = 520;
const H = 220;
const PAD = { top: 24, right: 16, bottom: 34, left: 16 };

export default function Chart() {
  const min = 68;
  const max = 88;
  const x = (i) => PAD.left + (i * (W - PAD.left - PAD.right)) / (POINTS.length - 1);
  const y = (kg) => PAD.top + (1 - (kg - min) / (max - min)) * (H - PAD.top - PAD.bottom);
  const line = POINTS.map((p, i) => `${i === 0 ? 'M' : 'L'} ${x(i)} ${y(p.kg)}`).join(' ');
  const area = `${line} L ${x(POINTS.length - 1)} ${H - PAD.bottom} L ${x(0)} ${H - PAD.bottom} Z`;

  return (
    <figure className="rounded-2xl border border-border bg-panel p-5">
      <figcaption className="flex items-baseline gap-2">
        <span className="font-display text-3xl" data-count-to="85">85</span>
        <span className="text-sm text-muted">kg top set</span>
        <span className="ml-auto text-sm text-silver">&#9650; 12.5 kg since 2 Jun</span>
      </figcaption>
      <svg viewBox={`0 0 ${W} ${H}`} className="mt-4 w-full" role="img"
           aria-label="Bench press top set: 72.5 kg in June, 80 kg in August, 85 kg in September.">
        <defs>
          <linearGradient id="ma-fill" x1="0" x2="0" y1="0" y2="1">
            <stop offset="0%" stopColor="#d9b06a" stopOpacity="0.28" />
            <stop offset="100%" stopColor="#d9b06a" stopOpacity="0" />
          </linearGradient>
        </defs>
        <path d={area} fill="url(#ma-fill)" data-chart-area="" />
        <path
          d={line}
          fill="none"
          stroke="#d9b06a"
          strokeWidth="2.5"
          strokeLinecap="round"
          strokeLinejoin="round"
          data-chart-line=""
        />
        {POINTS.map((p, i) => (
          <g key={p.label}>
            <circle cx={x(i)} cy={y(p.kg)} r="4" fill="#0b0b0c" stroke="#d9b06a" strokeWidth="2"
                    data-chart-dot="" />
            <text x={x(i)} y={H - 10} textAnchor={i === 0 ? 'start' : i === POINTS.length - 1 ? 'end' : 'middle'}
                  fill="#7c7c84" fontSize="12">{p.label}</text>
          </g>
        ))}
      </svg>
    </figure>
  );
}
