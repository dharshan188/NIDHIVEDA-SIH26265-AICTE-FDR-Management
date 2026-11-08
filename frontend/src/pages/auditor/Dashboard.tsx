import { AlertTriangle, ArrowRight, ArrowUp, BarChart3, CalendarDays, Clock3, Database, FileCheck2, FileText, Landmark, Search, ShieldCheck } from 'lucide-react';
import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { ComplianceBar, StatusBars, ValueDonut } from '../../components/Charts';
import Hero from '../../components/Hero';
import { FdrTable, MaturityTable } from '../../components/Tables';
import { CountUp, ErrorBox, Kpi, Loading, Panel, Stagger, ViewAll } from '../../components/ui';
import { croreP, pct } from '../../lib/format';
import { useT } from '../../lib/prefs';
import { useApi, useStore } from '../../store/Store';
import { WhatChanged } from '../shared/Nudge';
import { Alert, type DashData } from '../aicte/Dashboard';

export default function AuditorDashboard() {
  const nav = useNavigate();
  const { refresh } = useStore();
  const base = '/auditor';
  const [metric, setMetric] = useState('count');
  const t = useT();
  const d = useApi<DashData>('/dashboard/auditor');
  if (!d.data) return d.error ? <ErrorBox text={d.error} onRetry={refresh} /> : <Loading layout="dashboard" />;
  const { stats: s, recent, maturing, compliance, last_bank_sync } = d.data;
  const b = s.by_bucket;
  const T = s.total.count;
  const sub = (amt: number, n: number) => <>₹ {croreP(amt)} Crore<br />({pct(n, T)}%)</>;

  return (
    <div>
      <Hero role="auditor" lastSync={last_bank_sync} />
      <Stagger>
        <WhatChanged />
        <div className="kpis k6" data-tour="kpis">
          <Kpi compact tone="blue" icon={<Landmark size={36} />} label="Total Institutions" value={<CountUp id="aud.institutions" value={s.institutions} />} extra={<span className="up"><ArrowUp size={15} aria-hidden /> {s.institutions_submitting_this_week} this week</span>} onClick={() => nav(`${base}/institutions`)} />
          <Kpi compact tone="green" icon={<Database size={36} />} label="Total FDRs" value={<CountUp id="aud.total" value={T} />} sub={<>₹ {croreP(s.total.amount_paise)} Crore</>} onClick={() => nav(`${base}/fdrs`)} />
          <Kpi compact tone="green" icon={<ShieldCheck size={36} />} label="Active / Verified FDRs" value={<CountUp id="aud.active" value={b.active.count} />} sub={sub(b.active.amount_paise, b.active.count)} onClick={() => nav(`${base}/fdrs?bucket=active`)} />
          <Kpi compact tone="orange" icon={<Clock3 size={36} />} label="Pending Verification" value={<CountUp id="aud.pending" value={b.pending.count} />} sub={sub(b.pending.amount_paise, b.pending.count)} onClick={() => nav(`${base}/fdrs?bucket=pending`)} />
          <Kpi compact tone="red" icon={<CalendarDays size={36} />} label="Maturing in 90 Days" value={<CountUp id="aud.maturing" value={b.maturing.count} />} sub={sub(b.maturing.amount_paise, b.maturing.count)} onClick={() => nav(`${base}/renewals`)} />
          <Kpi compact tone="purple" icon={<FileText size={36} />} label="Release Requests" value={<CountUp id="aud.releases" value={s.open_release_requests.count} />} sub={<>₹ {croreP(s.open_release_requests.amount_paise)} Crore</>} onClick={() => nav(`${base}/releases`)} />
        </div>

        <div className="row g-aud-top">
          <Panel title="FDR Status Distribution" action={
            <select className="sel" value={metric} onChange={(e) => setMetric(e.target.value)} style={{ width: 168 }} aria-label={t('Chart metric')}>
              <option value="count">{t('Count of FDRs')}</option>
              <option value="value">{t('Value (₹ Crore)')}</option>
            </select>}>
            {metric === 'count' ? <StatusBars id="aud.status" stats={s} variant="auditor" height={200} onBar={(k) => nav(`${base}/fdrs?bucket=${k}`)} /> : <ValueDonut id="aud.status-value" stats={s} base={base} />}
          </Panel>
          <Panel title="FDR Value Distribution (₹ Crore)">
            <ValueDonut id="aud.value" stats={s} base={base} />
          </Panel>
        </div>

        <div className="row g-aud-mid">
          <Panel title="Recent Submissions for Audit Review" action={<ViewAll to={`${base}/fdrs`} />}>
            <FdrTable caption="Recent submissions" rows={recent} base={base} size="tight" cols={['idx', 'inst', 'ref', 'bank', 'amount', 'submitted', 'status', 'action']} />
          </Panel>
          <Panel title="Audit Focus Areas" action={<ViewAll to={`${base}/compliance`} />}>
            <div className="alerts" style={{ gap: 6 }}>
              <Alert tone="red" plainIcon icon={<Clock3 size={30} color="var(--orange-600)" />} title={`${b.pending.count} submissions pending verification`} sub="Review completeness and compliance" to={`${base}/fdrs?bucket=pending`} />
              <Alert tone="purple" plainIcon icon={<AlertTriangle size={30} color="var(--red)" />} title={`${s.fdrs_with_discrepancy} FDRs with discrepancies`} sub="Check details and request clarification" to={`${base}/discrepancies`} />
              <Alert tone="purple" plainIcon icon={<CalendarDays size={30} color="var(--purple)" />} title={`${b.maturing.count} FDRs maturing in next 90 days`} sub="Ensure renewal / replacement process" to={`${base}/renewals`} />
              <Alert tone="plain" plainIcon icon={<FileCheck2 size={30} color="var(--primary)" />} title={`${s.open_release_requests.count} release requests under process`} sub="Verify eligibility and approvals" to={`${base}/releases`} />
            </div>
          </Panel>
        </div>

        <div className="row g-aud-bot">
          <Panel title="Institution Compliance Summary" action={<ViewAll to={`${base}/compliance`} />}>
            <ComplianceBar id="aud.compliance" c={compliance} />
          </Panel>
          <Panel title="Upcoming Maturities (Next 90 Days)" action={<ViewAll to={`${base}/renewals`} />}>
            <MaturityTable rows={maturing} base={base} />
          </Panel>
          <Panel title="Audit Actions">
            <div className="aud-actions">
              <button onClick={() => nav(`${base}/fdrs?bucket=pending`)}><FileText className="lg" size={32} aria-hidden /><span>Review<br />Submissions</span><ArrowRight className="ar" size={16} aria-hidden /></button>
              <button onClick={() => nav(`${base}/discrepancies`)}><Search className="lg" size={32} aria-hidden /><span>Check<br />Discrepancies</span><ArrowRight className="ar" size={16} aria-hidden /></button>
              <button onClick={() => nav(`${base}/audit-trail`)}><Landmark className="lg" size={32} aria-hidden /><span>Verify<br />Audit Ledger</span><ArrowRight className="ar" size={16} aria-hidden /></button>
              <button onClick={() => nav(`${base}/reports`)}><BarChart3 className="lg" size={32} aria-hidden /><span>Generate<br />Audit Report</span><ArrowRight className="ar" size={16} aria-hidden /></button>
            </div>
          </Panel>
        </div>
      </Stagger>
    </div>
  );
}
