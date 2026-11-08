import { CheckCircle2, KeyRound, Landmark, ShieldAlert, ShieldQuestion } from 'lucide-react';
import { useState } from 'react';
import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import type { BankMessage } from '../../api/types';
import { tipStyle } from '../../components/Charts';
import { Pager, TableWrap } from '../../components/Tables';
import { ErrorBox, Kpi, Loading, PageHead, Panel, Planned, SimBadge, Stagger, StatusPill, Tabs } from '../../components/ui';
import { fmtDateTime, lakhP } from '../../lib/format';
import { useRole } from '../../lib/hooks';
import { useApi } from '../../store/Store';

interface Recon {
  certification: { bank_confirmed_pool: number | null; expected_pool_from_ledger: number; aggregate_matches: boolean; unallocated_credits: number;
    legacy_declared_total: number; per_institution: Record<string, { certifiable: number; declared_not_certifiable: number; uncertain: number; held: number; unverified_source: number }>; statement: string };
  per_bank: { bank: string; bank_name: string; live: number; confirmed: number; mismatch: number; awaiting: number }[];
  signers: { key_id: string; bank: string; valid_from: string; ended_at: string | null; compromised_from: string | null; note: string | null }[];
}

export default function Reconciliation() {
  const { base } = useRole();
  const d = useApi<Recon>('/reconciliation');
  const [status, setStatus] = useState('');
  const [page, setPage] = useState(1);
  const msgs = useApi<{ total: number; items: BankMessage[] }>(`/bank/messages?page=${page}&size=12${status ? `&status=${status}` : ''}`, [page, status]);
  if (!d.data) return d.error ? <ErrorBox text={d.error} /> : <Loading rows={10} />;
  const { certification: c, per_bank, signers } = d.data;
  const live = per_bank.reduce((s, b) => s + b.live, 0);
  const conf = per_bank.reduce((s, b) => s + b.confirmed, 0);
  const mism = per_bank.reduce((s, b) => s + b.mismatch, 0);
  const rows = per_bank.map((b) => ({ ...b, short: b.bank }));

  return (
    <Stagger>
      <PageHead title="Bank Reconciliation" sub="Every figure is computed from signed bank messages in the database" crumbs={[{ label: 'Dashboard', to: base }, { label: 'Bank Reconciliation' }]}
        actions={<SimBadge title="All 12 banks are simulated in this build" />} />
      <div className="planned-strip"><Planned label="Real bank links (SFMS / host-to-host)" note="every bank message on this page comes from the bank simulator" /></div>
      <div className="kpis k4">
        <Kpi tone="blue" icon={<Landmark size={34} />} label="Live FDRs" value={live.toLocaleString('en-IN')} sub="across 12 banks" />
        <Kpi tone="green" icon={<CheckCircle2 size={34} />} label="Bank confirmed" value={conf.toLocaleString('en-IN')} sub={`${live ? ((conf / live) * 100).toFixed(1) : '0.0'}% of live FDRs`} />
        <Kpi tone="red" icon={<ShieldAlert size={34} />} label="FDRs with discrepancies" value={String(mism)} sub="bank record differs" />
        <Kpi tone="orange" icon={<ShieldQuestion size={34} />} label="Awaiting bank" value={(live - conf).toLocaleString('en-IN')} sub="institution-declared only" />
      </div>

      <div className="row g-2">
        <Panel title={<>Pool certification <SimBadge /></>} sub={c.statement}>
          <dl className="kv" style={{ gridTemplateColumns: '220px 1fr' }}>
            <dt>Bank-confirmed pool balance</dt><dd>{c.bank_confirmed_pool === null ? 'no valid confirmation' : `₹ ${lakhP(c.bank_confirmed_pool)} lakh`}</dd>
            <dt>Expected pool from ledger</dt><dd>₹ {lakhP(c.expected_pool_from_ledger)} lakh</dd>
            <dt>Aggregate certifiable</dt><dd>{c.aggregate_matches ? <StatusPill status="active" label="Matches" /> : <StatusPill status="discrepancy" label="Does not match" />}</dd>
            <dt>Unallocated credits</dt><dd>₹ {lakhP(c.unallocated_credits)} lakh (refundable, visible)</dd>
          </dl>
          <h4 style={{ margin: '16px 0 8px', fontSize: 14 }}>Per institution (online deposits)</h4>
          <TableWrap label="Per-institution certification" simulated>
            <table className="tbl cardable">
              <caption className="sr-only">Per-institution certification</caption>
              <thead><tr><th scope="col">Institution</th><th scope="col">Certifiable</th><th scope="col">Declared, not certifiable</th><th scope="col">Uncertain / held</th></tr></thead>
              <tbody>
                {Object.entries(c.per_institution).map(([k, v]) => (
                  <tr key={k}><td>{k}</td><td>₹ {lakhP(v.certifiable)} L</td><td>₹ {lakhP(v.declared_not_certifiable)} L</td><td>₹ {lakhP(v.uncertain + v.held + v.unverified_source)} L</td></tr>
                ))}
              </tbody>
            </table>
          </TableWrap>
        </Panel>
        <Panel title="Confirmation status by bank">
          <ResponsiveContainer width="100%" height={300}>
            <BarChart data={rows} margin={{ top: 10, right: 8, left: -10, bottom: 0 }}>
              <CartesianGrid vertical={false} stroke="var(--c-fg-e8edf4)" />
              <XAxis dataKey="short" fontSize={12} interval={0} tickLine={false} />
              <YAxis fontSize={12} tickLine={false} axisLine={false} />
              <Tooltip contentStyle={tipStyle} cursor={{ fill: 'rgba(11,94,215,.05)' }} />
              <Legend wrapperStyle={{ fontSize: 13 }} />
              <Bar dataKey="confirmed" name="Confirmed" stackId="a" fill="var(--green)" />
              <Bar dataKey="awaiting" name="Awaiting" stackId="a" fill="var(--c-fg-d97706)" />
            </BarChart>
          </ResponsiveContainer>
        </Panel>
      </div>

      <Panel title={<>Bank Authority Registry <SimBadge /></>} sub="Validity is judged at receipt time. Ended keys keep earlier evidence valid; a compromised key invalidates everything received from its compromise date.">
        <TableWrap label="Registered bank signing keys" simulated>
          <table className="tbl cardable">
            <caption className="sr-only">Registered bank signing keys</caption>
            <thead><tr><th scope="col">Key</th><th scope="col">Bank</th><th scope="col">Valid from</th><th scope="col">Ended</th><th scope="col">Compromised from</th><th scope="col">Status</th></tr></thead>
            <tbody>
              {signers.map((s) => (
                <tr key={s.key_id}>
                  <td><KeyRound size={13} aria-hidden /> {s.key_id}</td><td>{s.bank}</td><td>{s.valid_from}</td><td>{s.ended_at ?? '—'}</td><td>{s.compromised_from ?? '—'}</td>
                  <td>{s.compromised_from ? <StatusPill status="discrepancy" label="Compromised" /> : s.ended_at ? <StatusPill status="closed" label="Ended" /> : <StatusPill status="active" label="Active" />}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </TableWrap>
      </Panel>

      <Panel title={<>Bank message log <SimBadge /></>} sub="Every message received, with its signature and record check outcome">
        <Tabs id="bm" value={status} onChange={(k) => { setStatus(k); setPage(1); }} tabs={[{ key: '', label: 'All' }, { key: 'ACCEPTED', label: 'Accepted' }, { key: 'REJECTED', label: 'Rejected' }]} />
        {msgs.error ? <ErrorBox text={msgs.error} /> : !msgs.data ? <Loading /> : (
          <>
            <TableWrap label="Bank messages" simulated>
              <table className="tbl cardable">
                <caption className="sr-only">Bank messages</caption>
                <thead><tr><th scope="col">Received</th><th scope="col">Kind</th><th scope="col">Bank / key</th><th scope="col">Reference</th><th scope="col">Outcome</th></tr></thead>
                <tbody>
                  {msgs.data.items.map((m) => (
                    <tr key={m.id}>
                      <td>{fmtDateTime(m.received_at)}</td><td>{m.kind.replace(/_/g, ' ')}{m.scenario_id && ` (${m.scenario_id})`}</td><td>{m.bank} · {m.key_id}</td><td>{m.ref ?? m.evidence_id}</td>
                      <td>{m.status === 'ACCEPTED' ? <StatusPill status="active" label="Accepted" /> : m.status === 'DUPLICATE' ? <StatusPill status="closed" label="Duplicate" /> : <span title={m.reason ?? ''}><StatusPill status="discrepancy" label={`Rejected: ${m.reason}`} /></span>}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </TableWrap>
            <Pager page={page} size={12} total={msgs.data.total} onPage={setPage} />
          </>
        )}
      </Panel>
    </Stagger>
  );
}
