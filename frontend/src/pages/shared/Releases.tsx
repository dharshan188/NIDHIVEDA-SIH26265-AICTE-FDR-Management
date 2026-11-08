import { Check, ChevronDown, FileSignature, Landmark, Send, ShieldAlert, X } from 'lucide-react';
import { useState } from 'react';
import { Link } from 'react-router-dom';
import { post } from '../../api/client';
import type { Fdr, Release } from '../../api/types';
import { ReleaseStepper } from '../../components/Flowchart';
import { Empty, ErrorBox, Loading, Modal, PageHead, Panel, SimBadge, Stagger, StatusPill, Tabs } from '../../components/ui';
import { fmtDate, inrP, rupeeText } from '../../lib/format';
import { useRole } from '../../lib/hooks';
import { useApi, useStore } from '../../store/Store';

const STAGE: Record<Release['stage'], { label: string; step: string; pill: 'pending' | 'active' | 'released' | 'discrepancy' }> = {
  SUBMITTED: { label: 'Submitted', step: 'submitted', pill: 'pending' },
  SCRUTINY_DONE: { label: 'Scrutiny done', step: 'authority', pill: 'pending' },
  APPROVED: { label: 'Approved, awaiting bank', step: 'approved', pill: 'active' },
  COMPLETED: { label: 'Completed', step: 'released', pill: 'released' },
  REJECTED: { label: 'Rejected', step: 'rejected', pill: 'discrepancy' },
};

function RequestCard({ r }: { r: Release }) {
  const { user, run, toast } = useStore();
  const { base, role } = useRole();
  const [open, setOpen] = useState(false);
  const [modal, setModal] = useState<'scrutiny' | 'reject' | null>(null);
  const [text, setText] = useState('');
  const detail = useApi<Release>(open ? `/release-requests/${r.id}` : null, [open]);
  const official = user?.role === 'AICTE_OFFICIAL';
  const gate = detail.data?.gate;

  const approve = async () => {
    if (!gate || !user) return;
    if (!import.meta.env.DEV) {
      toast('Approval needs your DSC token and the signer utility. That integration is planned and not built in this version.', 'info');
      return;
    }
    await run(async () => {
      // Dev build only: the SIMULATED DSC issuer signs the gate decision the approver is looking at.
      const sig = await post<{ certificate_pem: string; signature_b64: string }>(import.meta.env.DEV ? '/sim/dsc/sign' : '', { username: user.username, message: gate.approval_message });
      return post(`/release-requests/${r.id}/approve`, sig);
    }, `${r.id} approved with DSC (release approved)`);
  };

  return (
    <div className="card" style={{ padding: '14px 16px' }}>
      <button style={{ display: 'flex', alignItems: 'center', gap: 14, width: '100%', border: 0, background: 'none', textAlign: 'left', flexWrap: 'wrap', padding: 0 }}
        aria-expanded={open} onClick={() => setOpen(!open)}>
        <span style={{ flex: 1, minWidth: 220 }}>
          <b style={{ color: 'var(--navy)', fontSize: 14.5 }}>{r.id}</b> <span className="muted" style={{ fontSize: 13 }}>· raised {fmtDate(r.raised_on)}</span>
          <span style={{ display: 'block', fontSize: 13.5, marginTop: 3 }}>{r.institution_name} · {r.fdr_id ?? r.obligation_id}</span>
        </span>
        {r.amount_paise !== null && <b className="num" style={{ color: 'var(--navy)' }}>{inrP(r.amount_paise)}</b>}
        <StatusPill status={STAGE[r.stage].pill} label={STAGE[r.stage].label} />
        <ChevronDown size={18} aria-hidden style={{ transform: open ? 'rotate(180deg)' : undefined }} />
      </button>
      {open && (
        <div style={{ paddingTop: 14 }}>
          <ReleaseStepper stage={STAGE[r.stage].step} />
          <p style={{ fontSize: 13.5, marginTop: 12 }}><b>Reason:</b> {r.reason}{r.remarks && <> · <b>Remarks:</b> {r.remarks}</>}</p>
          <p style={{ fontSize: 13, color: 'var(--muted)' }}>Scrutiny by {r.scrutiny_by ?? '—'} · Approved by {r.approved_by ?? '—'}{r.dsc_serial && ` · DSC ${r.dsc_serial.slice(0, 10)}…`}</p>
          {detail.data?.refund && <p style={{ fontSize: 13.5 }}>Payment: <Link className="link" to={`${base}/payments`}>{rupeeText(detail.data.refund.status_text)}</Link></p>}
          {gate && official && (
            <div style={{ marginTop: 10 }}>
              <h4 style={{ fontSize: 14, margin: '6px 0' }}>Release gate for you ({user?.designation}) {gate.allowed ? <StatusPill status="active" label="All checks pass" /> : <StatusPill status="discrepancy" label={`Blocked: ${gate.blocked_by.join(', ')}`} />}</h4>
              <ul style={{ listStyle: 'none', padding: 0, margin: 0, display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 6 }}>
                {gate.checks.map((c) => (
                  <li key={c.code} style={{ fontSize: 13, display: 'flex', gap: 8, padding: '7px 10px', borderRadius: 6, background: c.ok ? 'var(--c-bg-f1faf5)' : 'var(--c-bg-fdf1f1)' }}>
                    {c.ok ? <Check size={15} color="var(--green-ink)" aria-hidden /> : <X size={15} color="var(--red-ink)" aria-hidden />}
                    <span><b>{c.code}</b>{c.mandatory ? '' : ' (administrative)'}: {c.detail}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
          {official && (
            <div style={{ display: 'flex', gap: 10, justifyContent: 'flex-end', marginTop: 12, flexWrap: 'wrap' }}>
              {['SUBMITTED', 'SCRUTINY_DONE'].includes(r.stage) && <button className="btn btn-red btn-sm" onClick={() => setModal('reject')}><X size={15} aria-hidden /> Reject</button>}
              {r.stage === 'SUBMITTED' && user?.kernel_role === 'section_officer' && <button className="btn btn-primary btn-sm" onClick={() => setModal('scrutiny')}>Record scrutiny</button>}
              {r.stage === 'SUBMITTED' && user?.kernel_role !== 'section_officer' && <span className="hint">Scrutiny is done by a Section Officer (maker).</span>}
              {r.stage === 'SCRUTINY_DONE' && ['deputy_director', 'director'].includes(user?.kernel_role ?? '') && (
                <button className="btn btn-green btn-sm" onClick={approve} disabled={!gate?.allowed}><FileSignature size={15} aria-hidden /> Approve with DSC</button>
              )}
              {r.stage === 'APPROVED' && r.fdr_id && (
                <button className="btn btn-ghost btn-sm" onClick={() => run(() => post(`/release-requests/${r.id}/lien-discharge`), 'Bank confirmed lien discharge')}>
                  <Landmark size={15} aria-hidden /> Ask bank to discharge lien <SimBadge />
                </button>
              )}
            </div>
          )}
          {role === 'institution' && r.stage === 'APPROVED' && <p className="hint">Approved. Not complete until {r.fdr_id ? 'your bank confirms the lien is discharged' : 'your bank confirms the credit'}.</p>}
        </div>
      )}
      <Modal open={modal === 'scrutiny'} onClose={() => setModal(null)} title={`Scrutiny for ${r.id}`} sub="Records entitlement and Affidavit-6 in the ledger. You cannot then approve this request (maker-checker)."
        footer={<><button className="btn btn-ghost" onClick={() => setModal(null)}>Cancel</button>
          <button className="btn btn-primary" disabled={text.trim().length < 5} onClick={async () => { if (await run(() => post(`/release-requests/${r.id}/scrutiny`, { entitlement_basis: text, affidavit6_format_ok: true }), 'Scrutiny recorded') !== undefined) setModal(null); }}>Record</button></>}>
        <label className="lb" htmlFor="ent">Entitlement basis <em>*</em></label>
        <textarea id="ent" className="inp" value={text} onChange={(e) => setText(e.target.value)} placeholder="e.g. Programme closure approved (EoA 2026-27); deposit refundable" />
      </Modal>
      <Modal open={modal === 'reject'} onClose={() => setModal(null)} title={`Reject ${r.id}`} sub="The institution will be notified with your remarks"
        footer={<><button className="btn btn-ghost" onClick={() => setModal(null)}>Cancel</button>
          <button className="btn btn-red" disabled={text.trim().length < 5} onClick={async () => { if (await run(() => post(`/release-requests/${r.id}/reject`, { remarks: text }), 'Request rejected') !== undefined) setModal(null); }}>Reject request</button></>}>
        <label className="lb" htmlFor="rej">Remarks <em>*</em></label>
        <textarea id="rej" className="inp" value={text} onChange={(e) => setText(e.target.value)} />
      </Modal>
    </div>
  );
}

export default function Releases() {
  const { role, base } = useRole();
  const { run, user } = useStore();
  const [tab, setTab] = useState<'open' | 'closed'>('open');
  const d = useApi<{ total: number; by_stage: Record<string, number>; items: Release[] }>(`/release-requests?stage=${tab === 'open' ? 'open' : ''}&size=100`, [tab]);
  const mine = role === 'institution';
  const eligible = useApi<{ items: Fdr[] }>(mine ? '/fdrs?size=200' : null);
  const online = useApi<{ items: { obligation_id: string; programme: string; required_paise: number; refunds: string[] }[] }>(mine ? '/obligations' : null);
  const [kind, setKind] = useState<'fdr' | 'online'>('fdr');
  const [fdrId, setFdrId] = useState('');
  const [reason, setReason] = useState('');
  const items = (d.data?.items ?? []).filter((r) => (tab === 'open' ? !['COMPLETED', 'REJECTED'].includes(r.stage) : ['COMPLETED', 'REJECTED'].includes(r.stage)));
  const title = mine ? 'Release / Refund Request' : 'Release / Refund';
  const by = d.data?.by_stage ?? {};

  return (
    <Stagger>
      <PageHead title={title} sub="Release needs entitlement, Affidavit-6, current bank evidence and competent-authority approval (maker-checker)" crumbs={[{ label: 'Dashboard', to: base }, { label: title }]} />
      {!mine && (
        <p className="hint" style={{ margin: '-6px 0 12px' }}>
          {Object.entries(by).map(([k, v]) => `${STAGE[k as Release['stage']]?.label ?? k}: ${v}`).join(' · ')}
          {user?.kernel_role && <> · You are signed in as <b>{user.designation}</b>.</>}
        </p>
      )}
      <div className={mine ? 'row g-side' : ''}>
        <Panel>
          <Tabs id="rel" value={tab} onChange={setTab} tabs={[{ key: 'open', label: 'In process' }, { key: 'closed', label: 'Completed / rejected' }]} />
          {d.error ? <ErrorBox text={d.error} /> : !d.data ? <Loading /> : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
              {items.slice(0, 40).map((r) => <RequestCard key={r.id} r={r} />)}
              {items.length === 0 && <Empty text="No release requests here" />}
            </div>
          )}
        </Panel>
        {mine && (
          <Panel title="Raise a new request" sub="Only verified FDRs are eligible">
            <Tabs id="relkind" value={kind} onChange={(k) => { setKind(k); setFdrId(''); }} tabs={[{ key: 'fdr', label: 'FDR (lien)' }, { key: 'online', label: 'Online deposit (RTGS)' }]} />
            <label className="lb" htmlFor="rf">{kind === 'fdr' ? 'FDR' : 'Online deposit'} <em>*</em></label>
            <select id="rf" className="inp" value={fdrId} onChange={(e) => setFdrId(e.target.value)}>
              <option value="">Select</option>
              {kind === 'fdr'
                ? (eligible.data?.items ?? []).filter((f) => f.status === 'verified').map((f) => <option key={f.id} value={f.id}>{f.id} · {f.bank_name} · {inrP(f.amount_paise)}</option>)
                : (online.data?.items ?? []).filter((o) => o.refunds.length === 0).map((o) => <option key={o.obligation_id} value={o.obligation_id}>{o.obligation_id} · {o.programme} · {inrP(o.required_paise)}</option>)}
            </select>
            <label className="lb" htmlFor="rr" style={{ marginTop: 14 }}>Reason <em>*</em></label>
            <textarea id="rr" className="inp" value={reason} onChange={(e) => setReason(e.target.value)} placeholder="e.g. Closure of programme approved; renewed FDR verified" />
            <button className="btn btn-primary" style={{ width: '100%', marginTop: 14 }} disabled={!fdrId || reason.trim().length < 5}
              onClick={async () => { if (await run(() => post('/release-requests', kind === 'fdr' ? { fdr_id: fdrId, reason } : { obligation_id: fdrId, reason }), 'Release request submitted') !== undefined) { setFdrId(''); setReason(''); } }}>
              <Send size={16} aria-hidden /> Submit request
            </button>
            <p className="hint"><ShieldAlert size={12} aria-hidden /> A request does not release anything by itself.</p>
          </Panel>
        )}
      </div>
    </Stagger>
  );
}

