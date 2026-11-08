import { motion, useScroll, useSpring } from 'framer-motion';
import { Download, Loader2, Search, ShieldCheck, ShieldX } from 'lucide-react';
import { useEffect, useRef, useState } from 'react';
import { post } from '../../api/client';
import { Pager, TableWrap } from '../../components/Tables';
import { ErrorBox, Loading, PageHead, Panel, Planned, Stagger, Tabs } from '../../components/ui';
import { prefersReducedMotion } from '../../lib/motion';
import { fmtDateTime } from '../../lib/format';
import { useRole } from '../../lib/hooks';
import { useApi, useStore } from '../../store/Store';

interface Ev { seq: number; at: string; type: string; actor: string; data: Record<string, unknown>; prev: string; hash: string }
interface ChainCheck { events: number; valid: boolean; head: string; problems: { seq: number; problem: string }[]; first_bad_seq: number | null }
interface Verify { ok: boolean; kernel_chain: ChainCheck; portal_chain: ChainCheck; checkpoint: { valid: boolean | null; detail: string; path: string }; replay_matches_live_state: boolean | null; limits: string }

export default function AuditTrail() {
  const { base } = useRole();
  const { toast } = useStore();
  const [chain, setChain] = useState<'kernel' | 'portal'>('kernel');
  const [q, setQ] = useState('');
  const [dq, setDq] = useState('');
  const [page, setPage] = useState(1);
  const [check, setCheck] = useState<Verify | null>(null);
  const [busy, setBusy] = useState(false);
  // scroll-linked progress through the event table (sticky header inside a capped-height scroller)
  const scroller = useRef<HTMLDivElement>(null);
  const { scrollYProgress } = useScroll({ container: scroller });
  const progress = useSpring(scrollYProgress, { stiffness: 300, damping: 40, restDelta: 0.001 });
  useEffect(() => {
    const t = setTimeout(() => setDq(q), 300);
    return () => clearTimeout(t);
  }, [q]);
  useEffect(() => setPage(1), [chain, dq]);
  const d = useApi<{ total: number; items: Ev[] }>(`/audit-trail?chain=${chain}&page=${page}&size=50${dq ? `&q=${encodeURIComponent(dq)}` : ''}`, [chain, page, dq]);

  const verify = async () => {
    setBusy(true);
    try {
      setCheck(await post<Verify>('/audit-trail/verify'));
    } catch (e) {
      toast(String(e), 'error');
    } finally {
      setBusy(false);
    }
  };

  const summary = (name: string, c: ChainCheck) => (
    <li>{c.valid ? <ShieldCheck size={16} color="var(--green-ink)" aria-hidden /> : <ShieldX size={16} color="var(--red-ink)" aria-hidden />} <b>{name}</b>: {c.events.toLocaleString('en-IN')} events,{' '}
      {c.valid ? <>intact (head {c.head.slice(0, 12)}…)</> : <>broken at #{c.first_bad_seq}: {c.problems[0]?.problem}</>}</li>
  );

  return (
    <Stagger>
      <PageHead title="Audit Trail" sub="Two SHA-256 hash chains: the ledger (every financial control) and the portal (sign-ins, submissions, policy changes)" crumbs={[{ label: 'Dashboard', to: base }, { label: 'Audit Trail' }]}
        actions={<>
          <a className="btn btn-ghost" href="/api/reports/export.csv?kind=audit"><Download size={17} aria-hidden /> Export</a>
          <button className="btn btn-primary" onClick={verify} disabled={busy}>{busy ? <Loader2 size={17} className="spin" aria-hidden /> : <ShieldCheck size={17} aria-hidden />} Verify ledger integrity</button>
        </>} />
      {check && (
        <section className={`card verify-box ${check.ok ? 'ok' : 'bad'}`} role="status" aria-live="polite">
          <h3>{check.ok ? 'Ledger intact: every hash recomputed and matched' : 'Integrity problem detected'}</h3>
          <ul>
            {summary('Ledger chain', check.kernel_chain)}
            {summary('Portal chain', check.portal_chain)}
            <li>{check.checkpoint.valid ? <ShieldCheck size={16} color="var(--green-ink)" aria-hidden /> : <ShieldX size={16} color="var(--red-ink)" aria-hidden />} <b>Off-host checkpoint</b>: {check.checkpoint.detail}</li>
            <li>{check.replay_matches_live_state ? <ShieldCheck size={16} color="var(--green-ink)" aria-hidden /> : <ShieldX size={16} color="var(--red-ink)" aria-hidden />} <b>Replay</b>: {check.replay_matches_live_state === null ? 'not run (chain broken)' : check.replay_matches_live_state ? 'rebuilding state from the stored events gives the live state' : 'replayed state differs from live state'}</li>
          </ul>
          <p className="hint">{check.limits}</p>
        </section>
      )}
      <div className="planned-strip">
        <Planned label="RFC 3161 time-stamping of the chain head" note="the checkpoint here is a local file" />
      </div>
      <Panel>
        <Tabs id="chain" value={chain} onChange={setChain} tabs={[{ key: 'kernel', label: 'Ledger events' }, { key: 'portal', label: 'Portal events' }]} />
        <label className="field" style={{ marginBottom: 12 }}><Search size={18} aria-hidden /><span className="sr-only">Search events</span><input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search by FDR, institution, event type or actor" /></label>
        {d.error ? <ErrorBox text={d.error} /> : !d.data ? <Loading layout="table" rows={12} /> : (
          <>
            <div className="scroll-progress" aria-hidden><motion.span style={{ scaleX: prefersReducedMotion() ? scrollYProgress : progress }} /></div>
            <TableWrap label="Audit events" tall scrollRef={scroller}>
              <table className="tbl cardable">
                <caption className="sr-only">Audit events</caption>
                <thead><tr><th scope="col">#</th><th scope="col">Time</th><th scope="col">Actor</th><th scope="col">Event</th><th scope="col">Detail</th><th scope="col">Hash (prev → this)</th></tr></thead>
                <tbody>
                  {d.data.items.map((e) => (
                    <tr key={e.seq}>
                      <td>{e.seq}</td><td>{fmtDateTime(e.at)}</td><td>{e.actor}</td><td style={{ fontWeight: 500 }}>{e.type.replace(/_/g, ' ')}</td>
                      <td className="ell" style={{ maxWidth: 340 }} title={JSON.stringify(e.data)}>{brief(e.data)}</td>
                      <td><span className="hash" title={e.prev}>{e.prev.slice(0, 8)}</span> → <span className="hash" title={e.hash}>{e.hash.slice(0, 8)}</span></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </TableWrap>
            <Pager page={page} size={50} total={d.data.total} onPage={setPage} />
          </>
        )}
      </Panel>
    </Stagger>
  );
}

function brief(d: Record<string, unknown>): string {
  const env = d.envelope as { kind?: string; bank?: string } | undefined;
  if (env) return `${env.kind} from ${env.bank} (${d.evidence_id})`;
  return Object.entries(d).filter(([, v]) => typeof v !== 'object').slice(0, 4).map(([k, v]) => `${k}: ${v}`).join(' · ');
}
