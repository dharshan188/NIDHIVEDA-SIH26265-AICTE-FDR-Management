import { motion } from 'framer-motion';
import { FileDown, FileSpreadsheet, ShieldCheck } from 'lucide-react';
import { useEffect, useRef, type ReactNode } from 'react';
import { useNavigate } from 'react-router-dom';
import type { Fdr } from '../api/types';
import { downloadFile, errorText } from '../api/client';
import { downloadCsv, fileSlug, tableRows } from '../lib/export';
import { fmtDate, inrP } from '../lib/format';
import { T } from '../lib/motion';
import { useT } from '../lib/prefs';
import { useStore } from '../store/Store';
import { DaysLeft, StatusPill } from './ui';

/**
 * Scrollable table container with CSV / PDF export of what it shows. `tall` caps the height so the header stays
 * visible (sticky) while the rows scroll. Cells carry data-label so the table can collapse to cards on phones.
 */
export function TableWrap({ label, children, simulated, tall, style, exportName, note, scrollRef }: {
  label: string; children: ReactNode; simulated?: boolean; tall?: boolean; style?: React.CSSProperties; exportName?: string; note?: string;
  scrollRef?: React.RefObject<HTMLDivElement | null>;
}) {
  const own = useRef<HTMLDivElement>(null);
  const ref = scrollRef ?? own;
  const t = useT();
  const { toast } = useStore();
  const table = () => ref.current?.querySelector('table') ?? null;
  // Phones show each row as a card: give every cell its column name unless the page already set one.
  useEffect(() => {
    const tb = table();
    if (!tb) return;
    const heads = Array.from(tb.tHead?.rows[0]?.cells ?? []).map((c) => (c.textContent ?? '').trim());
    for (const row of Array.from(tb.tBodies[0]?.rows ?? [])) {
      Array.from(row.cells).forEach((c, i) => {
        if (!c.dataset.label && heads[i] && c.colSpan === 1) c.dataset.label = heads[i];
      });
    }
  });
  const csv = () => {
    const tb = table();
    if (!tb) return;
    const rows = tableRows(tb);
    downloadCsv(fileSlug(exportName ?? label), rows, simulated ? 'Bank-sourced values in this export are SIMULATED (bank simulator, not a real bank).' : note);
    toast(`${label}: ${rows.length - 1} rows exported as CSV`, 'info');
  };
  const pdf = async () => {
    const tb = table();
    if (!tb) return;
    const [columns, ...rows] = tableRows(tb);
    // the server renders the rows exactly as shown, in the print-packet layout, and audits the export
    try {
      await downloadFile('/exports/pdf', `${fileSlug(exportName ?? label)}.pdf`, { title: label, subtitle: note ?? null, columns, rows, simulated: !!simulated });
      toast(`${label}: ${rows.length} rows exported as PDF`, 'info');
    } catch (e) {
      toast(errorText(e), 'error');
    }
  };
  return (
    <div className="table-block">
      <div className="table-tools" data-no-print>
        <button type="button" className="tt-btn" onClick={csv} aria-label={`${t('Export CSV')}: ${label}`}><FileSpreadsheet size={14} aria-hidden /> CSV</button>
        <button type="button" className="tt-btn" onClick={pdf} aria-label={`${t('Export PDF')}: ${label}`}><FileDown size={14} aria-hidden /> PDF</button>
      </div>
      <div ref={ref} className={`table-wrap${tall ? ' tall' : ''}`} tabIndex={0} role="region" aria-label={label} style={style}>
        {children}
      </div>
    </div>
  );
}

export type Col = 'idx' | 'inst' | 'ref' | 'bank' | 'amount' | 'issue' | 'maturity' | 'submitted' | 'status' | 'bucket' | 'days' | 'source' | 'action';

const HEAD: Record<Col, string> = {
  idx: '#', inst: 'Institution Name', ref: 'FDR Reference No.', bank: 'Bank Name', amount: 'Amount', issue: 'Issue Date',
  maturity: 'Maturity Date', submitted: 'Submitted On', status: 'Status', bucket: 'Status', days: 'Days Left', source: 'Bank Check', action: 'Action',
};

/** Navigation state that lets the detail page show the reference and status at once, so they can travel into its header. */
export interface FdrNavState { fdr: { id: string; bucket: Fdr['bucket'] } }

export function FdrTable({ rows, cols, base, size = 'normal', offset = 0, caption, simulated }: {
  rows: Fdr[]; cols: Col[]; base: string; size?: 'normal' | 'roomy' | 'tight'; offset?: number; caption: string; simulated?: boolean;
}) {
  const nav = useNavigate();
  const t = useT();
  const open = (f: Fdr) => nav(`${base}/fdr/${f.id}`, { state: { fdr: { id: f.id, bucket: f.bucket } } satisfies FdrNavState });
  return (
    <TableWrap label={caption} simulated={simulated ?? cols.includes('source')}>
      <table className={`tbl cardable ${size === 'roomy' ? 'roomy' : size === 'tight' ? 'tight' : ''}`}>
        <caption className="sr-only">{caption}</caption>
        <thead>
          <tr>{cols.map((c) => <th key={c} scope="col" className={c === 'action' || c === 'days' || c === 'source' ? 'c' : c === 'amount' ? 'r' : ''}>{t(HEAD[c])}</th>)}</tr>
        </thead>
        <tbody>
          {rows.map((f, i) => (
            <tr key={f.id} className="clickable" onClick={() => open(f)}>
              {cols.map((c) => {
                const dl = t(HEAD[c]);
                switch (c) {
                  case 'idx': return <td key={c} className="c num" data-label={dl}>{offset + i + 1}</td>;
                  case 'inst': return <td key={c} className="ell" data-label={dl} title={f.institution_name ?? ''}>{f.institution_name}</td>;
                  case 'ref': return <td key={c} data-label={dl}><motion.span layoutId={`fdr-ref-${f.id}`} transition={T.route} className="ref-id">{f.id}</motion.span></td>;
                  case 'bank': return <td key={c} data-label={dl}>{f.bank_name}</td>;
                  case 'amount': return <td key={c} className="num r" data-label={dl}>{inrP(f.amount_paise)}</td>;
                  case 'issue': return <td key={c} data-label={dl}>{fmtDate(f.issue_date)}</td>;
                  case 'maturity': return <td key={c} data-label={dl}>{fmtDate(f.maturity_date)}</td>;
                  case 'submitted': return <td key={c} data-label={dl}>{fmtDate(f.submitted_on)}</td>;
                  case 'status': return <td key={c} data-label={dl}><StatusPill status={f.status} wrap={size === 'normal'} /></td>;
                  case 'bucket': return <td key={c} data-label={dl}><StatusPill status={f.bucket} wrap={size === 'roomy'} layoutId={`fdr-pill-${f.id}`} /></td>;
                  case 'days': return <td key={c} className="c" data-label={dl}>{f.status === 'verified' ? <DaysLeft days={f.days_left} /> : '—'}</td>;
                  case 'source': return (
                    <td key={c} className="c" data-label={dl}>
                      {f.bank_confirmed ? <span className="src bank"><ShieldCheck size={12} aria-hidden /> {t('Bank confirmed')}</span> : <span className="src inst">{t('Institution declared')}</span>}
                    </td>
                  );
                  case 'action': return (
                    <td key={c} className="c" data-label={dl} onClick={(e) => e.stopPropagation()}>
                      <button className="btn btn-ghost btn-xs" onClick={() => open(f)} aria-label={`${f.status === 'pending' || f.status === 'discrepancy' ? 'Review' : 'View'} ${f.id}`}>
                        {t(f.status === 'pending' || f.status === 'discrepancy' ? 'Review' : 'View')}
                      </button>
                    </td>
                  );
                }
                return null;
              })}
            </tr>
          ))}
          {rows.length === 0 && (
            <tr className="empty-row"><td colSpan={cols.length}><div className="empty"><b>{t('No records match the current filters')}</b></div></td></tr>
          )}
        </tbody>
      </table>
    </TableWrap>
  );
}

export function MaturityTable({ rows, base }: { rows: Fdr[]; base: string }) {
  const nav = useNavigate();
  return (
    <TableWrap label="Upcoming maturities (next 90 days)" style={{ border: 0 }}>
      <table className="tbl cardable">
        <caption className="sr-only">FDRs maturing in the next 90 days</caption>
        <thead>
          <tr>
            <th scope="col" className="c">#</th><th scope="col">Institution Name</th><th scope="col">Maturity Date</th><th scope="col" className="r">Amount</th>
            <th scope="col" className="c">Days Left</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((f, i) => (
            <tr key={f.id} className="clickable" onClick={() => nav(`${base}/fdr/${f.id}`, { state: { fdr: { id: f.id, bucket: f.bucket } } satisfies FdrNavState })}>
              <td className="c num" data-label="#">{i + 1}</td>
              <td className="ell" data-label="Institution Name" title={f.institution_name ?? ''}>{f.institution_name}</td>
              <td data-label="Maturity Date">{fmtDate(f.maturity_date)}</td>
              <td className="num r" data-label="Amount">{inrP(f.amount_paise)}</td>
              <td className="c" data-label="Days Left"><DaysLeft days={f.days_left} /></td>
            </tr>
          ))}
          {rows.length === 0 && <tr className="empty-row"><td colSpan={5}><div className="empty"><b>No FDRs mature in the next 90 days</b></div></td></tr>}
        </tbody>
      </table>
    </TableWrap>
  );
}

export function Pager({ page, size, total, onPage }: { page: number; size: number; total: number; onPage: (p: number) => void }) {
  const pages = Math.max(1, Math.ceil(total / size));
  const nums = Array.from({ length: pages }, (_, i) => i + 1).filter((i) => i === 1 || i === pages || Math.abs(i - page) <= 1);
  return (
    <nav className="pager" aria-label="Pagination">
      <span>Showing {total ? (page - 1) * size + 1 : 0}–{Math.min(total, page * size)} of {total.toLocaleString('en-IN')}</span>
      <div className="pg">
        <button disabled={page <= 1} onClick={() => onPage(page - 1)} aria-label="Previous page">‹</button>
        {nums.map((n, k) => (
          <span key={n} style={{ display: 'contents' }}>
            {k > 0 && n - nums[k - 1] > 1 && <button disabled aria-hidden>…</button>}
            <button className={n === page ? 'on' : ''} aria-current={n === page ? 'page' : undefined} onClick={() => onPage(n)}>{n}</button>
          </span>
        ))}
        <button disabled={page >= pages} onClick={() => onPage(page + 1)} aria-label="Next page">›</button>
      </div>
    </nav>
  );
}
