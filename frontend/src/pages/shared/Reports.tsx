import { Download, Printer, Timer } from 'lucide-react';
import type { Compliance, Stats } from '../../api/types';
import { ComplianceBar, SeriesBars, StatusBars, ValueDonut } from '../../components/Charts';
import { ErrorBox, Kpi, Loading, PageHead, Panel, SimBadge, Stagger } from '../../components/ui';
import { croreP } from '../../lib/format';
import { useRole } from '../../lib/hooks';
import { useApi } from '../../store/Store';

interface Summary {
  stats: Stats;
  compliance: Compliance;
  submissions_by_month: { month: string; submitted: number }[];
  maturity_forecast: { month: string; count: number }[];
  value_by_bank: { bank: string; bank_name: string; amount_paise: number }[];
  top_states: { state: string; count: number }[];
  avg_days_to_bank_confirmation: number | null;
  confirmation_samples: number;
  note: string;
}

export default function Reports() {
  const { base } = useRole();
  const d = useApi<Summary>('/reports/summary');
  if (!d.data) return d.error ? <ErrorBox text={d.error} /> : <Loading layout="dashboard" />;
  const r = d.data;
  const banks = r.value_by_bank.map((b) => ({ name: b.bank, value: +(b.amount_paise / 1e9).toFixed(2) }));
  return (
    <Stagger>
      <PageHead title={base === '/auditor' ? 'Reports' : 'Reports & Analytics'} sub={r.note} crumbs={[{ label: 'Dashboard', to: base }, { label: 'Reports' }]}
        actions={<>
          <button className="btn btn-ghost" onClick={() => window.print()}><Printer size={17} aria-hidden /> Print</button>
          <a className="btn btn-primary" href="/api/reports/export.csv?kind=fdrs"><Download size={17} aria-hidden /> Export FDRs (CSV)</a>
        </>} />
      <div className="kpis k3">
        <Kpi tone="blue" icon={<Timer size={34} />} label="Avg. days: submission → bank confirmation" value={r.avg_days_to_bank_confirmation === null ? '—' : `${r.avg_days_to_bank_confirmation} days`} sub={`measured on ${r.confirmation_samples} FDRs in this database`} />
        <Kpi tone="green" icon={<Timer size={34} />} label="Total deposits on record" value={`₹ ${croreP(r.stats.total.amount_paise)} Cr`} sub={`${r.stats.total.count} FDRs`} />
        <Kpi tone="red" icon={<Timer size={34} />} label="FDRs with discrepancies" value={String(r.stats.fdrs_with_discrepancy)} sub={`at ${r.stats.institutions_with_discrepancy} institutions`} />
      </div>
      <div className="row g-2">
        <Panel title="Status distribution"><StatusBars id="rep.status" stats={r.stats} variant="auditor" height={230} /></Panel>
        <Panel title="Value distribution (₹ Crore)"><ValueDonut id="rep.value" stats={r.stats} base={base} /></Panel>
      </div>
      <div className="row g-2">
        <Panel title="Submissions by month (last 12 months)">
          <SeriesBars id="rep.submissions" caption="FDR submissions by month, last 12 months" data={r.submissions_by_month} xKey="month" yKey="submitted" name="Submitted" />
        </Panel>
        <Panel title="Maturity forecast (next 12 months)" sub="Red: next 3 months · amber: months 4–6 · blue: later">
          <SeriesBars id="rep.maturity" caption="FDRs maturing by month, next 12 months" data={r.maturity_forecast} xKey="month" yKey="count" name="FDRs maturing"
            colorAt={(i) => (i < 3 ? 'var(--chart-discrepancy)' : i < 6 ? 'var(--chart-pending)' : 'var(--chart-primary)')} />
        </Panel>
      </div>
      <div className="row g-3">
        <Panel title={<>Live deposit value by bank (₹ Cr) <SimBadge title="Bank names come from FDR records; balances are not read from any bank" /></>}>
          <SeriesBars id="rep.banks" caption="Live deposit value by bank, ₹ crore" data={banks} xKey="name" yKey="value" name="₹ Crore" horizontal height={280} unit=" Cr" />
        </Panel>
        <Panel title="Top states by live FDRs">
          <ul className="state-bars" aria-label={`Top states by live FDRs. Highest: ${r.top_states[0]?.state} ${r.top_states[0]?.count}.`}>
            {r.top_states.map((x) => (
              <li key={x.state}>
                <span>{x.state}</span>
                <span className="sb-track" aria-hidden><span className="sb-fill" style={{ transform: `scaleX(${x.count / r.top_states[0].count})` }} /></span>
                <b className="num">{x.count}</b>
              </li>
            ))}
          </ul>
        </Panel>
        <Panel title="Institution compliance"><ComplianceBar id="rep.compliance" c={r.compliance} /></Panel>
      </div>
    </Stagger>
  );
}
