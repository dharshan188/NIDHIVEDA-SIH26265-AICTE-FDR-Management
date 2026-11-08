import { AlertTriangle, CheckCircle2, Download, FileCheck2, FileText, Loader2, Lock, MessageSquarePlus, Pencil, ShieldAlert, ShieldCheck, XCircle } from 'lucide-react';
import { useState } from 'react';
import { api, errorText, post } from '../api/client';
import type { ContentCheck, DocInfo, Fdr, Timeline } from '../api/types';
import { fmtDate, fmtDateTime, inrP } from '../lib/format';
import { useApi, useStore } from '../store/Store';
import { Empty, ErrorBox, Loading, Modal, Panel, SimBadge } from './ui';

// ---------------------------------------------------------------- history timeline
const TONE: Record<string, string> = { issued: 'b', submitted: 'b', bank_confirmation: 'g', verified: 'g', renewed: 'g', renumbered: 'o', matured: 'o',
  matures: 'b', released: 'g', closed: 'b', discrepancy: 'r' };

/** Issued → submitted → confirmed → verified → renewed / renumbered → matured → released, each with the rule editions in
 * force on that date and how the relevant rule resolves then; any renewal gap is flagged above the list. */
export function FdrTimeline({ fid }: { fid: string }) {
  const d = useApi<Timeline>(`/fdrs/${fid}/timeline`, [fid]);
  return (
    <Panel title="History timeline" sub="Each date shows the APH editions in force then and how the rule for that step resolves">
      {d.error ? <ErrorBox text={d.error} /> : !d.data ? <Loading rows={5} /> : (
        <>
          {d.data.gaps.map((g) => (
            <div key={g.kind} className="alert a-red" role="status" style={{ marginBottom: 10 }}>
              <span className="ai" aria-hidden><AlertTriangle size={18} /></span>
              <span><b>Renewal gap</b><span>{g.label} (since {fmtDate(g.since)})</span></span>
            </div>
          ))}
          {d.data.gaps.length === 0 && <p className="ack-ok" style={{ marginBottom: 10 }}><CheckCircle2 size={15} aria-hidden /> No renewal gap</p>}
          <ol className="timeline" style={{ listStyle: 'none', margin: 0 }}>
            {d.data.events.map((e, i) => (
              <li key={`${e.kind}-${e.at}-${i}`} className={`tl-item ${TONE[e.kind] ?? 'b'}${e.future ? ' future' : ''}`}>
                <b>{e.label}</b>
                <time dateTime={e.at} style={{ display: 'block' }}>{fmtDate(e.date)} · {e.source.includes('SIMULATED') ? <>{e.source.replace(' (SIMULATED)', '')} <SimBadge /></> : e.source}</time>
                <p>
                  In force: {e.editions_in_force.length ? e.editions_in_force.join(', ') : e.future ? 'no APH edition published for this date yet' : <b className="bad-ink">no edition covers this date (escalated, never guessed)</b>}
                  {e.rule && <> · <code>{e.rule.key}</code> = <b>{JSON.stringify(e.rule.value)}</b> ({e.rule.status.toLowerCase()}){e.rule.cites.length > 0 && <>, {e.rule.cites.join('; ')}</>}</>}
                </p>
              </li>
            ))}
          </ol>
          {d.data.reminders.length > 0 && (
            <p className="muted small">Maturity reminders sent: {d.data.reminders.map((r) => `${r.window} (${fmtDate(r.at)}${r.ack_at ? ', acknowledged' : ''})`).join(' · ')}</p>
          )}
        </>
      )}
    </Panel>
  );
}

// ---------------------------------------------------------------- documents
export function CheckList({ checks }: { checks: ContentCheck[] }) {
  return (
    <ul className="checks" aria-label="Content checks">
      {checks.map((c) => (
        <li key={c.code} className={c.ok ? 'ok' : c.ok === false ? 'bad' : 'skip'}>
          {c.ok ? <CheckCircle2 size={14} aria-hidden /> : c.ok === false ? <XCircle size={14} aria-hidden /> : <span aria-hidden>–</span>}
          <span>{c.label}{c.ok === false && c.detail ? `: ${c.detail}` : c.ok === null ? ' (not run)' : ''}</span>
          <span className="sr-only">{c.ok ? 'passed' : c.ok === false ? 'failed' : 'not run'}</span>
        </li>
      ))}
    </ul>
  );
}

export function ScanChip({ scan }: { scan: { status: string; engine: string | null } }) {
  const ok = scan.status === 'clean';
  return (
    <span className={`dchip ${ok ? 'd-delivered' : scan.status === 'infected' ? 'd-failed' : 'd-deferred'}`}>
      {ok ? <ShieldCheck size={13} aria-hidden /> : <ShieldAlert size={13} aria-hidden />} Malware scan: {scan.status.replace('_', ' ')}{scan.engine ? ` (${scan.engine})` : ''}
    </span>
  );
}

export function EncChip({ enc }: { enc: DocInfo['encryption'] }) {
  return enc
    ? <span className="dchip d-delivered"><Lock size={13} aria-hidden /> Encrypted {enc.alg} · key {enc.kek_id} · {enc.store === 's3' ? 'object store (ciphertext only)' : 'server disk (ciphertext only)'}</span>
    : <span className="dchip d-deferred"><Lock size={13} aria-hidden /> No file stored (seed record)</span>;
}

/** Each document: type, scan result, encryption, the content checks it passed, and an on-demand SHA-256 re-check. */
export function DocumentsPanel({ fid, docs }: { fid: string; docs: DocInfo[] }) {
  const { run } = useStore();
  const [busy, setBusy] = useState<number | null>(null);
  const [res, setRes] = useState<Record<number, { result: string; actual: string | null; checked_at: string }>>({});
  const verify = async (id: number) => {
    setBusy(id);
    const r = await run(() => post<{ result: string; actual: string | null; checked_at: string }>(`/fdrs/${fid}/documents/${id}/verify`));
    if (r) setRes((x) => ({ ...x, [id]: r }));
    setBusy(null);
  };
  return (
    <Panel title="Documents" sub={`${docs.length} file(s) · scanned, encrypted at rest, SHA-256 recorded at upload`}>
      {docs.length === 0 && <Empty text="No documents" />}
      <ul className="doc-list">
        {docs.map((x) => {
          const r = res[x.id];
          const integ = r?.result ?? x.integrity.status;
          return (
            <li key={x.id} className="doc-row">
              <div className="file-row" style={{ border: 0, padding: 0 }}>
                <FileText size={20} color="var(--red)" aria-hidden />
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontWeight: 600, color: 'var(--ink)' }}>{x.name} <span className="muted small">· {x.doc_type_label}</span></div>
                  <div className="muted small">{Math.max(1, Math.round(x.size_bytes / 1024))} KB · uploaded {fmtDateTime(x.uploaded_on)}</div>
                </div>
                {x.stored && <a className="btn btn-ghost btn-sm" href={`/api/fdrs/${fid}/documents/${x.id}`} target="_blank" rel="noreferrer"><Download size={15} aria-hidden /> Open</a>}
              </div>
              <div className="ln-chips">
                <ScanChip scan={x.scan} />
                <EncChip enc={x.encryption} />
                {integ && <span className={`dchip ${integ === 'match' ? 'd-delivered' : 'd-failed'}`}><FileCheck2 size={13} aria-hidden /> SHA-256 {integ === 'match' ? 'matches' : integ}{(r?.checked_at ?? x.integrity.at) ? ` · ${fmtDateTime((r?.checked_at ?? x.integrity.at)!)}` : ''}</span>}
              </div>
              <div className="sha"><span className="muted small">SHA-256</span> <code>{x.sha256}</code></div>
              {x.content_checks.length > 0 ? <CheckList checks={x.content_checks} /> : <p className="muted small">Content checks: not recorded (uploaded before checks were stored, or a seed record).</p>}
              {x.stored && (
                <button className="btn btn-ghost btn-sm" onClick={() => verify(x.id)} disabled={busy === x.id} aria-describedby={`sha-${x.id}`}>
                  {busy === x.id ? <Loader2 size={15} className="spin" aria-hidden /> : <FileCheck2 size={15} aria-hidden />} Check SHA-256 now
                </button>
              )}
              <span id={`sha-${x.id}`} className="sr-only">Decrypts the stored copy and compares its SHA-256 with the value recorded at upload</span>
            </li>
          );
        })}
      </ul>
    </Panel>
  );
}

// ---------------------------------------------------------------- observations
interface Obs { id: number; category: string; category_label: string; text: string; status: 'open' | 'answered' | 'closed'; raised_by: string; raised_at: string;
  closed_by: string | null; closed_at: string | null; replies: { id: number; author: string; side: string; at: string; text: string }[] }
const OBS_PILL: Record<Obs['status'], string> = { open: 'p-discrepancy', answered: 'p-pending', closed: 'p-active' };
const OBS_WORD: Record<Obs['status'], string> = { open: 'Open: waiting for the institution', answered: 'Answered: waiting for the officer', closed: 'Closed' };

/** Officers raise; the institution replies (status answered); officers close. Every step is in the portal audit trail. */
export function ObservationsPanel({ fid, role }: { fid: string; role: 'aicte' | 'institution' | 'auditor' }) {
  const { run } = useStore();
  const d = useApi<{ items: Obs[] }>(`/fdrs/${fid}/observations`, [fid]);
  const [raise, setRaise] = useState(false);
  const [cat, setCat] = useState('missing_document');
  const [text, setText] = useState('');
  const [reply, setReply] = useState<Record<number, string>>({});
  const items = d.data?.items ?? [];
  return (
    <Panel title="Scrutiny observations" sub={`${items.filter((o) => o.status !== 'closed').length} open · officers raise, the institution replies, officers close`}
      action={role === 'aicte' ? <button className="btn btn-ghost btn-sm" onClick={() => setRaise(true)}><MessageSquarePlus size={15} aria-hidden /> Raise observation</button> : undefined}>
      {d.error ? <ErrorBox text={d.error} /> : !d.data ? <Loading rows={2} /> : items.length === 0 ? <Empty text="No observations" hint={role === 'aicte' ? 'Raise one if a document is missing or a value does not match.' : undefined} /> : (
        <ul className="esc-list">
          {items.map((o) => (
            <li key={o.id} className="card esc-card">
              <div className="esc-head">
                <b>#{o.id} · {o.category_label}</b>
                <span className={`pill ${OBS_PILL[o.status]}`}>{OBS_WORD[o.status]}</span>
              </div>
              <p className="small" style={{ margin: '6px 0' }}>{o.text}</p>
              <p className="muted small" style={{ margin: 0 }}>Raised by {o.raised_by} · {fmtDateTime(o.raised_at)}{o.closed_at && <> · closed by {o.closed_by} · {fmtDateTime(o.closed_at)}</>}</p>
              {o.replies.length > 0 && (
                <ol className="family">
                  {o.replies.map((r) => <li key={r.id}><b>{r.side === 'institution' ? 'Institution' : 'AICTE'}</b> ({r.author}) · {fmtDateTime(r.at)}: {r.text}</li>)}
                </ol>
              )}
              {o.status !== 'closed' && role !== 'auditor' && (
                <div className="obs-reply">
                  <label className="sr-only" htmlFor={`rep-${o.id}`}>Reply to observation {o.id}</label>
                  <textarea id={`rep-${o.id}`} className="inp" rows={2} value={reply[o.id] ?? ''} onChange={(e) => setReply({ ...reply, [o.id]: e.target.value })}
                    placeholder={role === 'institution' ? 'Your reply (e.g. lien letter uploaded on …)' : 'Note to the institution'} />
                  <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                    <button className="btn btn-primary btn-sm" disabled={(reply[o.id] ?? '').trim().length < 2}
                      onClick={async () => { if (await run(() => post(`/observations/${o.id}/replies`, { text: reply[o.id] }), 'Reply recorded') !== undefined) setReply({ ...reply, [o.id]: '' }); }}>Send reply</button>
                    {role === 'aicte' && <button className="btn btn-green btn-sm" onClick={() => run(() => post(`/observations/${o.id}/close`), `Observation ${o.id} closed`)}>Close observation</button>}
                  </div>
                </div>
              )}
            </li>
          ))}
        </ul>
      )}
      <Modal open={raise} onClose={() => setRaise(false)} title="Raise a scrutiny observation" sub={`${fid} · the institution is notified through the Nudge Ladder`}
        footer={<><button className="btn btn-ghost" onClick={() => setRaise(false)}>Cancel</button>
          <button className="btn btn-primary" disabled={text.trim().length < 5}
            onClick={async () => { if (await run(() => post(`/fdrs/${fid}/observations`, { category: cat, text }), 'Observation raised') !== undefined) { setRaise(false); setText(''); } }}>Raise</button></>}>
        <label className="lb" htmlFor="obs-cat">Category</label>
        <select id="obs-cat" className="inp" value={cat} onChange={(e) => setCat(e.target.value)}>
          <option value="missing_document">Missing document</option><option value="mismatch">Mismatch with the bank record</option><option value="query">Query</option>
        </select>
        <label className="lb" htmlFor="obs-text" style={{ marginTop: 12 }}>Observation <em>*</em></label>
        <textarea id="obs-text" className="inp" value={text} onChange={(e) => setText(e.target.value)} placeholder="e.g. Bank lien letter is not on record" />
      </Modal>
    </Panel>
  );
}

// ---------------------------------------------------------------- permitted field edits
interface FieldRule { entity: string; field: string; label: string; roles: string[]; pii: boolean; fdr_states: string[] | null; you_can_edit: boolean }
interface FieldChange { id: number; field: string; before: string | null; after: string | null; actor: string; at: string; reason: string; audit_seq: number }

const fmtField = (field: string, v: string | number | null) => (v === null || v === '' ? '—' : field === 'rate_bp' ? `${(Number(v) / 100).toFixed(2)}% (${v} bp)` : String(v));

/** Only the fields the server permits, for the roles and FDR states it permits. Before / after and a reason are required;
 * the server writes the change to the hash-chained portal audit and returns its sequence number. */
export function FieldEdits({ f }: { f: Fdr }) {
  const { run } = useStore();
  const rules = useApi<{ fields: FieldRule[]; never_editable: string[] }>('/records/fields');
  const hist = useApi<{ items: FieldChange[] }>(`/records/fdr/${f.id}/changes`, [f.id]);
  const [edit, setEdit] = useState<FieldRule | null>(null);
  const [value, setValue] = useState('');
  const [reason, setReason] = useState('');
  const [err, setErr] = useState('');
  const mine = (rules.data?.fields ?? []).filter((r) => r.entity === 'fdr');
  const current = (r: FieldRule) => (r.field === 'rate_bp' ? f.rate_bp : (f as unknown as Record<string, string>)[r.field]) ?? null;
  const open = (r: FieldRule) => {
    setEdit(r);
    setValue(String(current(r) ?? ''));
    setReason('');
    setErr('');
  };
  const save = async () => {
    setErr('');
    try {
      await api(`/records/fdr/${f.id}`, { method: 'PATCH', json: { field: edit!.field, value, reason } });
      await run(async () => undefined, `${edit!.label} updated`);
      setEdit(null);
    } catch (e) {
      setErr(errorText(e));
    }
  };
  return (
    <Panel title="Record fields" sub="Bank, number, amount and dates are held by the ledger and never edited here; a correction is a new submission">
      {rules.error ? <ErrorBox text={rules.error} /> : !rules.data ? <Loading rows={2} /> : (
        <dl className="kv">
          {mine.map((r) => {
            const allowedNow = r.you_can_edit && (!r.fdr_states || r.fdr_states.includes(f.status));
            return (
              <div key={r.field} style={{ display: 'contents' }}>
                <dt>{r.label}</dt>
                <dd style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
                  <span>{fmtField(r.field, current(r))}</span>
                  {allowedNow ? <button className="btn btn-ghost btn-xs" onClick={() => open(r)} aria-label={`Edit ${r.label}`}><Pencil size={13} aria-hidden /> Edit</button>
                    : <span className="muted small">{!r.you_can_edit ? 'not editable by your role' : `editable only while ${r.fdr_states?.join(' or ')}`}</span>}
                </dd>
              </div>
            );
          })}
        </dl>
      )}
      <h3 className="small" style={{ marginTop: 14, color: 'var(--navy)' }}>Change history</h3>
      {!hist.data ? <Loading rows={1} /> : hist.data.items.length === 0 ? <p className="muted small">No field has been changed.</p> : (
        <table className="diff">
          <caption className="sr-only">Field changes for {f.id}</caption>
          <thead><tr><th scope="col">Field</th><th scope="col">Before</th><th scope="col">After</th><th scope="col">Who, when, why</th></tr></thead>
          <tbody>
            {hist.data.items.map((c) => (
              <tr key={c.id}><td>{c.field}</td><td className="before">{fmtField(c.field, c.before)}</td><td className="after">{fmtField(c.field, c.after)}</td>
                <td className="small">{c.actor} · {fmtDateTime(c.at)} · audit #{c.audit_seq}<br />{c.reason}</td></tr>
            ))}
          </tbody>
        </table>
      )}
      <Modal open={!!edit} onClose={() => setEdit(null)} title={`Change ${edit?.label.toLowerCase() ?? ''}`} sub={`${f.id} · ${inrP(f.amount_paise)}`}
        footer={<><button className="btn btn-ghost" onClick={() => setEdit(null)}>Cancel</button>
          <button className="btn btn-primary" disabled={!edit || value.trim() === String(current(edit) ?? '') || reason.trim().length < 5} onClick={save}>Save change</button></>}>
        {edit && (
          <>
            <label className="lb" htmlFor="fe-val">New value {edit.field === 'rate_bp' && '(basis points, e.g. 710 = 7.10%)'}</label>
            <input id="fe-val" className="inp" value={value} onChange={(e) => setValue(e.target.value)} />
            <table className="diff">
              <caption className="sr-only">Before and after</caption>
              <thead><tr><th scope="col">Before</th><th scope="col">After</th></tr></thead>
              <tbody><tr><td className="before">{fmtField(edit.field, current(edit))}</td><td className="after">{fmtField(edit.field, value)}</td></tr></tbody>
            </table>
            <label className="lb" htmlFor="fe-reason" style={{ marginTop: 12 }}>Reason <em>*</em></label>
            <textarea id="fe-reason" className="inp" value={reason} onChange={(e) => setReason(e.target.value)} placeholder="e.g. Branch name as printed on the bank's covering letter" />
            <p className="hint">Recorded with your name and the time in the hash-chained audit trail.</p>
            {err && <div className="error-box" role="alert"><span>{err}</span></div>}
          </>
        )}
      </Modal>
    </Panel>
  );
}
