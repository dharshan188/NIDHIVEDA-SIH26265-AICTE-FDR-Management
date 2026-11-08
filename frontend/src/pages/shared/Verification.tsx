import { AlertTriangle, ArrowRight, Check, Clock3, Landmark, Loader2, Search, ShieldCheck, X } from 'lucide-react';
import { useEffect, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { post } from '../../api/client';
import type { Fdr } from '../../api/types';
import { Empty, ErrorBox, Loading, PageHead, Panel, SimBadge, Stagger, StatusPill, Tabs } from '../../components/ui';
import { fmtDate, inrP } from '../../lib/format';
import { useRole } from '../../lib/hooks';
import { useApi, useStore } from '../../store/Store';

const SLA_DAYS = 7;
interface Row { field: string; label: string; declared: string | number; bank_confirmed: string | number | null; confidence: string }
interface Detail { fdr: Fdr; comparison: { rows: Row[]; confirmation: unknown; problems: string[] } }

export default function Verification({ readOnly }: { readOnly?: boolean }) {
  const { base } = useRole();
  const { run } = useStore();
  const [params] = useSearchParams();
  const [tab, setTab] = useState<'pending' | 'discrepancy'>(readOnly || params.get('tab') === 'discrepancy' ? 'discrepancy' : 'pending');
  const [q, setQ] = useState('');
  const list = useApi<{ total: number; items: Fdr[] }>(`/fdrs?bucket=${tab}&sort=maturity&size=200${q ? `&q=${encodeURIComponent(q)}` : ''}`, [tab, q]);
  const pend = useApi<{ total: number }>('/fdrs?bucket=pending&size=1');
  const disc = useApi<{ total: number }>('/fdrs?bucket=discrepancy&size=1');
  const queue = [...(list.data?.items ?? [])].sort((a, b) => a.submitted_on.localeCompare(b.submitted_on));
  const [selId, setSelId] = useState<string | null>(null);
  useEffect(() => setSelId(null), [tab]);
  const current = selId ?? queue[0]?.id ?? null;
  const d = useApi<Detail>(current ? `/fdrs/${current}` : null, [current]);
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState('');
  const age = (iso: string) => Math.floor((Date.now() - new Date(iso).getTime()) / 864e5);
  const overdue = queue.filter((f) => tab === 'pending' && age(f.submitted_on) > SLA_DAYS).length;
  const title = readOnly ? 'Discrepancies' : 'Verification & Scrutiny';

  return (
    <Stagger>
      <PageHead title={title} sub={readOnly ? 'FDRs where submitted details differ from bank records or prescribed conditions' : `${pend.data?.total ?? '…'} awaiting scrutiny · ${overdue} beyond the ${SLA_DAYS}-day target`}
        crumbs={[{ label: 'Dashboard', to: base }, { label: title }]} />
      <div className="row" style={{ gridTemplateColumns: 'minmax(300px, 400px) minmax(0, 1fr)' }}>
        <Panel>
          {!readOnly && <Tabs id="verif" value={tab} onChange={setTab} tabs={[{ key: 'pending', label: `Pending (${pend.data?.total ?? '…'})` }, { key: 'discrepancy', label: `Discrepancy (${disc.data?.total ?? '…'})` }]} />}
          <label className="field" style={{ marginBottom: 10 }}><Search size={17} aria-hidden /><span className="sr-only">Filter queue</span><input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Filter queue" /></label>
          {list.error ? <ErrorBox text={list.error} /> : !list.data ? <Loading /> : (
            <ul style={{ maxHeight: 640, overflow: 'auto', display: 'flex', flexDirection: 'column', gap: 6, padding: 0, margin: 0, listStyle: 'none' }} aria-label="Queue">
              {queue.map((f) => {
                const on = current === f.id;
                const a = age(f.submitted_on);
                return (
                  <li key={f.id}>
                    <button onClick={() => setSelId(f.id)} className="card" aria-current={on}
                      style={{ width: '100%', textAlign: 'left', padding: '10px 12px', borderColor: on ? 'var(--c-bd-3d7ee0)' : undefined, background: on ? 'var(--c-bg-f1f6fe)' : 'var(--card)', boxShadow: on ? '0 0 0 1px var(--c-fg-3d7ee0) inset' : 'none' }}>
                      <span style={{ display: 'flex', justifyContent: 'space-between', gap: 8 }}>
                        <b style={{ fontSize: 13.5, color: 'var(--ink)' }}>{f.institution_name}</b>
                        <span style={{ fontSize: 12.5, color: a > SLA_DAYS && tab === 'pending' ? 'var(--red-ink)' : 'var(--muted)', display: 'flex', gap: 4, alignItems: 'center', whiteSpace: 'nowrap' }}><Clock3 size={12} aria-hidden /> {a}d</span>
                      </span>
                      <span style={{ display: 'block', fontSize: 13, color: 'var(--muted)', marginTop: 3 }}>{f.id} · {f.bank_name} · {inrP(f.amount_paise)}</span>
                      {f.discrepancy_reason && <span style={{ display: 'block', fontSize: 12.5, color: 'var(--red-ink)', marginTop: 4 }}>{f.discrepancy_reason}</span>}
                    </button>
                  </li>
                );
              })}
              {queue.length === 0 && <Empty text="The queue is clear." />}
            </ul>
          )}
        </Panel>

        {!current ? <div className="card"><Empty text="Select an item from the queue" /></div> : !d.data ? (d.error ? <ErrorBox text={d.error} /> : <div className="card panel"><Loading rows={8} /></div>) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
            <section className="card panel">
              <div className="panel-head">
                <div><h3>{d.data.fdr.id}</h3><p>{d.data.fdr.institution_name ?? ''} · submitted {fmtDate(d.data.fdr.submitted_on)}</p></div>
                <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                  <StatusPill status={d.data.fdr.status} />
                  <Link to={`${base}/fdr/${d.data.fdr.id}`} className="view-all">Full record <ArrowRight size={16} aria-hidden /></Link>
                </div>
              </div>
              <div className="panel-head" style={{ marginBottom: 6 }}><h3 style={{ fontSize: 15.5 }}>Checks against the issuing bank <SimBadge /></h3></div>
              <ul style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8, padding: 0, margin: 0, listStyle: 'none' }}>
                {d.data.comparison.rows.map((r) => {
                  const ok = r.confidence === 'BANK_CONFIRMED';
                  const bad = r.confidence === 'MISMATCH' || r.confidence === 'UNVERIFIED_SOURCE';
                  return (
                    <li key={r.field} style={{ display: 'flex', gap: 10, alignItems: 'center', padding: '10px 12px', borderRadius: 8, background: ok ? 'var(--c-bg-f1faf5)' : bad ? 'var(--c-bg-fdf1f1)' : 'var(--c-fg-f5f7fb)', fontSize: 13.5 }}>
                      <span aria-hidden style={{ width: 22, height: 22, borderRadius: '50%', display: 'grid', placeItems: 'center', flex: 'none', color: 'var(--on-solid)', background: ok ? 'var(--green)' : bad ? 'var(--red)' : 'var(--c-fg-6b7690)' }}>
                        {ok ? <Check size={13} strokeWidth={3} /> : bad ? <X size={13} strokeWidth={3} /> : <Clock3 size={12} />}
                      </span>
                      <span>{r.label}: <b>{ok ? 'matches bank' : bad ? r.confidence === 'MISMATCH' ? 'differs from bank' : 'unverified source' : 'awaiting bank'}</b></span>
                    </li>
                  );
                })}
              </ul>
              {!readOnly && (
                <div style={{ display: 'flex', gap: 10, marginTop: 14, alignItems: 'center', flexWrap: 'wrap' }}>
                  <button className="btn btn-ghost" disabled={busy} onClick={async () => { setBusy(true); await run(() => post(`/fdrs/${current}/bank-confirmation`), 'Issuing bank (simulated) replied'); setBusy(false); }}>
                    {busy ? <Loader2 className="spin" size={17} aria-hidden /> : <Landmark size={17} aria-hidden />} {busy ? 'Asking the bank…' : 'Request bank confirmation'}
                  </button>
                  <span className="hint" style={{ margin: 0 }}>Just-in-time check through the FDR confirmation channel</span>
                </div>
              )}
            </section>
            {!readOnly && (
              <section className="card panel">
                <div className="panel-head"><h3>Scrutiny decision</h3></div>
                <label className="sr-only" htmlFor="snote">Scrutiny observations</label>
                <textarea id="snote" className="inp" value={note} onChange={(e) => setNote(e.target.value)} placeholder="Scrutiny observations (recorded in the audit trail)" />
                <div style={{ display: 'flex', gap: 10, marginTop: 12, justifyContent: 'flex-end' }}>
                  <button className="btn btn-red" disabled={note.trim().length < 3} onClick={async () => { if (await run(() => post(`/fdrs/${current}/discrepancy`, { reason: note }), 'Discrepancy recorded') !== undefined) setNote(''); }}>
                    <AlertTriangle size={17} aria-hidden /> Flag discrepancy
                  </button>
                  <button className="btn btn-green" disabled={!d.data.comparison.confirmation} onClick={async () => { if (await run(() => post(`/fdrs/${current}/verify`, { note: note || null }), 'Verified') !== undefined) setNote(''); }}>
                    <ShieldCheck size={17} aria-hidden /> Mark verified
                  </button>
                </div>
                {!d.data.comparison.confirmation && <p className="hint" style={{ textAlign: 'right' }}>Verification needs a valid confirmation from the issuing bank.</p>}
              </section>
            )}
          </div>
        )}
      </div>
    </Stagger>
  );
}
