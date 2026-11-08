import { BadgeCheck, CircleDashed, FileDown, Loader2, Printer, ShieldAlert } from 'lucide-react';
import { useRef, useState } from 'react';
import { api, downloadFile, errorText } from '../api/client';
import type { Fdr, Institution, Release } from '../api/types';
import { printNode } from '../lib/export';
import { fmtDate, fmtDateTime, inrP } from '../lib/format';
import { useT } from '../lib/prefs';
import { useStore } from '../store/Store';
import { InfoTip } from './ui';

/** One sentence each, shown behind the "i" next to every answer. */
export const GLOSSARY: Record<Answer, string> = {
  entitlement: 'Whether the institution is entitled to have the deposit released, as recorded in the Section Officer’s scrutiny (for example closure approval and Affidavit-6).',
  attribution: 'Whether the instrument is proven to belong to this institution by a signed message from the issuing bank, not by the institution’s own declaration.',
  availability: 'Whether the instrument is still held under lien to AICTE and not in dispute, so that it can actually be released.',
  authorisation: 'Whether the competent authority approved the release with a DSC signature over the release-gate decision, separately from the officer who did the scrutiny.',
  completion: 'Whether the bank confirmed the outcome (lien discharge for an FDR, positive credit confirmation for a refund); a debit with a UTR alone is not completion.',
};

export type Answer = 'entitlement' | 'attribution' | 'availability' | 'authorisation' | 'completion';
type Tone = 'ok' | 'wait' | 'bad';
export interface Row { field: string; label: string; declared: string | number; bank_confirmed: string | number | null; confidence: 'BANK_CONFIRMED' | 'DECLARED' | 'MISMATCH' | 'UNVERIFIED_SOURCE' }
export interface Confirmation { evidence_id: string; as_of: string; bank: string; key_id: string; received_at: string }

/**
 * The five answers are kept apart, as the solution requires. Each is read straight from the records on this page;
 * nothing is computed beyond picking the wording.
 */
export function fiveAnswers(f: Fdr, release: Release | null, confirmation: Confirmation | null): { key: Answer; label: string; tone: Tone; text: string }[] {
  const released = f.status === 'released' || f.status === 'closed';
  return [
    {
      key: 'entitlement', label: 'Entitlement',
      ...(release?.scrutiny_by ? { tone: 'ok' as Tone, text: `Scrutiny recorded by ${release.scrutiny_by}` }
        : release ? { tone: 'wait' as Tone, text: 'Release requested; scrutiny not yet recorded' }
          : { tone: 'wait' as Tone, text: released ? 'Recorded before this ledger (released instrument)' : 'No release requested' }),
    },
    {
      key: 'attribution', label: 'Attribution',
      ...(confirmation ? { tone: 'ok' as Tone, text: `Issuing bank confirmed (${confirmation.evidence_id})` }
        : f.status === 'discrepancy' ? { tone: 'bad' as Tone, text: 'Bank values do not match the declaration' }
          : { tone: 'wait' as Tone, text: 'Declared by the institution only' }),
    },
    {
      key: 'availability', label: 'Availability',
      ...(f.status === 'verified' ? { tone: 'ok' as Tone, text: 'Held under lien to AICTE' }
        : f.status === 'pending' ? { tone: 'wait' as Tone, text: 'Not yet verified' }
          : f.status === 'discrepancy' ? { tone: 'bad' as Tone, text: `Discrepancy open: ${f.discrepancy_reason ?? 'see record'}` }
            : { tone: 'wait' as Tone, text: 'No longer held (released or closed)' }),
    },
    {
      key: 'authorisation', label: 'Authorisation',
      ...(release?.approved_by ? { tone: 'ok' as Tone, text: `Approved by ${release.approved_by} with DSC` }
        : release && release.stage === 'REJECTED' ? { tone: 'bad' as Tone, text: 'Release request rejected' }
          : { tone: 'wait' as Tone, text: release ? 'Awaiting competent-authority approval' : 'Not requested' }),
    },
    {
      key: 'completion', label: 'Completion',
      ...(release?.stage === 'COMPLETED' || released ? { tone: 'ok' as Tone, text: 'Completed on the bank’s confirmation' }
        : release?.stage === 'APPROVED' ? { tone: 'wait' as Tone, text: 'Approved; waiting for the bank’s confirmation. Not complete.' }
          : { tone: 'wait' as Tone, text: 'Not complete' }),
    },
  ];
}

const TONE_ICON: Record<Tone, React.ReactNode> = {
  ok: <BadgeCheck size={16} aria-hidden />,
  wait: <CircleDashed size={16} aria-hidden />,
  bad: <ShieldAlert size={16} aria-hidden />,
};
const TONE_WORD: Record<Tone, string> = { ok: 'Yes', wait: 'Not yet', bad: 'Problem' };

export function FiveAnswers({ answers }: { answers: ReturnType<typeof fiveAnswers> }) {
  const t = useT();
  return (
    <ul className="answers">
      {answers.map((a) => (
        <li key={a.key} className={`answer a-${a.tone}`}>
          <span className="answer-ico">{TONE_ICON[a.tone]}</span>
          <span className="answer-body">
            <span className="answer-h">{t(a.label)} <InfoTip label={a.label} text={GLOSSARY[a.key]} /></span>
            <span className="answer-t"><span className="sr-only">{TONE_WORD[a.tone]}: </span>{a.text}</span>
          </span>
        </li>
      ))}
    </ul>
  );
}

const CONF_WORD: Record<Row['confidence'], string> = { BANK_CONFIRMED: 'Bank confirmed', DECLARED: 'Institution declared', MISMATCH: 'Mismatch', UNVERIFIED_SOURCE: 'Unverified source' };

interface PacketData { rule: { key: string; status: string; value: unknown; cites: string[]; action: string; on_date: string } | null; audit: { seq: number; hash: string; at: string; type: string } | null; auditNote?: string }

/**
 * One-click evidence packet: declared vs bank-confirmed, confidence per item, the rule the kernel cites for release on
 * the print date, the five answers, and the newest ledger hash for this FDR. Printed on A4 with the SIMULATED label.
 * "Save as PDF" in the print dialog gives the PDF; it is the same layout.
 */
export function PacketButton({ f, inst, rows, confirmation, release, show }: {
  f: Fdr; inst: Institution; rows: Row[]; confirmation: Confirmation | null; release: Release | null; show: (field: string, v: string | number | null) => string;
}) {
  const { user, toast } = useStore();
  const t = useT();
  const [busy, setBusy] = useState(false);
  const [data, setData] = useState<PacketData | null>(null);
  const ref = useRef<HTMLDivElement>(null);
  const answers = fiveAnswers(f, release, confirmation);

  const go = async () => {
    setBusy(true);
    const today = new Date().toISOString().slice(0, 10);
    const [rule, audit] = await Promise.all([
      api<PacketData['rule']>(`/rules/resolve?key=release.fdr_instrument&on_date=${today}`).catch(() => null),
      user?.role === 'INSTITUTION'
        ? Promise.resolve(null)
        : api<{ items: { seq: number; hash: string; at: string; type: string }[] }>(`/audit-trail?chain=kernel&size=1&q=${encodeURIComponent(f.id)}`).then((r) => r.items[0] ?? null).catch(() => null),
    ]);
    setData({ rule, audit, auditNote: user?.role === 'INSTITUTION' ? 'The audit trail is open to AICTE officials and auditors only.' : undefined });
    setBusy(false);
    // wait one frame so the packet below renders with the fetched data
    requestAnimationFrame(() => requestAnimationFrame(() => {
      if (ref.current) printNode(ref.current, { title: `Evidence packet · ${f.id}`, simulated: true, subtitle: `${inst.name} · ${inst.aicte_id}` });
      else toast('Could not prepare the packet', 'error');
    }));
  };

  return (
    <>
      <button className="btn btn-ghost" onClick={go} disabled={busy}>
        {busy ? <Loader2 size={17} className="spin" aria-hidden /> : <Printer size={17} aria-hidden />} {t('Print evidence packet')}
      </button>
      <button className="btn btn-ghost" onClick={() => downloadFile(`/fdrs/${f.id}/packet.pdf`, `${f.id}-evidence-packet.pdf`).catch((e) => toast(errorText(e), 'error'))}>
        <FileDown size={17} aria-hidden /> {t('Download PDF packet')}
      </button>
      {data && (
        <div className="offscreen" aria-hidden ref={ref}>
          <section className="pk-sec">
            <h2>Instrument</h2>
            <dl className="pk-kv">
              <dt>FDR reference</dt><dd>{f.id}</dd>
              <dt>Institution</dt><dd>{inst.name} ({inst.aicte_id})</dd>
              <dt>Bank</dt><dd>{f.bank_name}, {f.branch}</dd>
              <dt>FDR number</dt><dd>{f.instrument_no}</dd>
              <dt>Amount</dt><dd>{inrP(f.amount_paise)}</dd>
              <dt>Issue / maturity</dt><dd>{fmtDate(f.issue_date)} / {fmtDate(f.maturity_date)}</dd>
              <dt>Status</dt><dd>{f.status}</dd>
            </dl>
          </section>
          <section className="pk-sec">
            <h2>Declared vs bank-confirmed <span className="pk-sim">SIMULATED</span></h2>
            <table className="pk-table">
              <thead><tr><th>Field</th><th>Institution declared</th><th>Bank confirmed (simulated bank)</th><th>Confidence</th></tr></thead>
              <tbody>
                {rows.map((r) => (
                  <tr key={r.field}><td>{r.label}</td><td>{show(r.field, r.declared)}</td><td>{show(r.field, r.bank_confirmed)}</td><td>{CONF_WORD[r.confidence]}</td></tr>
                ))}
              </tbody>
            </table>
            <p className="pk-note">
              {confirmation
                ? `Relied on ${confirmation.evidence_id}, signed by ${confirmation.key_id}, received ${fmtDateTime(confirmation.received_at)}; bank position as of ${fmtDate(confirmation.as_of)}.`
                : 'No valid confirmation from the issuing bank: every value is as declared by the institution.'}
            </p>
          </section>
          <section className="pk-sec">
            <h2>Five answers</h2>
            <table className="pk-table">
              <tbody>{answers.map((a) => <tr key={a.key}><th>{a.label}</th><td>{TONE_WORD[a.tone]}</td><td>{a.text}</td></tr>)}</tbody>
            </table>
          </section>
          <section className="pk-sec">
            <h2>Rule cited</h2>
            {data.rule ? (
              <p className="pk-note">
                <b>{data.rule.key}</b> on {fmtDate(data.rule.on_date)}: {data.rule.status}{data.rule.value !== null && data.rule.value !== undefined ? ` (${String(data.rule.value)})` : ''}.
                {' '}Cites: {data.rule.cites.length ? data.rule.cites.join('; ') : 'none'}. Kernel action: {data.rule.action}.
              </p>
            ) : <p className="pk-note">The rule service did not answer; no rule is cited.</p>}
          </section>
          <section className="pk-sec">
            <h2>Audit hash</h2>
            {data.audit ? (
              <p className="pk-note">Newest ledger event for this FDR: #{data.audit.seq} {data.audit.type.replace(/_/g, ' ')} at {fmtDateTime(data.audit.at)}.<br /><code className="pk-hash">{data.audit.hash}</code></p>
            ) : <p className="pk-note">{data.auditNote ?? 'No ledger event found for this FDR.'}</p>}
          </section>
        </div>
      )}
    </>
  );
}
