import { animate, motion, useInView } from 'framer-motion';
import { BarChart3, Table2 } from 'lucide-react';
import { useEffect, useId, useMemo, useRef, useState, type ReactNode } from 'react';
import { useNavigate } from 'react-router-dom';
import { Bar, BarChart, CartesianGrid, Cell, LabelList, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import type { Bucket, Compliance, Stats } from '../api/types';
import { pct } from '../lib/format';
import { DUR, EASE, STAGGER, firstTime, lastSeen, markSeen, prefersReducedMotion } from '../lib/motion';
import { useT } from '../lib/prefs';
import { CountUp } from './ui';

export const BUCKETS: { key: Bucket; label: string; color: string }[] = [
  { key: 'active', label: 'Active', color: 'var(--chart-active)' },
  { key: 'pending', label: 'Pending Verification', color: 'var(--chart-pending)' },
  { key: 'discrepancy', label: 'Discrepancy', color: 'var(--chart-discrepancy)' },
  { key: 'maturing', label: 'Maturing in 90 Days', color: 'var(--chart-maturing)' },
  { key: 'released', label: 'Released', color: 'var(--chart-released)' },
  { key: 'closed', label: 'Closed / Other', color: 'var(--chart-closed)' },
];

export const tipStyle = {
  borderRadius: 8, border: '1px solid var(--line)', background: 'var(--card)', color: 'var(--text)', boxShadow: 'var(--shadow-md)', fontSize: 13, padding: '8px 12px',
};

// ---------------------------------------------------------------- frame: accessible label + "View as table"
export interface TableAlt {
  caption: string;
  columns: string[];
  rows: (string | number)[][];
}

/** Every chart sits in a frame: an aria-label that gives the key number, and a toggle to the same data as a table. */
/** `interactive`: the chart holds its own controls (legend buttons), so the figure is a labelled group, not an image
 * (an image's descendants are presentational and must not be focusable). */
export function ChartFrame({ label, table, children, className, interactive }: { label: string; table: TableAlt; children: ReactNode; className?: string; interactive?: boolean }) {
  const [asTable, setAsTable] = useState(false);
  const t = useT();
  const id = useId();
  return (
    <div className={`chart-frame ${className ?? ''}`}>
      <div className="chart-tools">
        <button type="button" className="chart-toggle" aria-pressed={asTable} aria-controls={id} onClick={() => setAsTable(!asTable)}>
          {asTable ? <BarChart3 size={14} aria-hidden /> : <Table2 size={14} aria-hidden />} {t(asTable ? 'View as chart' : 'View as table')}
        </button>
      </div>
      <div id={id}>
        {asTable ? (
          <div className="table-wrap" tabIndex={0} role="region" aria-label={table.caption}>
            <table className="tbl tight">
              <caption className="sr-only">{table.caption}</caption>
              <thead><tr>{table.columns.map((c, i) => <th key={c} scope="col" className={i ? 'r' : ''}>{t(c)}</th>)}</tr></thead>
              <tbody>
                {table.rows.map((r, i) => (
                  <tr key={i}>{r.map((c, j) => (j === 0 ? <th key={j} scope="row" className="th-row">{typeof c === 'string' ? t(c) : c}</th> : <td key={j} className="r num">{c}</td>))}</tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <figure className="chart-fig" role={interactive ? 'group' : 'img'} aria-label={label}>
            {children}
          </figure>
        )}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------- data-change tracking
/** First view of a chart in this session plays its reveal; later views render at rest. Changed values pulse once. */
function useChartMotion(id: string, values: Record<string, number>) {
  const [reveal] = useState(() => !prefersReducedMotion() && firstTime(`chart:${id}`));
  const prev = useRef<Record<string, number | undefined>>(Object.fromEntries(Object.keys(values).map((k) => [k, lastSeen(`chart:${id}:${k}`)])));
  const [pulses, setPulses] = useState<Record<string, number>>({});
  const sig = JSON.stringify(values);
  useEffect(() => {
    const changed: string[] = [];
    for (const [k, v] of Object.entries(values)) {
      const p = prev.current[k];
      if (p !== undefined && p !== v) changed.push(k);
      prev.current[k] = v;
      markSeen(`chart:${id}:${k}`, v);
    }
    if (changed.length && !prefersReducedMotion()) setPulses((ps) => ({ ...ps, ...Object.fromEntries(changed.map((k) => [k, (ps[k] ?? 0) + 1])) }));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sig, id]);
  return { reveal, pulses };
}

interface ShapeProps { x?: number; y?: number; width?: number; height?: number; fill?: string; index?: number; payload?: { key?: string } }

/** A bar that grows from its baseline (600 ms ease-out, 40 ms stagger) on first view, and pulses once when its value changes. */
function GrowBar({ x = 0, y = 0, width = 0, height = 0, fill, index = 0, reveal, inView, pulse, horizontal, radius = 2, onClick, label }: ShapeProps & {
  reveal: boolean; inView: boolean; pulse: number; horizontal?: boolean; radius?: number; onClick?: () => void; label?: string;
}) {
  const ref = useRef<SVGRectElement>(null);
  useEffect(() => {
    if (!pulse || !ref.current) return;
    const el = ref.current;
    const a = animate(el, horizontal ? { scaleX: [1, 1.05, 1], opacity: [1, 0.72, 1] } : { scaleY: [1, 1.07, 1], opacity: [1, 0.72, 1] }, { duration: DUR.pulse, ease: EASE.inOut });
    return () => a.stop();
  }, [pulse, horizontal]);
  if (width <= 0 || height <= 0) return null;
  const axis = horizontal ? 'scaleX' : 'scaleY';
  return (
    <motion.rect
      ref={ref} x={x} y={y} width={width} height={height} fill={fill} rx={radius}
      style={{ transformBox: 'fill-box', originX: 0, originY: 1, cursor: onClick ? 'pointer' : undefined }}
      initial={reveal ? { [axis]: 0 } : false}
      animate={reveal && !inView ? { [axis]: 0 } : { [axis]: 1 }}
      transition={{ duration: DUR.bars, ease: EASE.out, delay: index * STAGGER }}
      onClick={onClick}
      aria-label={label}
    />
  );
}

// ---------------------------------------------------------------- status bars
/** Bar chart of FDR counts by lifecycle bucket (dashboards, reports). */
export function StatusBars({ stats, variant, height = 190, onBar, id }: { stats: Stats; variant: 'aicte' | 'auditor'; height?: number; onBar?: (k: string) => void; id: string }) {
  const t = useT();
  const total = stats.total.count;
  const data = BUCKETS.map((b) => ({ key: b.key, name: t(b.label), value: stats.by_bucket[b.key].count, color: b.color, pct: pct(stats.by_bucket[b.key].count, total) }));
  const aud = variant === 'auditor';
  const max = Math.max(800, Math.ceil(Math.max(...data.map((d) => d.value)) / 200) * 200);
  const box = useRef<HTMLDivElement>(null);
  const inView = useInView(box, { once: true, amount: 0.3 });
  const { reveal, pulses } = useChartMotion(id, Object.fromEntries(data.map((d) => [d.key, d.value])));
  const top = data.reduce((a, b) => (b.value > a.value ? b : a));

  const Tick = ({ x, y, payload }: { x?: number; y?: number; payload?: { value: string } }) => {
    const d = data.find((q) => q.name === payload?.value)!;
    const words = d.name.split(' ');
    const lines = words.length > 2 ? [words.slice(0, Math.ceil(words.length / 2)).join(' '), words.slice(Math.ceil(words.length / 2)).join(' ')] : words.length === 2 && d.name.length > 12 ? words : [d.name];
    if (!aud) lines.push(`(${d.pct}%)`);
    return (
      <text x={x} y={(y ?? 0) + 6} textAnchor="middle" fontSize={12} fill="var(--text)">
        {lines.map((l, i) => <tspan key={i} x={x} dy={i ? 14 : 8}>{l}</tspan>)}
      </text>
    );
  };

  const Label = (p: { x?: number | string; y?: number | string; width?: number | string; index?: number }) => {
    const d = data[p.index ?? 0];
    const cx = Number(p.x) + Number(p.width) / 2;
    const y = Number(p.y);
    return (
      <g>
        <text x={cx} y={aud ? y - 20 : y - 8} textAnchor="middle" fontSize={14} fontWeight={700} fill="var(--navy)" className="num">{d.value}</text>
        {aud && <text x={cx} y={y - 6} textAnchor="middle" fontSize={12} fill="var(--text)">({d.pct}%)</text>}
      </g>
    );
  };

  return (
    <ChartFrame
      label={`FDR status distribution, ${total} FDRs. Largest: ${top.name} ${top.value}. ${data.map((d) => `${d.name} ${d.value}`).join(', ')}.`}
      table={{ caption: `FDR status distribution (total ${total})`, columns: ['Status', 'Count', 'Share'], rows: data.map((d) => [d.name, d.value, `${d.pct}%`]) }}>
      <div ref={box}>
        <ResponsiveContainer width="100%" height={height}>
          <BarChart data={data} margin={{ top: aud ? 32 : 20, right: 8, left: 0, bottom: 0 }} barCategoryGap="22%" accessibilityLayer={false}>
            <CartesianGrid vertical={false} stroke="var(--line)" />
            <XAxis dataKey="name" interval={0} tickLine={false} axisLine={{ stroke: 'var(--line)' }} tick={<Tick />} height={aud ? 44 : 52} />
            <YAxis tickLine={false} axisLine={false} domain={[0, max]} ticks={[0, 200, 400, 600, 800].filter((v) => v <= max)} fontSize={12} tick={{ fill: 'var(--text)' }} width={aud ? 36 : 48}
              label={aud ? undefined : { value: 'Number of FDRs', angle: -90, position: 'insideLeft', offset: 12, fontSize: 12, fill: 'var(--text)', dy: 40 }} />
            <Tooltip cursor={{ fill: 'var(--primary-50)' }} contentStyle={tipStyle} labelStyle={{ color: 'var(--navy)', fontWeight: 600 }} formatter={(v) => [`${v} FDRs`, '']} separator="" />
            <Bar dataKey="value" maxBarSize={aud ? 68 : 56} isAnimationActive={false}
              shape={(p: ShapeProps) => <GrowBar {...p} reveal={reveal} inView={inView} pulse={pulses[data[p.index ?? 0].key] ?? 0} onClick={onBar ? () => onBar(data[p.index ?? 0].key) : undefined} />}>
              {data.map((d) => <Cell key={d.key} fill={d.color} />)}
              <LabelList dataKey="value" content={Label} />
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
    </ChartFrame>
  );
}

// ---------------------------------------------------------------- simple bar series (reports)
export function SeriesBars({ id, data, xKey, yKey, name, height = 240, colorAt, horizontal, unit = '', caption }: {
  id: string; data: Record<string, string | number>[]; xKey: string; yKey: string; name: string; height?: number; colorAt?: (i: number) => string; horizontal?: boolean; unit?: string; caption: string;
}) {
  const box = useRef<HTMLDivElement>(null);
  const inView = useInView(box, { once: true, amount: 0.3 });
  const values = useMemo(() => Object.fromEntries(data.map((d) => [String(d[xKey]), Number(d[yKey])])), [data, xKey, yKey]);
  const { reveal, pulses } = useChartMotion(id, values);
  const total = data.reduce((n, d) => n + Number(d[yKey]), 0);
  const peak = data.reduce<Record<string, string | number> | null>((a, b) => (!a || Number(b[yKey]) > Number(a[yKey]) ? b : a), null);
  const fill = (i: number) => colorAt?.(i) ?? 'var(--chart-primary)';
  return (
    <ChartFrame
      label={`${caption}. ${data.length} bars, total ${+total.toFixed(2)}${unit}. Highest: ${peak ? `${peak[xKey]} ${peak[yKey]}${unit}` : 'none'}.`}
      table={{ caption, columns: [horizontal ? 'Bank' : 'Month', name], rows: data.map((d) => [String(d[xKey]), `${d[yKey]}${unit}`]) }}>
      <div ref={box}>
        <ResponsiveContainer width="100%" height={height}>
          {horizontal ? (
            <BarChart data={data} layout="vertical" margin={{ top: 0, right: 40, left: 4, bottom: 0 }} accessibilityLayer={false}>
              <XAxis type="number" hide />
              <YAxis type="category" dataKey={xKey} fontSize={12} width={64} tickLine={false} axisLine={false} tick={{ fill: 'var(--text)' }} />
              <Tooltip contentStyle={tipStyle} labelStyle={{ color: 'var(--navy)', fontWeight: 600 }} cursor={{ fill: 'var(--primary-50)' }} />
              <Bar dataKey={yKey} name={name} barSize={12} isAnimationActive={false} label={{ position: 'right', fontSize: 12, fill: 'var(--text)' }}
                shape={(p: ShapeProps) => <GrowBar {...p} horizontal radius={3} reveal={reveal} inView={inView} pulse={pulses[String(data[p.index ?? 0][xKey])] ?? 0} />}>
                {data.map((_, i) => <Cell key={i} fill={fill(i)} />)}
              </Bar>
            </BarChart>
          ) : (
            <BarChart data={data} margin={{ top: 12, right: 8, left: -16, bottom: 0 }} accessibilityLayer={false}>
              <CartesianGrid vertical={false} stroke="var(--line)" />
              <XAxis dataKey={xKey} fontSize={12} tickLine={false} tick={{ fill: 'var(--text)' }} axisLine={{ stroke: 'var(--line)' }} />
              <YAxis fontSize={12} tickLine={false} axisLine={false} allowDecimals={false} tick={{ fill: 'var(--text)' }} />
              <Tooltip contentStyle={tipStyle} labelStyle={{ color: 'var(--navy)', fontWeight: 600 }} cursor={{ fill: 'var(--primary-50)' }} />
              <Bar dataKey={yKey} name={name} isAnimationActive={false}
                shape={(p: ShapeProps) => <GrowBar {...p} radius={4} reveal={reveal} inView={inView} pulse={pulses[String(data[p.index ?? 0][xKey])] ?? 0} />}>
                {data.map((_, i) => <Cell key={i} fill={fill(i)} />)}
              </Bar>
            </BarChart>
          )}
        </ResponsiveContainer>
      </div>
    </ChartFrame>
  );
}

// ---------------------------------------------------------------- donut
const R = 72;
const SW = 24;
const C = 2 * Math.PI * R;

/** Donut of FDR value by bucket. Segments draw clockwise in sequence (800 ms in total) on first view; hover or focus
 *  enlarges a segment and shows its count, value and share. */
export function ValueDonut({ stats, base, id }: { stats: Stats; base: string; id: string }) {
  const nav = useNavigate();
  const t = useT();
  const total = stats.total.amount_paise / 1e9;
  const data = BUCKETS.map((b) => ({ ...b, name: t(b.key === 'active' ? 'Active / Verified FDRs' : b.label), value: stats.by_bucket[b.key].amount_paise / 1e9, count: stats.by_bucket[b.key].count }));
  const box = useRef<HTMLDivElement>(null);
  const inView = useInView(box, { once: true, amount: 0.3 });
  const { reveal, pulses } = useChartMotion(id, Object.fromEntries(data.map((d) => [d.key, +d.value.toFixed(2)])));
  const [hover, setHover] = useState<number | null>(null);
  let acc = 0;
  const segs = data.map((d) => {
    const frac = total ? d.value / total : 0;
    const s = { ...d, frac, start: acc };
    acc += frac;
    return s;
  });
  const top = segs.reduce((a, b) => (b.value > a.value ? b : a));
  const h = hover !== null ? segs[hover] : null;
  const go = (k: Bucket) => nav(`${base}/${base === '/aicte' ? 'submissions' : 'fdrs'}?bucket=${k}`);

  return (
    <ChartFrame interactive
      label={`FDR value distribution, total ₹ ${total.toFixed(2)} crore. Largest: ${top.name} ₹ ${top.value.toFixed(2)} crore (${pct(top.value, total)}%).`}
      table={{ caption: `FDR value by status (₹ crore, total ${total.toFixed(2)})`, columns: ['Status', 'Count', 'Value (₹ Crore)', 'Share'], rows: segs.map((s) => [s.name, s.count, s.value.toFixed(2), `${pct(s.value, total)}%`]) }}>
      <div className="donut-wrap" ref={box}>
        <div className="donut">
          <svg viewBox="0 0 200 200" width="184" height="184" aria-hidden="true" focusable="false">
            <circle cx="100" cy="100" r={R} fill="none" stroke="var(--surface-3)" strokeWidth={SW} />
            <g transform="rotate(-90 100 100)">
              {segs.map((s, i) => s.frac > 0 && (
                <DonutSeg key={s.key} i={i} seg={s} reveal={reveal} inView={inView} pulse={pulses[s.key] ?? 0} active={hover === i}
                  onEnter={() => setHover(i)} onLeave={() => setHover((x) => (x === i ? null : x))} onGo={() => go(s.key)}
                  label={`${s.name}: ${s.count} FDRs, ₹ ${s.value.toFixed(2)} crore, ${pct(s.value, total)}%`} />
              ))}
            </g>
          </svg>
          <div className="donut-centre" aria-hidden={!!h}>
            {h ? (
              <div className="donut-tip" role="status">
                <b>{h.name}</b>
                <span className="num">{h.count} FDRs</span>
                <span className="num">₹ {h.value.toFixed(2)} Cr</span>
                <span className="num">{pct(h.value, total)}%</span>
              </div>
            ) : (
              <div>
                <div className="donut-total">₹ <CountUp id={`${id}:total`} value={total} decimals={2} /><br />{t('Crore')}</div>
                <div className="donut-sub">{t('Total FDRs')}</div>
              </div>
            )}
          </div>
        </div>
        <div className="dlegend">
          {segs.map((d, i) => (
            <button type="button" key={d.key} className={`dl-row${hover === i ? ' on' : ''}`} onMouseEnter={() => setHover(i)} onMouseLeave={() => setHover(null)}
              onFocus={() => setHover(i)} onBlur={() => setHover(null)} onClick={() => go(d.key)}
              aria-label={`${d.name}: ${d.count} FDRs, ₹ ${d.value.toFixed(2)} crore, ${pct(d.value, total)}%. Open the list`}>
              <span><i className="sw" style={{ background: d.color }} aria-hidden />{d.name}</span>
              <span className="v num">{d.value.toFixed(2)}</span>
              <span className="p num">({pct(d.value, total)}%)</span>
            </button>
          ))}
        </div>
      </div>
    </ChartFrame>
  );
}

function DonutSeg({ seg, i, reveal, inView, pulse, active, onEnter, onLeave, onGo, label }: {
  seg: { frac: number; start: number; color: string }; i: number; reveal: boolean; inView: boolean; pulse: number; active: boolean;
  onEnter: () => void; onLeave: () => void; onGo: () => void; label: string;
}) {
  const ref = useRef<SVGCircleElement>(null);
  const len = Math.max(0, seg.frac * C - 1.5); // 1.5 px gap between segments
  useEffect(() => {
    if (!pulse || !ref.current) return;
    const a = animate(ref.current, { opacity: [1, 0.6, 1] }, { duration: DUR.pulse, ease: EASE.inOut });
    return () => a.stop();
  }, [pulse]);
  const drawn = !reveal || inView;
  return (
    <motion.circle
      ref={ref} cx="100" cy="100" r={R} fill="none" stroke={seg.color} strokeWidth={SW}
      strokeDashoffset={-seg.start * C}
      initial={reveal ? { strokeDasharray: `0 ${C}` } : false}
      animate={{ strokeDasharray: drawn ? `${len} ${C}` : `0 ${C}`, scale: active ? 1.06 : 1 }}
      transition={{
        strokeDasharray: { duration: DUR.donut * seg.frac, delay: DUR.donut * seg.start, ease: 'linear' },
        scale: { duration: DUR.fast, ease: EASE.standard },
      }}
      style={{ transformBox: 'view-box', originX: '100px', originY: '100px', cursor: 'pointer', outline: 'none' }}
      className="donut-seg" data-i={i}
      onMouseEnter={onEnter} onMouseLeave={onLeave} onClick={onGo}
    >
      <title>{label}</title>
    </motion.circle>
  );
}

// ---------------------------------------------------------------- compliance bar
/** Horizontal stacked bar of institution compliance. Segments grow with transform only. */
export function ComplianceBar({ c, id }: { c: Compliance; id: string }) {
  const t = useT();
  const institutions = c.compliant + c.pending + c.discrepancy + c.no_valid_fdr;
  const parts = [
    { k: 'compliant', v: c.compliant, color: 'var(--chart-active)', label: 'Compliant' },
    { k: 'pending', v: c.pending, color: 'var(--chart-pending)', label: 'Pending Verification' },
    { k: 'discrepancy', v: c.discrepancy, color: 'var(--chart-discrepancy)', label: 'Has an FDR with a discrepancy' },
    { k: 'none', v: c.no_valid_fdr, color: 'var(--chart-none)', label: 'No Valid FDR' },
  ];
  const box = useRef<HTMLDivElement>(null);
  const inView = useInView(box, { once: true, amount: 0.3 });
  const { reveal, pulses } = useChartMotion(id, Object.fromEntries(parts.map((p) => [p.k, p.v])));
  return (
    <ChartFrame
      label={`Institution compliance: ${c.compliant} of ${institutions} institutions compliant (${pct(c.compliant, institutions)}%); ${c.pending} pending, ${c.discrepancy} with a discrepancy, ${c.no_valid_fdr} with no valid FDR.`}
      table={{ caption: `Institution compliance (${institutions} institutions)`, columns: ['Status', 'Institutions', 'Share'], rows: parts.map((p) => [p.label, p.v, `${pct(p.v, institutions)}%`]) }}>
      <div ref={box}>
        <div className="stackbar">
          {parts.map((p, i) => (
            <div key={p.k} style={{ flexBasis: `${(p.v / institutions) * 100}%` }} title={`${t(p.label)}: ${p.v}`}>
              <motion.div className={pulses[p.k] ? 'pulse-once' : undefined} key={pulses[p.k] ?? 0} style={{ background: p.color, height: '100%', originX: 0 }}
                initial={reveal ? { scaleX: 0 } : false} animate={{ scaleX: !reveal || inView ? 1 : 0 }}
                transition={{ duration: DUR.bars, delay: i * STAGGER, ease: EASE.out }} />
            </div>
          ))}
        </div>
        <div className="legend-grid">
          {parts.map((p) => (
            <div key={p.k}>
              <b style={{ color: p.k === 'none' ? 'var(--navy)' : p.color }}><CountUp id={`${id}:${p.k}`} value={p.v} /></b>
              <span>{t(p.label)}</span>
              <span className="num">({pct(p.v, institutions)}%)</span>
            </div>
          ))}
        </div>
      </div>
    </ChartFrame>
  );
}
