import { AlarmClock, BellRing, CalendarClock, CalendarX2, RefreshCw, Send } from 'lucide-react';
import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { post } from '../../api/client';
import type { Fdr } from '../../api/types';
import { DaysLeft, ErrorBox, Kpi, Loading, PageHead, Panel, Stagger, StatusPill, Tabs } from '../../components/ui';
import { fmtDate, inrP } from '../../lib/format';
import { TableWrap } from '../../components/Tables';
import { useRole } from '../../lib/hooks';
import { useApi, useStore } from '../../store/Store';

type W = 'all' | 'overdue' | '30' | '60' | '90';
const band = (d: number): W => (d < 0 ? 'overdue' : d <= 30 ? '30' : d <= 60 ? '60' : '90');

export default function Renewals() {
  const { role, base } = useRole();
  const { run } = useStore();
  const nav = useNavigate();
  const [win, setWin] = useState<W>('all');
  const [sent, setSent] = useState<Set<string>>(new Set());
  const d = useApi<{ items: Fdr[] }>('/fdrs?bucket=maturing&sort=maturity&size=200');
  if (!d.data) return d.error ? <ErrorBox text={d.error} /> : <Loading rows={8} />;
  const due = [...d.data.items].sort((a, b) => a.maturity_date.localeCompare(b.maturity_date));
  const cnt = (w: W) => due.filter((f) => band(f.days_left) === w).length;
  const rows = due.filter((f) => win === 'all' || band(f.days_left) === win);

  return (
    <Stagger>
      <PageHead title="Renewal & Maturity" sub="Maturity dates monitored from the server's current date" crumbs={[{ label: 'Dashboard', to: base }, { label: 'Renewal & Maturity' }]}
        actions={role === 'institution' ? <button className="btn btn-navy" onClick={() => nav(`${base}/upload`)}><RefreshCw size={17} aria-hidden /> Submit Renewal FDR</button> : undefined} />
      <div className="kpis k4">
        <Kpi tone="red" icon={<CalendarX2 size={34} />} label="Matured, not renewed" value={String(cnt('overdue'))} sub="follow-up needed" onClick={() => setWin('overdue')} />
        <Kpi tone="orange" icon={<AlarmClock size={34} />} label="Within 30 days" value={String(cnt('30'))} sub="urgent" onClick={() => setWin('30')} />
        <Kpi tone="purple" icon={<CalendarClock size={34} />} label="31 – 60 days" value={String(cnt('60'))} sub="second reminder" onClick={() => setWin('60')} />
        <Kpi tone="blue" icon={<BellRing size={34} />} label="61 – 90 days" value={String(cnt('90'))} sub="first reminder" onClick={() => setWin('90')} />
      </div>
      <Panel title="90-day maturity horizon" sub="Each marker is one FDR. Select a marker to open it.">
        <div style={{ position: 'relative', height: 120, margin: '10px 8px 6px' }}>
          <div style={{ position: 'absolute', left: 0, right: 0, top: 58, height: 8, borderRadius: 4, background: 'linear-gradient(90deg,var(--c-bg-fecaca),var(--c-bg-fde68a) 35%,var(--c-bg-ddd6fe) 66%,var(--c-fg-dbeafe))' }} aria-hidden />
          {[0, 30, 60, 90].map((x) => (
            <div key={x} aria-hidden style={{ position: 'absolute', left: `${(x / 90) * 100}%`, top: 74, transform: 'translateX(-50%)', fontSize: 12.5, color: 'var(--muted)', textAlign: 'center' }}>
              <div style={{ width: 1, height: 8, background: 'var(--c-bg-9aa6bd)', margin: '0 auto 4px' }} />{x === 0 ? 'Today' : `${x}d`}
            </div>
          ))}
          {due.map((f, i) => {
            const x = Math.max(0, f.days_left);
            return (
              <button key={f.id} aria-label={`${f.institution_name}, ${f.id}, ${f.days_left} days left`} title={`${f.institution_name} · ${f.id} · ${f.days_left} days`} onClick={() => nav(`${base}/fdr/${f.id}`)}
                style={{ position: 'absolute', left: `calc(${(x / 90) * 100}% - 6px)`, top: 6 + (i % 4) * 12, width: 12, height: 12, borderRadius: '50%', padding: 0,
                  background: x <= 30 ? 'var(--red)' : x <= 60 ? 'var(--c-fg-6a28d9)' : 'var(--primary)', border: '2px solid var(--c-bd-ffffff)', boxShadow: '0 1px 4px rgba(0,0,0,.25)' }} />
            );
          })}
        </div>
      </Panel>
      <Panel>
        <Tabs id="ren" value={win} onChange={setWin} tabs={[{ key: 'all', label: `All (${due.length})` }, { key: 'overdue', label: `Overdue (${cnt('overdue')})` }, { key: '30', label: `≤ 30 days (${cnt('30')})` }, { key: '60', label: `31–60 days (${cnt('60')})` }, { key: '90', label: `61–90 days (${cnt('90')})` }]} />
        <TableWrap label="FDRs maturing in the next 90 days">
          <table className="tbl cardable">
            <caption className="sr-only">FDRs maturing in the next 90 days</caption>
            <thead><tr><th scope="col" className="c">#</th>{role !== 'institution' && <th scope="col">Institution</th>}<th scope="col">FDR Reference</th><th scope="col">Bank</th><th scope="col">Amount</th><th scope="col">Maturity Date</th><th scope="col" className="c">Days Left</th><th scope="col">Renewal</th><th scope="col" className="c">Action</th></tr></thead>
            <tbody>
              {rows.map((f, i) => (
                <tr key={f.id} className="clickable" onClick={() => nav(`${base}/fdr/${f.id}`)}>
                  <td className="c">{i + 1}</td>
                  {role !== 'institution' && <td className="ell">{f.institution_name}</td>}
                  <td>{f.id}</td><td>{f.bank_name}</td><td className="num">{inrP(f.amount_paise)}</td><td>{fmtDate(f.maturity_date)}</td>
                  <td className="c"><DaysLeft days={f.days_left} /></td>
                  <td>{f.renewed_by ? <StatusPill status="active" label={`Renewed · ${f.renewed_by}`} /> : <StatusPill status="pending" label="Not submitted" />}</td>
                  <td className="c" onClick={(e) => e.stopPropagation()}>
                    {role === 'institution' ? (
                      <button className="btn btn-ghost btn-xs" onClick={() => nav(`${base}/upload?renewal=${f.id}`)}><RefreshCw size={13} aria-hidden /> Renew</button>
                    ) : role === 'aicte' && !f.renewed_by ? (
                      <button className="btn btn-ghost btn-xs" disabled={sent.has(f.id)} onClick={async () => {
                        const r = await run(() => post(`/messages/${f.institution_id}`, { text: `Reminder: ${f.id} (${f.bank_name}) matures on ${fmtDate(f.maturity_date)}. Please submit the renewed or replacement FDR before maturity.` }), `Reminder sent to ${f.institution_name}`);
                        if (r !== undefined) setSent(new Set(sent).add(f.id));
                      }}><Send size={13} aria-hidden /> {sent.has(f.id) ? 'Sent' : 'Remind'}</button>
                    ) : <span className="muted">—</span>}
                  </td>
                </tr>
              ))}
              {rows.length === 0 && <tr><td colSpan={9}><div className="empty">No FDRs in this window.</div></td></tr>}
            </tbody>
          </table>
        </TableWrap>
      </Panel>
    </Stagger>
  );
}
