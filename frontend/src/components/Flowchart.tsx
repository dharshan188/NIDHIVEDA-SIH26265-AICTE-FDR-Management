import { motion, useInView } from 'framer-motion';
import { AlertTriangle, BadgeCheck, Bell, Check, FileCheck2, FileUp, Gavel, HandCoins, Landmark, RefreshCw, ScanSearch, Send, Unlock } from 'lucide-react';
import { useRef, useState, type ReactNode } from 'react';
import { DUR, EASE, STAGGER, firstTime, prefersReducedMotion } from '../lib/motion';
import { useT } from '../lib/prefs';
import { ChartFrame } from './Charts';

export type NodeId = 'submit' | 'docs' | 'bank' | 'disc' | 'active' | 'monitor' | 'decide' | 'renew' | 'request' | 'scrutiny' | 'authority' | 'released';
export type NodeState = 'done' | 'current' | 'todo' | 'alert';

interface N { x: number; y: number; label: string; sub: string; full: string; icon: ReactNode; diamond?: boolean }

const NODES: Record<NodeId, N> = {
  submit: { x: 85, y: 165, label: 'FDR Submitted', sub: 'by Institution', full: 'FDR Submitted', icon: <FileUp size={15} /> },
  docs: { x: 250, y: 165, label: 'Document Check', sub: 'Completeness', full: 'Document Check', icon: <ScanSearch size={15} /> },
  bank: { x: 420, y: 165, label: 'Bank', sub: 'Verification', full: 'Bank Verification', icon: <Landmark size={15} />, diamond: true },
  disc: { x: 420, y: 46, label: 'Discrepancy', sub: 'Clarification', full: 'Discrepancy Clarification', icon: <AlertTriangle size={15} /> },
  active: { x: 590, y: 165, label: 'Verified & Active', sub: 'Lien to AICTE', full: 'Verified & Active', icon: <BadgeCheck size={15} /> },
  monitor: { x: 760, y: 165, label: 'Maturity Monitor', sub: 'T-90/60/30 alerts', full: 'Maturity Monitor', icon: <Bell size={15} /> },
  decide: { x: 935, y: 165, label: 'Renew or', sub: 'Release?', full: 'Renew or Release?', icon: <RefreshCw size={15} />, diamond: true },
  renew: { x: 935, y: 46, label: 'Renewal FDR', sub: 'Replacement', full: 'Renewal FDR', icon: <RefreshCw size={15} /> },
  request: { x: 935, y: 286, label: 'Release Request', sub: 'by Institution', full: 'Release Request', icon: <Send size={15} /> },
  scrutiny: { x: 760, y: 286, label: 'Scrutiny & NOC', sub: 'Regulation Bureau', full: 'Scrutiny & NOC', icon: <FileCheck2 size={15} /> },
  authority: { x: 590, y: 286, label: 'Competent', sub: 'Authority Approval', full: 'Competent Authority Approval', icon: <Gavel size={15} /> },
  released: { x: 420, y: 286, label: 'Released', sub: 'Lien removed', full: 'Released', icon: <Unlock size={15} /> },
};
const ORDER: NodeId[] = ['submit', 'docs', 'bank', 'disc', 'active', 'monitor', 'decide', 'renew', 'request', 'scrutiny', 'authority', 'released'];

const W = 156, H = 54, D = 50;

type E = { from: NodeId; to: NodeId; d: string; label?: string; lx?: number; ly?: number };
const r = (id: NodeId) => NODES[id].x + (NODES[id].diamond ? D : W / 2);
const l = (id: NodeId) => NODES[id].x - (NODES[id].diamond ? D : W / 2);
const t = (id: NodeId) => NODES[id].y - (NODES[id].diamond ? D : H / 2);
const b = (id: NodeId) => NODES[id].y + (NODES[id].diamond ? D : H / 2);
const h = (a: NodeId, z: NodeId) => `M${r(a)},${NODES[a].y} L${l(z) - 4},${NODES[z].y}`;
const hl = (a: NodeId, z: NodeId) => `M${l(a)},${NODES[a].y} L${r(z) + 4},${NODES[z].y}`;

const EDGES: E[] = [
  { from: 'submit', to: 'docs', d: h('submit', 'docs') },
  { from: 'docs', to: 'bank', d: h('docs', 'bank') },
  { from: 'bank', to: 'active', d: h('bank', 'active'), label: 'Match', lx: 492, ly: 156 },
  { from: 'bank', to: 'disc', d: `M420,${t('bank')} L420,${b('disc') + 4}`, label: 'Mismatch', lx: 454, ly: 96 },
  { from: 'disc', to: 'submit', d: `M${l('disc')},46 L85,46 L85,${t('submit') - 4}`, label: 'Clarify & resubmit', lx: 222, ly: 38 },
  { from: 'active', to: 'monitor', d: h('active', 'monitor') },
  { from: 'monitor', to: 'decide', d: h('monitor', 'decide') },
  { from: 'decide', to: 'renew', d: `M935,${t('decide')} L935,${b('renew') + 4}`, label: 'Renew', lx: 962, ly: 96 },
  { from: 'renew', to: 'active', d: `M${l('renew')},46 L590,46 L590,${t('active') - 4}`, label: 'Re-verify', lx: 720, ly: 38 },
  { from: 'decide', to: 'request', d: `M935,${b('decide')} L935,${t('request') - 4}`, label: 'Release', lx: 964, ly: 236 },
  { from: 'request', to: 'scrutiny', d: hl('request', 'scrutiny') },
  { from: 'scrutiny', to: 'authority', d: hl('scrutiny', 'authority') },
  { from: 'authority', to: 'released', d: hl('authority', 'released') },
];

const STATE_WORD: Record<NodeState, string> = { done: 'Done', current: 'Current', todo: 'Not reached', alert: 'Needs attention' };

/**
 * The FDR lifecycle. With `state` it shows one instrument (done / current / not reached / needs attention, each named
 * in text as well as colour); with `counts` it shows how many instruments sit at each stage.
 * First view: nodes appear in order, then the connectors draw in. The current stage glows softly and stays still.
 */
export function LifecycleFlow({ state = {}, counts, height, id }: { state?: Partial<Record<NodeId, NodeState>>; counts?: Partial<Record<NodeId, string | number>>; height?: number; id: string }) {
  const tr = useT();
  const st = (n: NodeId): NodeState => state[n] ?? (counts ? 'current' : 'todo');
  const edgeOn = (e: E) => (counts ? true : st(e.from) === 'done' && st(e.to) !== 'todo');
  const box = useRef<HTMLDivElement>(null);
  const inView = useInView(box, { once: true, amount: 0.25 });
  const [reveal] = useState(() => !prefersReducedMotion() && firstTime(`flow:${id}`));
  const show = !reveal || inView;
  const nodeDelay = (i: number) => i * STAGGER;
  const edgeStart = ORDER.length * STAGGER;
  const current = ORDER.filter((n) => st(n) === 'current' || st(n) === 'alert');

  const label = counts
    ? `FDR lifecycle pipeline: ${ORDER.filter((n) => counts[n] !== undefined).map((n) => `${NODES[n].full} ${counts[n]}`).join(', ')}.`
    : `FDR lifecycle for this instrument. ${current.length ? `Now at: ${current.map((n) => `${NODES[n].full}${st(n) === 'alert' ? ' (needs attention)' : ''}`).join(', ')}.` : 'No current stage.'} Done: ${ORDER.filter((n) => st(n) === 'done').map((n) => NODES[n].full).join(', ') || 'none'}.`;

  return (
    <ChartFrame label={label} table={{
      caption: counts ? 'Instruments at each lifecycle stage' : 'Lifecycle stages for this instrument',
      columns: counts ? ['Stage', 'Count'] : ['Stage', 'Status'],
      rows: ORDER.filter((n) => !counts || counts[n] !== undefined).map((n) => [NODES[n].full, counts ? (counts[n] as string | number) : tr(STATE_WORD[st(n)])]),
    }}>
      <div ref={box} className="flow-scroll" tabIndex={0} role="region" aria-label={tr('Lifecycle')}>
        <svg viewBox="0 0 1036 330" className="flow" style={{ height: height ?? 'auto' }} aria-hidden>
          <defs>
            <marker id={`arr-${id}`} viewBox="0 0 10 10" refX="8" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" className="fa-on" /></marker>
            <marker id={`arrg-${id}`} viewBox="0 0 10 10" refX="8" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" className="fa-off" /></marker>
            <filter id={`glow-${id}`} x="-30%" y="-40%" width="160%" height="180%"><feGaussianBlur stdDeviation="6" /></filter>
          </defs>
          {EDGES.map((e, i) => {
            const on = edgeOn(e);
            return (
              <g key={i}>
                <motion.path d={e.d} fill="none" className={on ? 'fe-on' : 'fe-off'} strokeWidth={on ? 2 : 1.6} strokeDasharray={on ? undefined : '4 5'}
                  markerEnd={`url(#${on ? 'arr' : 'arrg'}-${id})`}
                  initial={reveal ? { pathLength: 0, opacity: 0 } : false}
                  animate={show ? { pathLength: 1, opacity: 1 } : { pathLength: 0, opacity: 0 }}
                  transition={{ duration: DUR.base, delay: edgeStart + i * STAGGER * 0.75, ease: EASE.out }} />
                {e.label && (
                  <motion.text x={e.lx} y={e.ly} fontSize={12} className={on ? 'fl-on' : 'fl-off'} fontWeight={600} textAnchor="middle"
                    initial={reveal ? { opacity: 0 } : false} animate={{ opacity: show ? 1 : 0 }} transition={{ duration: DUR.fast, delay: edgeStart + i * STAGGER * 0.75 }}>
                    {tr(e.label)}
                  </motion.text>
                )}
              </g>
            );
          })}
          {ORDER.map((nid, i) => {
            const n = NODES[nid];
            const s = st(nid);
            const count = counts?.[nid];
            const glow = !counts && (s === 'current' || s === 'alert');
            return (
              <motion.g key={nid} className={`fn fn-${s}`}
                initial={reveal ? { opacity: 0, scale: 0.92 } : false} animate={show ? { opacity: 1, scale: 1 } : { opacity: 0, scale: 0.92 }}
                transition={{ delay: nodeDelay(i), duration: DUR.base, ease: EASE.out }}
                style={{ originX: `${n.x}px`, originY: `${n.y}px`, transformBox: 'view-box' }}>
                {glow && (n.diamond
                  ? <polygon className="fn-glow" points={`${n.x},${n.y - D - 4} ${n.x + D + 4},${n.y} ${n.x},${n.y + D + 4} ${n.x - D - 4},${n.y}`} filter={`url(#glow-${id})`} />
                  : <rect className="fn-glow" x={n.x - W / 2 - 4} y={n.y - H / 2 - 4} width={W + 8} height={H + 8} rx={14} filter={`url(#glow-${id})`} />)}
                {n.diamond
                  ? <polygon className="fn-box" points={`${n.x},${n.y - D} ${n.x + D},${n.y} ${n.x},${n.y + D} ${n.x - D},${n.y}`} strokeWidth={glow ? 2.4 : 1.6} />
                  : <rect className="fn-box" x={n.x - W / 2} y={n.y - H / 2} width={W} height={H} rx={10} strokeWidth={glow ? 2.4 : 1.6} />}
                {n.diamond ? (
                  <>
                    <circle className="fn-ico-bg" cx={n.x} cy={n.y - 20} r={11} />
                    <g className="fn-ico" transform={`translate(${n.x - 7.5},${n.y - 27.5})`}>{n.icon}</g>
                    <text className="fn-label" x={n.x} y={n.y + 4} fontSize={12} fontWeight={700} textAnchor="middle">{tr(n.label)}</text>
                    <text className="fn-sub" x={n.x} y={n.y + 18} fontSize={12} textAnchor="middle">{tr(n.sub)}</text>
                  </>
                ) : (
                  <>
                    <circle className="fn-ico-bg" cx={n.x - W / 2 + 22} cy={n.y} r={13} />
                    <g className="fn-ico" transform={`translate(${n.x - W / 2 + 14.5},${n.y - 7.5})`}>{n.icon}</g>
                    <text className="fn-label" x={n.x - W / 2 + 40} y={n.y - 3} fontSize={12} fontWeight={700}>{tr(n.label)}</text>
                    <text className="fn-sub" x={n.x - W / 2 + 40} y={n.y + 13} fontSize={12}>{tr(n.sub)}</text>
                  </>
                )}
                {count !== undefined && (
                  <g>
                    <rect className={s === 'alert' ? 'fn-count fn-count-alert' : 'fn-count'} x={n.x + (n.diamond ? 20 : W / 2 - 28)} y={n.y - (n.diamond ? D : H / 2) - 10} width={40} height={20} rx={10} />
                    <text className="fn-count-t num" x={n.x + (n.diamond ? 40 : W / 2 - 8)} y={n.y - (n.diamond ? D : H / 2) + 4} fontSize={12} fontWeight={700} textAnchor="middle">{count}</text>
                  </g>
                )}
                {!counts && s !== 'todo' && (
                  <g>
                    <rect className={`fn-tag fn-tag-${s}`} x={n.x - (n.diamond ? 36 : W / 2)} y={n.y + (n.diamond ? D + 4 : H / 2 + 4)} width={s === 'alert' ? 108 : 72} height={18} rx={9} />
                    <text className={`fn-tag-t fn-tag-t-${s}`} x={n.x - (n.diamond ? 36 : W / 2) + (s === 'alert' ? 54 : 36)} y={n.y + (n.diamond ? D + 17 : H / 2 + 17)} fontSize={12} fontWeight={600} textAnchor="middle">
                      {tr(STATE_WORD[s])}
                    </text>
                  </g>
                )}
              </motion.g>
            );
          })}
        </svg>
      </div>
    </ChartFrame>
  );
}

/** Horizontal stepper for the release workflow. The current step is marked in text and holds still. */
export function ReleaseStepper({ stage }: { stage: string }) {
  const tr = useT();
  const steps = [
    { k: 'submitted', label: 'Request Raised', icon: <Send size={16} /> },
    { k: 'scrutiny', label: 'Scrutiny & NOC', icon: <FileCheck2 size={16} /> },
    { k: 'authority', label: 'Competent Authority', icon: <Gavel size={16} /> },
    { k: 'approved', label: 'Approved', icon: <BadgeCheck size={16} /> },
    { k: 'released', label: 'Released', icon: <HandCoins size={16} /> },
  ];
  const rejected = stage === 'rejected';
  const idx = rejected ? -1 : steps.findIndex((s) => s.k === stage);
  return (
    <ol className="stepper">
      {steps.map((s, i) => {
        const done = i < idx || stage === 'released';
        const cur = i === idx && stage !== 'released';
        const cls = done ? 'done' : cur ? 'cur' : rejected && i === 0 ? 'bad' : 'todo';
        return (
          <li key={s.k} className={`step step-${cls}`} aria-current={cur ? 'step' : undefined}>
            {i > 0 && <span className="step-line" aria-hidden><span style={{ transform: `scaleX(${done || cur ? 1 : 0})` }} /></span>}
            <span className="step-dot" aria-hidden>{done ? <Check size={16} /> : s.icon}</span>
            <span className="step-label">{tr(s.label)}</span>
            <span className="sr-only">{done ? ', done' : cur ? ', current step' : rejected && i === 0 ? ', rejected' : ', not reached'}</span>
          </li>
        );
      })}
    </ol>
  );
}
