import { Download, Plus, Search } from 'lucide-react';
import { useEffect, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import type { Fdr } from '../../api/types';
import { BUCKETS } from '../../components/Charts';
import { FdrTable, Pager } from '../../components/Tables';
import { ErrorBox, Loading, PageHead, Panel, Stagger, Tabs } from '../../components/ui';
import { croreP } from '../../lib/format';
import { useRole } from '../../lib/hooks';
import { useApi } from '../../store/Store';

const BANKS: [string, string][] = [['SBI', 'State Bank of India'], ['HDFC', 'HDFC Bank'], ['ICICI', 'ICICI Bank'], ['CANARA', 'Canara Bank'], ['PNB', 'Punjab National Bank'],
  ['BOB', 'Bank of Baroda'], ['AXIS', 'Axis Bank'], ['UNION', 'Union Bank of India'], ['INDIAN', 'Indian Bank'], ['BOI', 'Bank of India'], ['KOTAK', 'Kotak Mahindra Bank'], ['IDBI', 'IDBI Bank']];

interface ListOut { total: number; amount_paise: number; counts: Record<string, number>; items: Fdr[] }

export default function FdrList() {
  const { role, base } = useRole();
  const nav = useNavigate();
  const [params, setParams] = useSearchParams();
  const bucket = params.get('bucket') ?? '';
  const [q, setQ] = useState('');
  const [debounced, setDebounced] = useState('');
  const [bank, setBank] = useState('');
  const [sort, setSort] = useState('submitted');
  const [unconfirmed, setUnconfirmed] = useState(false);
  const [page, setPage] = useState(1);
  useEffect(() => {
    const t = setTimeout(() => setDebounced(q), 250);
    return () => clearTimeout(t);
  }, [q]);
  useEffect(() => setPage(1), [bucket, debounced, bank, sort, unconfirmed]);
  const qs = new URLSearchParams({ page: String(page), size: '12', sort, ...(bucket && { bucket }), ...(debounced && { q: debounced }), ...(bank && { bank }), ...(unconfirmed && { bank_confirmed: '0' }) });
  const all = useApi<ListOut>(`/fdrs?size=1`);
  const d = useApi<ListOut>(`/fdrs?${qs}`, [qs.toString()]);
  const counts = all.data?.counts ?? {};
  const title = role === 'aicte' ? 'FDR Submissions' : role === 'auditor' ? 'FDR Records' : 'My FDRs / Deposits';

  return (
    <Stagger>
      <PageHead title={title} sub={d.data ? `${d.data.total.toLocaleString('en-IN')} instruments · ₹ ${croreP(d.data.amount_paise)} Crore` : 'Loading…'}
        crumbs={[{ label: 'Dashboard', to: base }, { label: title }]}
        actions={<>
          {role !== 'institution' && <a className="btn btn-ghost" href="/api/reports/export.csv?kind=fdrs"><Download size={17} aria-hidden /> Export CSV</a>}
          {role === 'institution' && <button className="btn btn-navy" onClick={() => nav(`${base}/upload`)}><Plus size={18} aria-hidden /> Upload New FDR</button>}
        </>} />
      <Panel>
        <Tabs id="fdr-list" value={bucket} onChange={(k) => setParams(k ? { bucket: k } : {})}
          tabs={[{ key: '', label: `All (${all.data?.total ?? '…'})` }, ...BUCKETS.map((b) => ({ key: b.key as string, label: `${b.label} (${counts[b.key] ?? 0})` }))]} />
        <div className="toolbar">
          <label className="field" style={{ flex: 1, minWidth: 220 }}>
            <Search size={18} aria-hidden /><span className="sr-only">Search</span>
            <input value={q} onChange={(e) => setQ(e.target.value)} placeholder={role === 'institution' ? 'Search by reference or FDR number' : 'Search by institution, reference or FDR number'} />
          </label>
          <select className="sel" style={{ height: 40 }} value={bank} onChange={(e) => setBank(e.target.value)} aria-label="Bank">
            <option value="">All banks</option>
            {BANKS.map(([c, n]) => <option key={c} value={c}>{n}</option>)}
          </select>
          <select className="sel" style={{ height: 40 }} value={sort} onChange={(e) => setSort(e.target.value)} aria-label="Sort">
            <option value="submitted">Newest first</option>
            <option value="maturity">Earliest maturity</option>
            <option value="amount">Highest amount</option>
          </select>
          <label className="chip" style={{ cursor: 'pointer', height: 40, borderRadius: 6, padding: '0 12px', fontSize: 13 }}>
            <input type="checkbox" className="chk" checked={unconfirmed} onChange={(e) => setUnconfirmed(e.target.checked)} /> Not bank-confirmed
          </label>
        </div>
        {d.error ? <ErrorBox text={d.error} /> : !d.data ? <Loading rows={8} /> : (
          <>
            <FdrTable caption={title} rows={d.data.items} offset={(page - 1) * 12} base={base}
              cols={role === 'institution' ? ['idx', 'ref', 'bank', 'amount', 'maturity', 'days', 'source', 'bucket', 'action'] : ['idx', 'inst', 'ref', 'bank', 'amount', 'maturity', 'days', 'source', 'bucket', 'action']} />
            <Pager page={page} size={12} total={d.data.total} onPage={setPage} />
          </>
        )}
      </Panel>
    </Stagger>
  );
}
