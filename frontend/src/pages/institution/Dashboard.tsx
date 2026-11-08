import { motion } from 'framer-motion';
import { AlertTriangle, ArrowRight, CalendarDays, Clock3, Database, FileText, Plus, RefreshCw, Search, Send, ShieldCheck } from 'lucide-react';
import { useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import type { Bucket, Fdr, Institution, Stats } from '../../api/types';
import Hero from '../../components/Hero';
import { FdrTable, TableWrap } from '../../components/Tables';
import { CountUp, ErrorBox, Kpi, Loading, Panel, Stagger, StatusPill, Tabs, ViewAll, item } from '../../components/ui';
import { fmtDate, fmtTime, inrP } from '../../lib/format';
import { useApi, useStore } from '../../store/Store';
import { WhatChanged } from '../shared/Nudge';
import { Alert } from '../aicte/Dashboard';

interface InstDash {
  institution: Institution;
  stats: Stats;
  fdrs: Fdr[];
  maturing: Fdr[];
  activity: { at: string; type: string; data: string }[];
  last_bank_sync: string | null;
}

const ACTIVITY: Record<string, string> = {
  fdr_submitted: 'FDR submitted by institution', release_requested: 'Release requested', payee_registered: 'Bank account registered',
  login_success: 'Signed in', logout: 'Signed out',
};

export default function InstitutionDashboard() {
  const { user, refresh } = useStore();
  const nav = useNavigate();
  const [tab, setTab] = useState<'all' | Bucket>('all');
  const [q, setQ] = useState('');
  const base = '/institution';
  const d = useApi<InstDash>(user?.institution_id ? `/dashboard/institution/${user.institution_id}` : null);
  const rows = useMemo(() => (d.data?.fdrs ?? []).filter((f) => {
    const t = q.toLowerCase();
    return (tab === 'all' || f.bucket === tab) && (!t || f.id.toLowerCase().includes(t) || f.bank_name.toLowerCase().includes(t) || f.status.includes(t));
  }), [d.data, tab, q]);
  if (!d.data) return d.error ? <ErrorBox text={d.error} onRetry={refresh} /> : <Loading layout="dashboard" />;
  const { stats: s, fdrs, maturing, institution, activity, last_bank_sync } = d.data;
  const b = s.by_bucket;
  const pending = fdrs.filter((f) => f.status === 'pending');
  const disc = fdrs.filter((f) => f.status === 'discrepancy');
  const live = { count: b.active.count + b.maturing.count, amount: b.active.amount_paise + b.maturing.amount_paise };
  const plural = (n: number) => `${n} FDR${n === 1 ? '' : 's'}`;
  const compliance = disc.length ? 'Action required: a discrepancy is open' : pending.length ? `Compliant except ${pending.length} pending verification` : live.count ? 'Fully compliant' : 'No valid FDR on record';

  return (
    <div>
      <Hero role="institution" institution={institution} lastSync={last_bank_sync} />
      <Stagger>
        <WhatChanged />
        <div className="kpis k4" data-tour="kpis">
          <Kpi chevron tone="blue" icon={<Database size={40} />} label="Total Deposits" value={<CountUp id="inst.total" value={s.total.amount_paise / 100} format={(n) => inrP(n * 100)} />} sub={plural(s.total.count)} onClick={() => nav(`${base}/fdrs`)} />
          <Kpi chevron tone="green" icon={<ShieldCheck size={40} fill="var(--green)" color="var(--card)" />} label="Active FDRs" value={<CountUp id="inst.active" value={live.amount / 100} format={(n) => inrP(n * 100)} />} sub={plural(live.count)} onClick={() => nav(`${base}/fdrs`)} />
          <Kpi chevron tone="orange" icon={<Clock3 size={40} />} label="Pending Verification" value={<CountUp id="inst.pending" value={b.pending.amount_paise / 100} format={(n) => inrP(n * 100)} />} sub={plural(b.pending.count)} onClick={() => nav(`${base}/fdrs`)} />
          <Kpi chevron tone="purple" icon={<CalendarDays size={40} />} label="Maturing in 90 Days" value={<CountUp id="inst.maturing" value={b.maturing.amount_paise / 100} format={(n) => inrP(n * 100)} />} sub={plural(b.maturing.count)} onClick={() => nav(`${base}/renewals`)} />
        </div>

        <div className="row g-inst-mid">
          <Panel title="My FDRs / Security Deposits" style={{ paddingBottom: 18 }}>
            <div style={{ display: 'flex', gap: 18, marginBottom: 14, flexWrap: 'wrap' }}>
              <label className="field" style={{ flex: 1, minWidth: 240, borderRadius: 4 }}>
                <Search size={18} aria-hidden />
                <span className="sr-only">Search my FDRs</span>
                <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search by reference no., bank name or status..." />
              </label>
              <button className="btn btn-navy" onClick={() => nav(`${base}/upload`)}><Plus size={20} aria-hidden /> Upload New FDR</button>
            </div>
            <Tabs id="inst-fdrs" value={tab} onChange={setTab} tabs={[
              { key: 'all', label: `All (${fdrs.length})` }, { key: 'active', label: `Active (${b.active.count})` }, { key: 'pending', label: `Pending Verification (${b.pending.count})` },
              { key: 'maturing', label: `Maturing (${b.maturing.count})` }, { key: 'released', label: `Released (${b.released.count})` },
            ]} />
            <FdrTable caption="My FDRs" rows={rows} base={base} size="roomy" cols={['idx', 'ref', 'bank', 'amount', 'issue', 'maturity', 'bucket', 'action']} />
          </Panel>

          <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
            <Panel title="Important Alerts" action={<ViewAll to={`${base}/notifications`} />}>
              <div className="alerts">
                {disc.map((f) => (
                  <Alert key={f.id} tone="red" icon={<AlertTriangle size={20} />} title="Clarification required" sub={<>{f.id} · {f.discrepancy_reason}</>} to={`${base}/fdr/${f.id}`} />
                ))}
                {pending.length > 0 ? (
                  <Alert tone="orange" icon={<Clock3 size={22} />} title={`${plural(pending.length)} ${pending.length > 1 ? 'are' : 'is'} pending verification`}
                    sub={<>{pending[0].id} &nbsp;•&nbsp; {inrP(pending[0].amount_paise)}<br />Submitted on {fmtDate(pending[0].submitted_on)}</>} to={`${base}/fdr/${pending[0].id}`} />
                ) : (
                  <Alert tone="green" icon={<ShieldCheck size={20} />} title="No pending verifications" sub="All submitted FDRs have been scrutinised" />
                )}
                {maturing.length ? (
                  <Alert tone="red" icon={<CalendarDays size={20} />} title={`${plural(maturing.length)} maturing in next 90 days`} sub={`Earliest in ${Math.min(...maturing.map((f) => f.days_left))} days — submit renewal`} to={`${base}/renewals`} />
                ) : (
                  <Alert tone="plain" icon={<CalendarDays size={22} />} title="No FDRs maturing in next 90 days" sub="You will be notified in advance." to={`${base}/renewals`} />
                )}
              </div>
            </Panel>
            <Panel title="Compliance Status" className="panel-green">
              <div className="compliance-box" style={{ background: 'none', padding: '0 4px' }}>
                <div className="shield" aria-hidden><ShieldCheck size={38} /></div>
                <div>
                  <b>{compliance}</b>
                  <span>Based on current records and bank confirmations.</span>
                </div>
              </div>
            </Panel>
          </div>
        </div>

        <div className="row g-inst-bot">
          <Panel title="Recent Activity" action={<ViewAll to={`${base}/fdrs`} />}>
            <TableWrap label="Recent activity">
              <table className="tbl cardable">
                <caption className="sr-only">Recent activity</caption>
                <thead><tr><th scope="col">Date &amp; Time</th><th scope="col">Activity</th><th scope="col">Reference No.</th><th scope="col">Status</th></tr></thead>
                <tbody>
                  {activity.slice(0, 4).map((a, i) => {
                    const data = JSON.parse(a.data) as { fdr_id?: string; release_id?: string };
                    const ref = data.fdr_id ?? data.release_id ?? '—';
                    const f = fdrs.find((x) => x.id === data.fdr_id);
                    return (
                      <tr key={i}>
                        <td data-label="Date & Time" style={{ lineHeight: 1.35 }}>{fmtDate(a.at)}<br />{fmtTime(a.at)}</td>
                        <td data-label="Activity">{ACTIVITY[a.type] ?? a.type.replace(/_/g, ' ')}</td>
                        <td data-label="Reference No.">{ref}</td>
                        <td data-label="Status">{f ? <StatusPill status={f.bucket} /> : <StatusPill status="done" />}</td>
                      </tr>
                    );
                  })}
                  {activity.length === 0 && <tr className="empty-row"><td colSpan={4}><div className="empty"><b>No activity yet</b></div></td></tr>}
                </tbody>
              </table>
            </TableWrap>
          </Panel>
          <Panel title="Quick Actions">
            <div className="qa">
              <motion.button variants={item} className="qa-card qa-green" onClick={() => nav(`${base}/renewals`)}>
                <RefreshCw className="big" size={36} aria-hidden /><b>Request Renewal</b><span>Submit renewed or replacement FDR</span><ArrowRight className="go" size={22} aria-hidden />
              </motion.button>
              <motion.button variants={item} className="qa-card qa-orange" onClick={() => nav(`${base}/release`)}>
                <Send className="big" size={36} aria-hidden /><b>Request Refund / Release</b><span>Apply for release of deposit / refund</span><ArrowRight className="go" size={22} aria-hidden />
              </motion.button>
              <motion.button variants={item} className="qa-card qa-purple" onClick={() => nav(`${base}/guidelines`)}>
                <FileText className="big" size={36} aria-hidden /><b>View Guidelines</b><span>Check AICTE rules, formats and FAQs</span><ArrowRight className="go" size={22} aria-hidden />
              </motion.button>
            </div>
          </Panel>
        </div>
      </Stagger>
    </div>
  );
}
