"use client";

import { MonthPoint, CategoryShare, categoryColor } from "./types";

const WIDTH = 600;
const HEIGHT = 220;
const PAD_LEFT = 52;
const PAD_BOTTOM = 24;
const PAD_TOP = 12;

export function LineChart({ points, formatY }: { points: MonthPoint[]; formatY: (n: number) => string }) {
  const values = points.map((p) => Number(p.value));
  const max = Math.max(...values, 1);
  const plotW = WIDTH - PAD_LEFT - 10;
  const plotH = HEIGHT - PAD_TOP - PAD_BOTTOM;
  const stepX = points.length > 1 ? plotW / (points.length - 1) : 0;

  const coords = values.map((v, i) => ({
    x: PAD_LEFT + i * stepX,
    y: PAD_TOP + plotH - (v / max) * plotH,
  }));

  const linePath = coords.map((c, i) => `${i === 0 ? "M" : "L"} ${c.x} ${c.y}`).join(" ");
  const areaPath = `${linePath} L ${coords[coords.length - 1]?.x ?? PAD_LEFT} ${PAD_TOP + plotH} L ${PAD_LEFT} ${PAD_TOP + plotH} Z`;

  const ticks = 4;
  const gridLines = Array.from({ length: ticks + 1 }, (_, i) => {
    const y = PAD_TOP + (plotH / ticks) * i;
    const value = max - (max / ticks) * i;
    return { y, value };
  });

  return (
    <svg viewBox={`0 0 ${WIDTH} ${HEIGHT}`} className="w-full h-auto" preserveAspectRatio="xMidYMid meet">
      {gridLines.map((g, i) => (
        <g key={i}>
          <line x1={PAD_LEFT} x2={WIDTH - 10} y1={g.y} y2={g.y} stroke="#eef0f4" strokeWidth={1} />
          <text x={PAD_LEFT - 8} y={g.y + 4} textAnchor="end" fontSize="10" fill="#9aa1ac">
            {formatY(g.value)}
          </text>
        </g>
      ))}
      <path d={areaPath} fill="#2563eb" fillOpacity={0.08} stroke="none" />
      <path d={linePath} fill="none" stroke="#2563eb" strokeWidth={2.5} strokeLinecap="round" strokeLinejoin="round" />
      {coords.map((c, i) => (
        <circle key={i} cx={c.x} cy={c.y} r={3} fill="#2563eb" />
      ))}
      {points.map((p, i) => (
        <text key={p.label + i} x={PAD_LEFT + i * stepX} y={HEIGHT - 4} textAnchor="middle" fontSize="11" fill="#9aa1ac">
          {p.label}
        </text>
      ))}
    </svg>
  );
}

export function BarChart({ points }: { points: MonthPoint[] }) {
  const values = points.map((p) => Number(p.value));
  const max = Math.max(...values, 1);
  const plotW = WIDTH - PAD_LEFT - 10;
  const plotH = HEIGHT - PAD_TOP - PAD_BOTTOM;
  const slot = plotW / points.length;
  const barW = Math.min(40, slot * 0.55);

  const ticks = 4;
  const gridLines = Array.from({ length: ticks + 1 }, (_, i) => {
    const y = PAD_TOP + (plotH / ticks) * i;
    const value = Math.round(max - (max / ticks) * i);
    return { y, value };
  });

  return (
    <svg viewBox={`0 0 ${WIDTH} ${HEIGHT}`} className="w-full h-auto" preserveAspectRatio="xMidYMid meet">
      {gridLines.map((g, i) => (
        <g key={i}>
          <line x1={PAD_LEFT} x2={WIDTH - 10} y1={g.y} y2={g.y} stroke="#eef0f4" strokeWidth={1} />
          <text x={PAD_LEFT - 8} y={g.y + 4} textAnchor="end" fontSize="10" fill="#9aa1ac">
            {g.value}
          </text>
        </g>
      ))}
      {points.map((p, i) => {
        const v = Number(p.value);
        const h = (v / max) * plotH;
        const x = PAD_LEFT + i * slot + (slot - barW) / 2;
        const y = PAD_TOP + plotH - h;
        return (
          <g key={p.label + i}>
            <rect x={x} y={y} width={barW} height={Math.max(h, 1)} rx={4} fill="#10b981" />
            <text x={x + barW / 2} y={HEIGHT - 4} textAnchor="middle" fontSize="11" fill="#9aa1ac">
              {p.label}
            </text>
          </g>
        );
      })}
    </svg>
  );
}

export function DonutChart({ shares, size = 200 }: { shares: CategoryShare[]; size?: number }) {
  const radius = size / 2;
  const innerRadius = radius * 0.58;
  const cx = radius;
  const cy = radius;

  const total = shares.reduce((sum, s) => sum + s.pct, 0) || 1;
  // Precompute cumulative-before-each-slice as a pure array (no mutation
  // during the render-time .map below) — avoids reassigning an
  // outer-scope variable while rendering, which the React Compiler's
  // eslint plugin flags as unsafe for memoization.
  const cumulativeStarts = shares.reduce<number[]>((acc, s, i) => {
    acc.push(i === 0 ? 0 : acc[i - 1] + shares[i - 1].pct);
    return acc;
  }, []);

  const arcs = shares.map((s, i) => {
    const cumulativeBefore = cumulativeStarts[i];
    const cumulativeAfter = cumulativeBefore + s.pct;
    const startAngle = (cumulativeBefore / total) * 2 * Math.PI - Math.PI / 2;
    const endAngle = (cumulativeAfter / total) * 2 * Math.PI - Math.PI / 2;

    const largeArc = endAngle - startAngle > Math.PI ? 1 : 0;
    const x1 = cx + radius * Math.cos(startAngle);
    const y1 = cy + radius * Math.sin(startAngle);
    const x2 = cx + radius * Math.cos(endAngle);
    const y2 = cy + radius * Math.sin(endAngle);
    const ix1 = cx + innerRadius * Math.cos(endAngle);
    const iy1 = cy + innerRadius * Math.sin(endAngle);
    const ix2 = cx + innerRadius * Math.cos(startAngle);
    const iy2 = cy + innerRadius * Math.sin(startAngle);

    const path = [
      `M ${x1} ${y1}`,
      `A ${radius} ${radius} 0 ${largeArc} 1 ${x2} ${y2}`,
      `L ${ix1} ${iy1}`,
      `A ${innerRadius} ${innerRadius} 0 ${largeArc} 0 ${ix2} ${iy2}`,
      "Z",
    ].join(" ");

    return { path, color: categoryColor(s.category, i) };
  });

  return (
    <svg viewBox={`0 0 ${size} ${size}`} width={size} height={size}>
      {arcs.map((a, i) => (
        <path key={i} d={a.path} fill={a.color} />
      ))}
    </svg>
  );
}
