import { AlertTriangle, BadgeCheck, Landmark, Loader2, RefreshCw, Send, ShieldCheck, ShieldQuestion } from 'lucide-react';
import { useState } from 'react';
import { Link, useLocation, useNavigate, useParams } from 'react-router-dom';
import { post } from '../../api/client';
import type { DocInfo, Fdr, Institution, Release } from '../../api/types';
import { DocumentsPanel, FdrTimeline, FieldEdits, ObservationsPanel } from '../../components/FdrPanels';
import { FiveAnswers, PacketButton, fiveAnswers, type Row } from '../../components/Evidence';
import { LifecycleFlow, type NodeId, type NodeState } from '../../components/Flowchart';
import { TableWrap, type FdrNavState } from '../../components/Tables';
import { Breadcrumbs, ErrorBox, Loading, Modal, PageHead, Panel, SimBadge, Stagger, StatusPill } from '../../components/ui';
import { T } from '../../lib/motion';
import { useT } from '../../lib/prefs';
import { motion } from 'framer-motion';
import { fmtDate, fmtDateTime, inrP } from '../../lib/format';
import { useRole } from '../../lib/hooks';
import { useApi, useStore } from '../../store/Store';

interface Detail {
  fdr: Fdr;
  institution: Institution;
  comparison: { rows: Row[]; simulated: boolean; problems: string[]; confirmation: { evidence_id: string; as_of: string; bank: string; key_id: string; received_at: string } | null;
    invalid_confirmations: { evidence_id: string; key_id: string; received_at: string }[] };
  documents: DocInfo[];
  release: Release | null;
  noc: { noc_id: string; instrument_no: string; state: string } | null;
  portal_history: { at: string; actor: string; type: string }[];
  ledger_events: { at: string; actor: string; type: string; seq: number }[];
}

const CONF: Record<Row['confidence'], { label: string; cls: string; icon: React.ReactNode }> = {
  BANK_CONFIRMED: { label: 'Bank confirmed', cls: 'src bank', icon: <BadgeCheck size={13} aria-hidden /> },
  DECLARED: { label: 'Institution declared', cls: 'src inst', icon: <ShieldQuestion size={13} aria-hidden /> },
  MISMATCH: { label: 'Mismatch', cls: 'src bad', icon: <AlertTriangle size={13} aria-hidden /> },
  UNVERIFIED_SOURCE: { label: 'Unverified source', cls: 'src bad', icon: <AlertTriangle size={13} aria-hidden /> },
};

function flowState(f: Fdr, r: Release | null): Partial<Record<NodeId, NodeState>> {
  const s: Partial<Record<NodeId, NodeState>> = { submit: 'done', docs: 'done' };
  if (f.status === 'pending') return { ...s, docs: 'current' };
  if (f.status === 'discrepancy') return { ...s, bank: 'done', disc: 'alert' };
  Object.assign(s, { bank: 'done', active: 'done' });
  if (f.status === 'released' || f.status === 'closed') return { ...s, monitor: 'done', decide: 'done', request: 'done', scrutiny: 'done', authority: 'done', released: 'done' };
  if (r && r.stage !== 'REJECTED' && r.stage !== 'COMPLETED') {
    Object.assign(s, { monitor: 'done', decide: 'done', request: 'done' });
    if (r.stage === 'SUBMITTED') s.scrutiny = 'current';
    if (r.stage === 'SCRUTINY_DONE') Object.assign(s, { scrutiny: 'done', authority: 'current' });
    if (r.stage === 'APPROVED') Object.assign(s, { scrutiny: 'done', authority: 'done', released: 'current' });
    return s;
  }
  if (f.renewed_by) return { ...s, monitor: 'done', decide: 'done', renew: 'done' };
  return { ...s, monitor: 'current', ...(f.days_left <= 90 ? { decide: 'current' as const } : {}) };
}

const show = (field: string, v: string | number | null) => (v === null ? '—' : field === 'amount' ? inrP(Number(v)) : field === 'maturity_date' ? fmtDate(String(v)) : String(v));

export default function FdrDetail() {
  const { id } = useParams();
  const { role, base } = useRole();
  const { user, run } = useStore();
  const nav = useNavigate();
  const t = useT();
  const pre = (useLocation().state as FdrNavState | null)?.fdr;
  const d = useApi<Detail>(`/fdrs/${id}`, [id]);
  const [busy, setBusy] = useState(false);
  const [modal, setModal] = useState<'verify' | 'flag' | 'release' | null>(null);
  const [note, setNote] = useState('');

  const listCrumb = { label: role === 'institution' ? 'My FDRs / Deposits' : 'FDR Records', to: role === 'aicte' ? `${base}/submissions` : `${base}/fdrs` };
  if (!d.data) {
    if (d.error) return <ErrorBox text={d.error} />;
    // While the record loads, the reference and status the row passed along are already in the header, so they can
    // travel there from the table (shared-element transition).
    return (
      <div>
        {pre && (
          <div className="page-head">
            <div>
              <Breadcrumbs crumbs={[{ label: 'Dashboard', to: base }, listCrumb, { label: pre.id }]} />
              <h1><motion.span layoutId={`fdr-ref-${pre.id}`} transition={T.route} className="ref-id">{pre.id}</motion.span></h1>
            </div>
            <div className="actions"><StatusPill status={pre.bucket} layoutId={`fdr-pill-${pre.id}`} /></div>
          </div>
        )}
        <Loading layout="detail" />
      </div>
    );
  }
  const { fdr: f, institution: inst, comparison: cmp, documents, release, portal_history, ledger_events } = d.data;
  const isOfficial = role === 'aicte';
  const open = release && ['SUBMITTED', 'SCRUTINY_DONE', 'APPROVED'].includes(release.stage);

  const bankCheck = async () => {
    setBusy(true);
    await run(() => post(`/fdrs/${f.id}/bank-confirmation`), 'Issuing bank (simulated) replied');
    setBusy(false);
  };

  return (
    <Stagger>
      <PageHead title={f.id} titleNode={<motion.span layoutId={`fdr-ref-${f.id}`} transition={T.route} className="ref-id">{f.id}</motion.span>} sub={`${inst.name} · ${inst.city}, ${inst.state}`}
        crumbs={[{ label: 'Dashboard', to: base }, listCrumb, { label: f.id }]}
        actions={
          <>
            <StatusPill status={f.bucket} layoutId={`fdr-pill-${f.id}`} />
            <PacketButton f={f} inst={inst} rows={cmp.rows} confirmation={cmp.confirmation} release={release} show={show} />
            {isOfficial && (f.status === 'pending' || f.status === 'discrepancy') && (
              <>
                <button className="btn btn-ghost" onClick={bankCheck} disabled={busy}>{busy ? <Loader2 size={17} className="spin" aria-hidden /> : <Landmark size={17} aria-hidden />} {busy ? 'Asking the bank…' : t('Request Bank Confirmation')}</button>
                <button className="btn btn-red" onClick={() => setModal('flag')}><AlertTriangle size={17} aria-hidden /> {t('Flag Discrepancy')}</button>
                <button className="btn btn-green" onClick={() => setModal('verify')} disabled={!cmp.confirmation}
                  title={cmp.confirmation ? undefined : 'Needs a valid bank confirmation first'}><ShieldCheck size={17} aria-hidden /> {t('Mark Verified')}</button>
              </>
            )}
            {role === 'institution' && f.status === 'verified' && !open && (
              <>
                {f.days_left <= 120 && !f.renewed_by && <button className="btn btn-ghost" onClick={() => nav(`${base}/upload?renewal=${f.id}`)}><RefreshCw size={17} aria-hidden /> {t('Submit Renewal')}</button>}
                <button className="btn btn-primary" onClick={() => setModal('release')}><Send size={17} aria-hidden /> {t('Request Release')}</button>
              </>
            )}
            {role === 'institution' && f.status === 'discrepancy' && <button className="btn btn-primary" onClick={() => nav(`${base}/upload?renewal=${f.id}`)}><RefreshCw size={17} aria-hidden /> Upload Corrected FDR</button>}
          </>
        }
      />

      {f.status === 'discrepancy' && (
        <div className="alert a-red" style={{ marginBottom: 12 }} role="status">
          <span className="ai" aria-hidden><AlertTriangle size={18} /></span>
          <span><b>Discrepancy: {f.discrepancy_reason}</b><span>{role === 'institution' ? 'Please upload a corrected FDR or a bank letter.' : 'Clarification has been requested from the institution.'}</span></span>
        </div>
      )}

      <Panel title="Lifecycle" sub="Where this instrument stands in the AICTE deposit workflow">
        <LifecycleFlow id={`fdr.${f.id}`} state={flowState(f, release)} />
      </Panel>

      <Panel title="Five answers" sub="Kept separate on purpose: one does not imply another. Select “i” for what each means." style={{ marginTop: 12 }}>
        <FiveAnswers answers={fiveAnswers(f, release, cmp.confirmation)} />
      </Panel>

      <div className="row g-side" style={{ marginTop: 12 }}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          <Panel title={<>{t('Declared vs bank-confirmed')} <SimBadge /></>} sub="Each field shows its source. Only a valid signature from the issuing bank counts as confirmation.">
            <TableWrap label={`Declared vs bank-confirmed, ${f.id}`} simulated>
              <table className="tbl roomy cardable">
                <caption className="sr-only">Comparison of declared and bank-confirmed values</caption>
                <thead><tr><th scope="col">{t('Field')}</th><th scope="col">{t('Institution declared')}</th><th scope="col">{t('Bank confirmed')} <SimBadge /></th><th scope="col">{t('Confidence')}</th></tr></thead>
                <tbody>
                  {cmp.rows.map((r) => (
                    <tr key={r.field}>
                      <td data-label={t('Field')}>{r.label}</td>
                      <td data-label={t('Institution declared')}>{show(r.field, r.declared)}</td>
                      <td data-label={t('Bank confirmed')} className={r.confidence === 'MISMATCH' ? 'mismatch' : undefined}>{show(r.field, r.bank_confirmed)}</td>
                      <td data-label={t('Confidence')}><span className={CONF[r.confidence].cls} style={{ margin: 0 }}>{CONF[r.confidence].icon} {t(CONF[r.confidence].label)}</span></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </TableWrap>
            <p className="hint" style={{ marginTop: 12 }}>
              {cmp.confirmation
                ? <>Relied on {cmp.confirmation.evidence_id}, signed by {cmp.confirmation.key_id}, received {fmtDateTime(cmp.confirmation.received_at)} (bank position as of {fmtDate(cmp.confirmation.as_of)}).</>
                : 'No valid confirmation from the issuing bank yet: every value is as declared by the institution.'}
              {cmp.invalid_confirmations.length > 0 && <> {cmp.invalid_confirmations.length} earlier confirmation(s) no longer count: their signing key was compromised or had ended.</>}
            </p>
          </Panel>

          {release && (
            <Panel title={`Release request ${release.id}`} sub={release.reason} action={<Link className="view-all" to={`${base}/${role === 'institution' ? 'release' : 'releases'}`}>Open</Link>}>
              <p style={{ fontSize: 13.5 }}>Stage: <b>{release.stage.replace('_', ' ')}</b>{release.case_id && <> · {release.case_id}</>}</p>
            </Panel>
          )}

          <DocumentsPanel fid={f.id} docs={documents} />
          <ObservationsPanel fid={f.id} role={role} />
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          <Panel title="Summary">
            <dl className="kv">
              <dt>Institution</dt><dd>{role === 'institution' ? inst.name : <Link className="link" to={`${base}/institutions/${inst.id}`}>{inst.name}</Link>}</dd>
              <dt>AICTE ID</dt><dd>{inst.aicte_id}</dd>
              <dt>Bank</dt><dd>{f.bank_name}, {f.branch}</dd>
              <dt>FDR number</dt><dd>{f.instrument_no}</dd>
              <dt>Amount</dt><dd>{inrP(f.amount_paise)}</dd>
              <dt>Interest</dt><dd>{(f.rate_bp / 100).toFixed(2)}% p.a.</dd>
              <dt>Submitted</dt><dd>{fmtDateTime(f.submitted_on)}</dd>
              <dt>Days to maturity</dt><dd>{['released', 'closed'].includes(f.status) ? '—' : f.days_left < 0 ? `Matured ${-f.days_left} days ago` : `${f.days_left} days`}</dd>
              {f.renewal_of && <><dt>Replaces</dt><dd><Link className="link" to={`${base}/fdr/${f.renewal_of}`}>{f.renewal_of}</Link></dd></>}
              {f.renewed_by && <><dt>Renewed by</dt><dd><Link className="link" to={`${base}/fdr/${f.renewed_by}`}>{f.renewed_by}</Link></dd></>}
            </dl>
          </Panel>
          <FieldEdits f={f} />
          <FdrTimeline fid={f.id} />
          <Panel title="Audit events" sub="Ledger and portal events for this FDR (hash-chained)">
            <ol className="timeline" style={{ listStyle: 'none', margin: 0 }}>
              {[...ledger_events.map((e) => ({ ...e, chain: 'ledger' })), ...portal_history.map((e) => ({ ...e, chain: 'portal', seq: 0 }))]
                .sort((a, b) => b.at.localeCompare(a.at)).slice(0, 14).map((h, i) => (
                  <li key={i} className={`tl-item ${/reject|discrep|mismatch/i.test(h.type) ? 'r' : /evidence_recorded|verified|noc|discharge/i.test(h.type) ? 'g' : 'o'}`}>
                    <b>{h.type.replace(/_/g, ' ')}</b>
                    <time style={{ display: 'block' }}>{h.actor} · {fmtDateTime(h.at)}{h.chain === 'ledger' ? ` · ledger #${h.seq}` : ''}</time>
                  </li>
                ))}
            </ol>
          </Panel>
        </div>
      </div>

      <Modal open={modal === 'verify'} onClose={() => setModal(null)} title="Mark FDR as verified" sub={`${f.id} · ${inst.name}`}
        footer={<><button className="btn btn-ghost" onClick={() => setModal(null)}>Cancel</button>
          <button className="btn btn-green" onClick={async () => { if (await run(() => post(`/fdrs/${f.id}/verify`, { note: note || null }), `${f.id} verified`) !== undefined) { setModal(null); setNote(''); } }}><ShieldCheck size={17} aria-hidden /> Confirm verification</button></>}>
        <label className="lb" htmlFor="vnote">Scrutiny remarks {user?.full_name ? `(${user.full_name})` : ''}</label>
        <textarea id="vnote" className="inp" value={note} onChange={(e) => setNote(e.target.value)} placeholder="e.g. Original FDR verified; lien marked in favour of AICTE" />
        <p className="hint">The server refuses verification unless the issuing bank's valid confirmation matches the declared instrument.</p>
      </Modal>

      <Modal open={modal === 'flag'} onClose={() => setModal(null)} title="Flag discrepancy" sub="The institution will be notified and asked for clarification"
        footer={<><button className="btn btn-ghost" onClick={() => setModal(null)}>Cancel</button>
          <button className="btn btn-red" disabled={note.trim().length < 3} onClick={async () => { if (await run(() => post(`/fdrs/${f.id}/discrepancy`, { reason: note }), 'Discrepancy recorded') !== undefined) { setModal(null); setNote(''); } }}>Flag &amp; notify</button></>}>
        <label className="lb" htmlFor="fnote">Reason <em>*</em></label>
        <textarea id="fnote" className="inp" value={note} onChange={(e) => setNote(e.target.value)} placeholder="e.g. Bank covering letter missing signature" />
      </Modal>

      <Modal open={modal === 'release'} onClose={() => setModal(null)} title="Request release / refund" sub={`${f.id} · ${inrP(f.amount_paise)}`}
        footer={<><button className="btn btn-ghost" onClick={() => setModal(null)}>Cancel</button>
          <button className="btn btn-primary" disabled={note.trim().length < 5} onClick={async () => { if (await run(() => post('/release-requests', { fdr_id: f.id, reason: note }), 'Release request submitted') !== undefined) { setModal(null); setNote(''); } }}><Send size={16} aria-hidden /> Submit request</button></>}>
        <label className="lb" htmlFor="rnote">Reason for release <em>*</em></label>
        <textarea id="rnote" className="inp" value={note} onChange={(e) => setNote(e.target.value)} placeholder="e.g. Renewed FDR submitted and verified" />
        <p className="hint">Release needs entitlement, Affidavit-6, a fresh bank confirmation and competent-authority approval. Completion is only on the bank's lien-discharge confirmation.</p>
      </Modal>
    </Stagger>
  );
}
