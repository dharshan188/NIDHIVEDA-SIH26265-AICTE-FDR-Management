import { ArrowRight, Banknote, CheckCircle2, CircleDashed, RotateCcw, Send, Undo2 } from 'lucide-react';
import { useState } from 'react';
import { post } from '../../api/client';
import type { Payment } from '../../api/types';
import { Empty, ErrorBox, Kpi, Loading, PageHead, Panel, SimBadge, Stagger, StatusPill, Tabs } from '../../components/ui';
import { fmtDateTime, inrP, rupeeText } from '../../lib/format';
import { TableWrap } from '../../components/Tables';
import { useRole } from '../../lib/hooks';
import { useApi, useStore } from '../../store/Store';

const DEV = import.meta.env.DEV;

/** One label per payment state. Debit + UTR is "sent", never "complete". */
export function paymentLabel(p: Payment): { text: string; pill: 'pending' | 'active' | 'discrepancy' | 'closed' | 'released' } {
  switch (p.state) {
    case 'AUTHORISED': return { text: 'Sanctioned, not yet sent', pill: 'closed' };
    case 'INITIATED': return { text: 'Instruction with bank, not yet sent', pill: 'pending' };
    case 'DEBITED': return { text: 'Sent, not complete', pill: 'pending' };
    case 'SETTLED': return { text: 'Settled', pill: 'active' };
    case 'REISSUE_REQUIRED': return { text: 'Returned: re-issue required', pill: 'discrepancy' };
    default: return { text: p.state, pill: 'closed' };
  }
}

const RETURN_REASONS = ['BENEFICIARY_BANK_REJECT', 'ACCOUNT_CLOSED', 'NAME_MISMATCH', 'INVALID_IFSC'];

function PaymentCard({ p }: { p: Payment }) {
  const { user, run } = useStore();
  const [reason, setReason] = useState(RETURN_REASONS[0]);
  const lab = paymentLabel(p);
  const finance = user?.kernel_role === 'finance_officer';
  const operator = DEV && user?.role !== 'INSTITUTION';
  const last = p.attempts[p.attempts.length - 1];
  return (
    <article className="card panel" aria-labelledby={`p-${p.refund_id}`}>
      <div className="panel-head" style={{ alignItems: 'flex-start' }}>
        <div>
          <h3 id={`p-${p.refund_id}`}>{p.refund_id} · {inrP(p.amount_paise)} <span className="muted" style={{ fontWeight: 400, fontSize: 14 }}>via {p.rail}</span></h3>
          <p>{p.institution_name ?? p.institution_id} · approved by {p.approver}</p>
        </div>
        <StatusPill status={lab.pill} label={lab.text} />
      </div>
      <p className={`pay-status pay-${p.state.toLowerCase()}`} role="status">{rupeeText(p.status_text)}</p>

      <div className="pay-flow" aria-label="Payment lifecycle">
        {['AUTHORISED', 'INITIATED', 'DEBITED', 'SETTLED'].map((s, i, arr) => {
          const reached = p.history.some((h) => h.state === s) || (s === 'SETTLED' && p.state === 'SETTLED');
          const now = p.state === s;
          return (
            <span key={s} style={{ display: 'contents' }}>
              <span className={`pf-node${reached ? ' done' : ''}${now ? ' now' : ''}`}>
                {reached ? <CheckCircle2 size={15} aria-hidden /> : <CircleDashed size={15} aria-hidden />}
                {s === 'DEBITED' ? 'Debited (UTR)' : s === 'SETTLED' ? 'Credit confirmed' : s[0] + s.slice(1).toLowerCase()}
              </span>
              {i < arr.length - 1 && <ArrowRight size={14} aria-hidden className="muted" />}
            </span>
          );
        })}
        {p.history.some((h) => h.state.startsWith('RETURNED')) && <span className="pf-node bad"><Undo2 size={15} aria-hidden /> Returned → re-issue</span>}
      </div>

      <TableWrap label="Payment attempts" simulated style={{ marginTop: 12 }}>
        <table className="tbl cardable">
          <caption className="sr-only">Payment attempts</caption>
          <thead><tr><th scope="col">#</th><th scope="col">UTR</th><th scope="col">Debited</th><th scope="col">Outcome</th></tr></thead>
          <tbody>
            {p.attempts.map((a, i) => (
              <tr key={a.utr}>
                <td>{i + 1}</td><td>{a.utr}</td><td>{fmtDateTime(a.debited_at)}</td>
                <td>{a.status === 'SETTLED' ? <StatusPill status="active" label={`Credit confirmed ${fmtDateTime(a.settled_at!)}`} />
                  : a.status === 'RETURNED' ? <StatusPill status="discrepancy" label={`Returned (${a.return_reason})${a.returned_after_settlement ? ' after settlement: investigate' : ''}`} />
                  : <StatusPill status="pending" label="Awaiting credit confirmation" />}</td>
              </tr>
            ))}
            {p.attempts.length === 0 && <tr><td colSpan={4}><div className="empty">No debit yet</div></td></tr>}
          </tbody>
        </table>
      </TableWrap>
      <p className="hint">Liability: outstanding {inrP(p.liability.outstanding_liability)} · in transit {inrP(p.liability.in_transit)} · settled {inrP(p.liability.settled_refunds)}
        {!p.payee_verified && ' · payee must be re-verified (Affidavit-9 + bank name look-up) before re-issue'}</p>

      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', justifyContent: 'flex-end', marginTop: 8 }}>
        {finance && p.state === 'AUTHORISED' && <button className="btn btn-primary btn-sm" onClick={() => run(() => post(`/payments/${p.refund_id}/initiate`), 'Payment initiated')}><Send size={15} aria-hidden /> Initiate payment</button>}
        {finance && p.state === 'REISSUE_REQUIRED' && <button className="btn btn-primary btn-sm" onClick={() => run(() => post(`/payments/${p.refund_id}/reissue`), 'Re-issue initiated')}><RotateCcw size={15} aria-hidden /> Re-issue</button>}
        {!finance && user?.role === 'AICTE_OFFICIAL' && ['AUTHORISED', 'REISSUE_REQUIRED'].includes(p.state) && <span className="hint">Only a Finance Officer (not the approver) can initiate.</span>}
      </div>
      {operator && (
        <div className="sim-panel" aria-label="Bank simulator controls">
          <b>Bank simulator</b> <SimBadge />
          {p.state === 'INITIATED' && <button className="btn btn-ghost btn-sm" onClick={() => run(() => post(`/sim/payments/${p.refund_id}/debit`), 'SBI (simulated) debited the payment')}>Bank debits (issues UTR)</button>}
          {p.state === 'DEBITED' && (
            <>
              <button className="btn btn-ghost btn-sm" onClick={() => run(() => post(`/sim/payments/${p.refund_id}/confirm`), 'Positive credit confirmation received')}>Beneficiary bank confirms credit (N10)</button>
              <label className="sr-only" htmlFor={`rr-${p.refund_id}`}>Return reason</label>
              <select id={`rr-${p.refund_id}`} className="sel" value={reason} onChange={(e) => setReason(e.target.value)}>{RETURN_REASONS.map((r) => <option key={r}>{r}</option>)}</select>
              <button className="btn btn-red btn-sm" onClick={() => run(() => post(`/sim/payments/${p.refund_id}/return`, { reason_code: reason }), 'Return advice received')}>Bank returns payment</button>
            </>
          )}
          {p.state === 'SETTLED' && last && <button className="btn btn-red btn-sm" onClick={() => run(() => post(`/sim/payments/${p.refund_id}/return`, { reason_code: 'ACCOUNT_CLOSED' }), 'Late return received')}>Late return after settlement</button>}
          {!['INITIATED', 'DEBITED', 'SETTLED'].includes(p.state) && <span className="hint">Nothing for the bank to do in this state.</span>}
        </div>
      )}
    </article>
  );
}

export default function Payments() {
  const { role, base } = useRole();
  const [tab, setTab] = useState<'open' | 'all'>('open');
  const d = useApi<{ items: Payment[] }>('/payments');
  if (!d.data) return d.error ? <ErrorBox text={d.error} /> : <Loading rows={8} />;
  const items = d.data.items.filter((p) => tab === 'all' || p.state !== 'SETTLED');
  const n = (s: string) => d.data!.items.filter((p) => p.state === s).length;
  return (
    <Stagger>
      <PageHead title={role === 'institution' ? 'Refund Payments' : 'Payments'} sub="A payment is complete only when the beneficiary bank positively confirms the credit"
        crumbs={[{ label: 'Dashboard', to: base }, { label: 'Payments' }]} actions={<SimBadge title="Debit advices, confirmations and returns come from the bank simulator" />} />
      <div className="kpis k4">
        <Kpi tone="orange" icon={<Send size={32} />} label="Sent, not complete" value={String(n('DEBITED') + n('INITIATED'))} sub="awaiting credit confirmation" />
        <Kpi tone="red" icon={<Undo2 size={32} />} label="Returned" value={String(n('REISSUE_REQUIRED'))} sub="liability reopened" />
        <Kpi tone="blue" icon={<Banknote size={32} />} label="Sanctioned" value={String(n('AUTHORISED'))} sub="not yet sent" />
        <Kpi tone="green" icon={<CheckCircle2 size={32} />} label="Settled" value={String(n('SETTLED'))} sub="credit confirmed" />
      </div>
      <Tabs id="pay" value={tab} onChange={setTab} tabs={[{ key: 'open', label: 'Needs attention' }, { key: 'all', label: `All (${d.data.items.length})` }]} />
      <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
        {items.map((p) => <PaymentCard key={p.refund_id} p={p} />)}
        {items.length === 0 && <Panel><Empty text="No payments here" /></Panel>}
      </div>
    </Stagger>
  );
}
