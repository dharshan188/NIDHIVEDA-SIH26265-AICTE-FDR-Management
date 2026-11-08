import { motion } from 'framer-motion';
import { ArrowUp, BellRing, CalendarDays, ChevronRight, ClipboardCheck, Clock3, Database, FileText, Info, Landmark, Search, ShieldAlert } from 'lucide-react';
import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import type { Bucket, Compliance, Fdr, Paged, Stats } from '../../api/types';
import { StatusBars } from '../../components/Charts';
import { LifecycleFlow } from '../../components/Flowchart';
import Hero from '../../components/Hero';
import { FdrTable, MaturityTable } from '../../components/Tables';
import { CountUp, ErrorBox, Kpi, Loading, Panel, Stagger, Tabs, ViewAll, item } from '../../components/ui';
import { croreP } from '../../lib/format';
import { useT } from '../../lib/prefs';
import { useApi, useStore } from '../../store/Store';
import { WhatChanged } from '../shared/Nudge';

export interface DashData {
  stats: Stats;
  recent: Fdr[];
  maturing: Fdr[];
  compliance: Compliance;
  last_bank_sync: string | null;
  pipeline?: { bank_unconfirmed_pending: number; renewals: number; release_by_stage: Record<string, number> };
}

type T = 'all' | Bucket;

export default function AicteDashboard() {
  const nav = useNavigate();
  const { refresh } = useStore();
  const t = useT();
  const [tab, setTab] = useState<T>('all');
  const base = '/aicte';
  const d = useApi<DashData>('/dashboard/aicte');
  const recent = useApi<Paged<Fdr>>(`/fdrs?size=5&sort=submitted${tab === 'all' ? '' : `&bucket=${tab}`}`, [tab]);

  if (!d.data) return d.error ? <ErrorBox text={d.error} onRetry={refresh} /> : <Loading layout="dashboard" />;
  const { stats: s, maturing, last_bank_sync, pipeline } = d.data;
  const b = s.by_bucket;
  const rel = pipeline?.release_by_stage ?? {};

  return (
    <div>
      <Hero role="aicte" lastSync={last_bank_sync} />
      <Stagger>
        <WhatChanged />
        <div className="kpis k5" data-tour="kpis">
          <Kpi tone="blue" icon={<Landmark size={38} />} label="Total Institutions" value={<CountUp id="aicte.institutions" value={s.institutions} />}
            extra={<span className="up"><ArrowUp size={15} aria-hidden /> {s.institutions_submitting_this_week} submitted this week</span>} onClick={() => nav(`${base}/institutions`)} />
          <Kpi tone="green" icon={<Database size={38} />} label="Active FDRs" value={<CountUp id="aicte.active" value={b.active.count} />} sub={<>₹ {croreP(b.active.amount_paise)} Crore</>} onClick={() => nav(`${base}/submissions?bucket=active`)} />
          <Kpi tone="orange" icon={<Clock3 size={38} />} label="Pending Verification" value={<CountUp id="aicte.pending" value={b.pending.count} />} sub={<>₹ {croreP(b.pending.amount_paise)} Crore</>} onClick={() => nav(`${base}/verification`)} />
          <Kpi tone="red" icon={<CalendarDays size={38} />} label="Maturing in 90 Days" value={<CountUp id="aicte.maturing" value={b.maturing.count} />} sub={<>₹ {croreP(b.maturing.amount_paise)} Crore</>} onClick={() => nav(`${base}/renewals`)} />
          <Kpi tone="purple" icon={<ClipboardCheck size={38} />} label="Release Requests" value={<CountUp id="aicte.releases" value={s.open_release_requests.count} />} sub={<>₹ {croreP(s.open_release_requests.amount_paise)} Crore</>} onClick={() => nav(`${base}/releases`)} />
        </div>

        <div className="row g-aicte-mid">
          <Panel title="Recent FDR Submissions" action={<ViewAll to={`${base}/submissions`} />}>
            <Tabs id="aicte-recent" value={tab} onChange={setTab} tabs={[
              { key: 'all', label: 'All' }, { key: 'pending', label: `Pending Verification (${b.pending.count})` }, { key: 'active', label: 'Active' },
              { key: 'discrepancy', label: `Discrepancy (${b.discrepancy.count})` }, { key: 'maturing', label: 'Maturing' },
            ]} />
            {recent.error ? <ErrorBox text={recent.error} /> : !recent.data ? <Loading layout="table" rows={5} /> : (
              <FdrTable caption="Most recent FDR submissions" rows={recent.data.items} base={base} cols={['idx', 'inst', 'ref', 'bank', 'amount', 'maturity', 'status', 'action']} />
            )}
          </Panel>

          <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
            <Panel title="Important Alerts" action={<ViewAll to={`${base}/notifications`} />}>
              <div className="alerts">
                <Alert tone="red" icon={<BellRing size={19} />} title={`${b.maturing.count} FDRs maturing in next 90 days`} sub="Action required for renewal/replacement" to={`${base}/renewals`} />
                <Alert tone="orange" icon={<BellRing size={19} />} title={`${b.pending.count} submissions pending verification`} sub="Review and complete scrutiny" to={`${base}/verification`} />
                <Alert tone="blue" icon={<ShieldAlert size={19} />} title={`${s.fdrs_with_discrepancy} FDRs with discrepancies`} sub="Check details and request clarification" to={`${base}/verification?tab=discrepancy`} />
                <Alert tone="navy" icon={<Info size={20} />} title={`${s.open_release_requests.count} release requests under process`} sub="Pending approvals from competent authority" to={`${base}/releases`} />
              </div>
            </Panel>
            <Panel title="Quick Access">
              <div className="tiles">
                <button className="tile" onClick={() => nav(`${base}/verification`)}><Search size={26} aria-hidden />Scrutinize<br />Submissions</button>
                <button className="tile" onClick={() => nav(`${base}/reconciliation`)}><Landmark size={27} aria-hidden />Verify<br />Bank Details</button>
                <button className="tile" onClick={() => nav(`${base}/releases`)}><FileText size={27} aria-hidden />Process<br />Release Request</button>
              </div>
            </Panel>
          </div>
        </div>

        <div className="row g-aicte-bot">
          <Panel title={<>{t('FDR Status Distribution')} (Total: <span className="num">{s.total.count.toLocaleString('en-IN')}</span>)</>}>
            <StatusBars id="aicte.status" stats={s} variant="aicte" height={204} onBar={(k) => nav(`${base}/submissions?bucket=${k}`)} />
          </Panel>
          <Panel title="Upcoming Maturities (Next 90 Days)" action={<ViewAll to={`${base}/renewals`} />}>
            <MaturityTable rows={maturing} base={base} />
          </Panel>
        </div>

        <Panel title="FDR Lifecycle Pipeline" sub="Live count of instruments at each stage, from the database" action={<ViewAll to={`${base}/reports`} label="Open Analytics" />}>
          <LifecycleFlow id="aicte.pipeline" counts={{
            submit: s.total.count, docs: b.pending.count, bank: pipeline?.bank_unconfirmed_pending ?? 0, disc: b.discrepancy.count,
            active: b.active.count, monitor: b.maturing.count, renew: pipeline?.renewals ?? 0,
            request: rel.SUBMITTED ?? 0, scrutiny: rel.SCRUTINY_DONE ?? 0, authority: rel.APPROVED ?? 0, released: b.released.count,
          }} state={{ disc: 'alert' }} />
        </Panel>
      </Stagger>
    </div>
  );
}

export function Alert({ tone, icon, title, sub, to, plainIcon }: { tone: string; icon: React.ReactNode; title: React.ReactNode; sub: React.ReactNode; to?: string; plainIcon?: boolean }) {
  const nav = useNavigate();
  return (
    <motion.button className={`alert a-${tone}`} variants={item} onClick={() => to && nav(to)}>
      <span className={`ai${plainIcon ? ' ico-only' : ''}`} aria-hidden>{icon}</span>
      <span style={{ minWidth: 0 }}>
        <b>{title}</b>
        <span>{sub}</span>
      </span>
      <ChevronRight className="chev" size={18} aria-hidden />
    </motion.button>
  );
}
