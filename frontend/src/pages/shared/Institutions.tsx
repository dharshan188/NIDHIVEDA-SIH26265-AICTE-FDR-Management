import { Download, Mail, MapPin, Phone, Search } from 'lucide-react';
import { useEffect, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import type { Compliance, Fdr, Institution, Stats } from '../../api/types';
import { ComplianceBar } from '../../components/Charts';
import { FdrTable, Pager, TableWrap } from '../../components/Tables';
import { ErrorBox, Kpi, Loading, PageHead, Panel, Stagger, StatusPill, Tabs } from '../../components/ui';
import { croreP, inrP } from '../../lib/format';
import { useRole } from '../../lib/hooks';
import { useApi } from '../../store/Store';

const PILL: Record<string, 'active' | 'pending' | 'discrepancy' | 'closed'> = { Compliant: 'active', 'Pending Verification': 'pending', Discrepancy: 'discrepancy', 'No Valid FDR': 'closed' };
interface ListOut { total: number; counts: Record<string, number>; states: string[]; items: Institution[] }

export default function Institutions({ complianceView }: { complianceView?: boolean }) {
  const { base } = useRole();
  const nav = useNavigate();
  const [q, setQ] = useState('');
  const [dq, setDq] = useState('');
  const [state, setState] = useState('');
  const [comp, setComp] = useState('');
  const [page, setPage] = useState(1);
  useEffect(() => {
    const t = setTimeout(() => setDq(q), 250);
    return () => clearTimeout(t);
  }, [q]);
  useEffect(() => setPage(1), [dq, state, comp]);
  const qs = new URLSearchParams({ page: String(page), size: '14', ...(dq && { q: dq }), ...(state && { state }), ...(comp && { compliance: comp }) }).toString();
  const d = useApi<ListOut>(`/institutions?${qs}`, [qs]);
  const dash = useApi<{ compliance: Compliance }>(complianceView ? '/dashboard/auditor' : null);
  const title = complianceView ? 'Compliance Review' : base === '/aicte' ? 'Institution Directory' : 'All Institutions';
  const counts = d.data?.counts ?? {};
  const all = Object.values(counts).reduce((a, b) => a + b, 0);

  return (
    <Stagger>
      <PageHead title={title} sub={`${all || '…'} AICTE-approved institutions`} crumbs={[{ label: 'Dashboard', to: base }, { label: title }]}
        actions={<a className="btn btn-ghost" href="/api/reports/export.csv?kind=institutions"><Download size={17} aria-hidden /> Export</a>} />
      {complianceView && dash.data && <Panel title="Institution Compliance Summary" style={{ marginBottom: 12 }}><ComplianceBar id="inst.compliance" c={dash.data.compliance} /></Panel>}
      <Panel>
        <Tabs id="inst-comp" value={comp} onChange={setComp} tabs={[
          { key: '', label: `All (${all})` }, { key: 'Compliant', label: `Compliant (${counts.Compliant ?? 0})` }, { key: 'Pending Verification', label: `Pending (${counts['Pending Verification'] ?? 0})` },
          { key: 'Discrepancy', label: `Has a discrepancy (${counts.Discrepancy ?? 0})` }, { key: 'No Valid FDR', label: `No Valid FDR (${counts['No Valid FDR'] ?? 0})` },
        ]} />
        <div className="toolbar">
          <label className="field" style={{ flex: 1, minWidth: 220 }}><Search size={18} aria-hidden /><span className="sr-only">Search</span><input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search by name, AICTE ID or city" /></label>
          <select className="sel" style={{ height: 40 }} value={state} onChange={(e) => setState(e.target.value)} aria-label="State"><option value="">All states</option>{(d.data?.states ?? []).map((s) => <option key={s}>{s}</option>)}</select>
        </div>
        {d.error ? <ErrorBox text={d.error} /> : !d.data ? <Loading rows={8} /> : (
          <>
            <TableWrap label={title}>
              <table className="tbl cardable">
                <caption className="sr-only">{title}</caption>
                <thead><tr><th scope="col" className="c">#</th><th scope="col">Institution Name</th><th scope="col">AICTE ID</th><th scope="col">Type</th><th scope="col">Location</th><th scope="col" className="c">Live FDRs</th><th scope="col">Deposit Held</th><th scope="col">Compliance</th></tr></thead>
                <tbody>
                  {d.data.items.map((r, i) => (
                    <tr key={r.id} className="clickable" onClick={() => nav(`${base}/institutions/${r.id}`)}>
                      <td className="c">{(page - 1) * 14 + i + 1}</td>
                      <td><Link to={`${base}/institutions/${r.id}`} onClick={(e) => e.stopPropagation()} style={{ fontWeight: 500, color: 'var(--ink)' }}>{r.name}</Link></td>
                      <td>{r.aicte_id}</td><td>{r.type}</td><td>{r.city}, {r.state}</td>
                      <td className="c">{r.live_fdrs}</td><td className="num">{inrP(r.amount_paise ?? 0)}</td>
                      <td><StatusPill status={PILL[r.compliance ?? 'No Valid FDR']} label={r.compliance} /></td>
                    </tr>
                  ))}
                  {d.data.items.length === 0 && <tr><td colSpan={8}><div className="empty">No institutions match the filters</div></td></tr>}
                </tbody>
              </table>
            </TableWrap>
            <Pager page={page} size={14} total={d.data.total} onPage={setPage} />
          </>
        )}
      </Panel>
    </Stagger>
  );
}

export function InstitutionDetail() {
  const { id } = useParams();
  const { base } = useRole();
  const d = useApi<{ institution: Institution; fdrs: Fdr[]; stats: Stats }>(`/institutions/${id}`, [id]);
  const [tab, setTab] = useState<'live' | 'all'>('live');
  if (!d.data) return d.error ? <ErrorBox text={d.error} /> : <Loading rows={8} />;
  const { institution: inst, fdrs, stats } = d.data;
  const live = fdrs.filter((f) => ['verified', 'pending', 'discrepancy'].includes(f.status));
  return (
    <Stagger>
      <PageHead title={inst.name} sub={`AICTE ID: ${inst.aicte_id} · ${inst.type} · Est. ${inst.established}`} crumbs={[{ label: 'Dashboard', to: base }, { label: 'Institutions', to: `${base}/institutions` }, { label: inst.name }]} />
      <div className="kpis k3">
        <Kpi tone="blue" icon={<MapPin size={34} />} label="Location" value={<span style={{ fontSize: 19 }}>{inst.city}</span>} sub={inst.state} />
        <Kpi tone="green" icon={<Mail size={34} />} label="Live FDRs" value={String(live.length)} sub={`₹ ${croreP(live.reduce((s, f) => s + f.amount_paise, 0))} Crore`} />
        <Kpi tone="purple" icon={<Phone size={34} />} label="All instruments" value={String(stats.total.count)} sub={`${stats.by_bucket.released.count} released · ${stats.by_bucket.closed.count} closed`} />
      </div>
      <div className="row g-side">
        <Panel title="Security Deposits / FDRs">
          <Tabs id="inst-detail" value={tab} onChange={setTab} tabs={[{ key: 'live', label: `Live (${live.length})` }, { key: 'all', label: `All (${fdrs.length})` }]} />
          <FdrTable caption="Institution FDRs" rows={tab === 'live' ? live : fdrs} base={base} cols={['idx', 'ref', 'bank', 'amount', 'maturity', 'days', 'bucket', 'action']} />
        </Panel>
        <Panel title="Contact">
          <dl className="kv" style={{ gridTemplateColumns: '110px 1fr' }}>
            <dt>Head</dt><dd>{inst.principal}</dd>
            <dt>Email</dt><dd>{inst.email}</dd>
            <dt>Phone</dt><dd>{inst.phone}</dd>
            <dt>Intake</dt><dd>{inst.intake} / year</dd>
          </dl>
        </Panel>
      </div>
    </Stagger>
  );
}
