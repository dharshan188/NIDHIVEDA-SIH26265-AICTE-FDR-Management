import { AlertOctagon, ArrowUpRight, BellRing, CheckCircle2, ChevronRight, Clock3, FileDown, FileSpreadsheet, Info, Mail, MessageCircle, MessageSquare, MoonStar, Smartphone, Sparkles, TrendingUp } from 'lucide-react';
import { useEffect, useRef, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { api, downloadFile, errorText, post } from '../../api/client';
import type { Delivery, LadderNotice, Rung } from '../../api/types';
import { DiffTable, diffLeaves } from '../../components/PolicyDiff';
import { TableWrap } from '../../components/Tables';
import { Empty, ErrorBox, Kpi, Loading, PageHead, Panel, SimBadge, Stagger, Tabs } from '../../components/ui';
import { fmtDateTime, relTime } from '../../lib/format';
import { useRole } from '../../lib/hooks';
import { useT } from '../../lib/prefs';
import { useApi, useStore } from '../../store/Store';

const RUNGS: { key: Rung; label: string; hint: string; Icon: typeof Info }[] = [
  { key: 'info', label: 'Informational', hint: 'In-app, batched into a daily digest', Icon: Info },
  { key: 'action', label: 'Action needed', hint: 'In-app and e-mail', Icon: BellRing },
  { key: 'deadline', label: 'Deadline within 7 days', hint: 'In-app, e-mail and SMS', Icon: Clock3 },
  { key: 'overdue', label: 'Overdue', hint: 'Every channel, copied to the escalation role', Icon: AlertOctagon },
];
const CH_ICON: Record<Delivery['channel'], typeof Mail> = { in_app: BellRing, email: Mail, sms: MessageSquare, whatsapp: MessageCircle, push: Smartphone };
const CH_LABEL: Record<Delivery['channel'], string> = { in_app: 'In-app', email: 'E-mail', sms: 'SMS', whatsapp: 'WhatsApp', push: 'Push' };

export function RungPill({ rung, label }: { rung: Rung; label?: string }) {
  return <span className={`rung rung-${rung}`}>{label ?? RUNGS.find((r) => r.key === rung)?.label ?? rung}</span>;
}

function DeliveryChip({ d }: { d: Delivery }) {
  const Icon = CH_ICON[d.channel];
  const word = d.status === 'delivered' && d.channel === 'in_app' ? 'shown' : d.status;
  const tip = [d.provider, d.reason, d.delivered_at ? `receipt ${fmtDateTime(d.delivered_at)}${d.receipt_simulated ? ' (simulated receipt)' : ''}` : null].filter(Boolean).join(' · ');
  return (
    <span className={`dchip d-${d.status}`} title={tip}>
      <Icon size={13} aria-hidden /> {CH_LABEL[d.channel]}: {word}
      {d.status === 'deferred' && <MoonStar size={12} aria-label="quiet hours" />}
      {d.simulated && d.channel !== 'in_app' && <span className="dchip-sim">SIMULATED</span>}
    </span>
  );
}

/** The ladder: how many open notices sit on each rung. Selecting a rung filters the list. */
function Ladder({ open, value, onPick }: { open: Record<Rung, number>; value: Rung | ''; onPick: (r: Rung | '') => void }) {
  const t = useT();
  return (
    <ol className="ladder" aria-label={t('Urgency ladder')}>
      {[...RUNGS].reverse().map((r, i) => (
        <li key={r.key} style={{ marginLeft: `${i * 18}px` }}>
          <button type="button" className={`ladder-step rung-${r.key}${value === r.key ? ' on' : ''}`} aria-pressed={value === r.key} onClick={() => onPick(value === r.key ? '' : r.key)}>
            <r.Icon size={18} aria-hidden />
            <span className="ls-text"><b>{t(r.label)}</b><small>{t(r.hint)}</small></span>
            <span className="ls-count num" aria-label={`${open[r.key] ?? 0} open`}>{open[r.key] ?? 0}</span>
          </button>
        </li>
      ))}
    </ol>
  );
}

export function NotificationCentre() {
  const { base } = useRole();
  const { run } = useStore();
  const nav = useNavigate();
  const t = useT();
  const [rung, setRung] = useState<Rung | ''>('');
  const [status, setStatus] = useState<'open' | 'acknowledged' | 'all'>('open');
  const [openId, setOpenId] = useState<number | null>(null);
  const q = `/nudge/centre?size=60${rung ? `&rung=${rung}` : ''}${status !== 'all' ? `&status=${status}` : ''}`;
  const d = useApi<{ total: number; open_by_rung: Record<Rung, number>; items: LadderNotice[] }>(q, [q]);
  const open = (n: LadderNotice) => run(async () => {
    await post(`/nudge/notifications/${n.id}/open`);
    setOpenId(n.id);
  });
  return (
    <Stagger>
      <PageHead title="Notification centre" sub="Nudge Ladder: urgency decides the channels; opening a notice acknowledges it and stops it climbing"
        crumbs={[{ label: 'Dashboard', to: base }, { label: 'Notifications' }]}
        actions={<button className="btn btn-ghost" onClick={() => run(() => post('/notifications/read'), 'All marked as read')}>{t('Mark all as read')}</button>} />
      <div className="nudge-grid">
        <Panel title="Ladder" sub="Open notices by rung">
          {d.data ? <Ladder open={d.data.open_by_rung} value={rung} onPick={setRung} /> : <Loading rows={4} />}
          <p className="muted small" style={{ marginTop: 12 }}>
            {t('No SMS or WhatsApp between 20:00 and 08:00 IST unless the item is overdue. Informational notices arrive as one daily digest.')}
          </p>
        </Panel>
        <Panel title={rung ? RUNGS.find((r) => r.key === rung)?.label : 'All notices'} sub={d.data ? `${d.data.total} ${t('notices')}` : undefined}>
          <Tabs id="nstatus" value={status} onChange={setStatus} tabs={[{ key: 'open', label: t('Open') }, { key: 'acknowledged', label: t('Acknowledged') }, { key: 'all', label: t('All') }]} />
          {d.error ? <ErrorBox text={d.error} /> : !d.data ? <Loading layout="list" rows={6} /> : d.data.items.length === 0 ? <Empty text="Nothing here" hint="Pick another rung or tab." /> : (
            <ul className="notif-list ladder-list">
              {d.data.items.map((n) => (
                <li key={n.id} className={`ln rung-edge-${n.rung}${n.ack_at ? ' is-ack' : ''}`}>
                  <div className="ln-head">
                    <RungPill rung={n.rung} label={n.rung_label} />
                    {n.window && <span className="win-chip">{n.window}</span>}
                    {n.escalation_step > 0 && <span className="win-chip esc"><TrendingUp size={12} aria-hidden /> {t('step')} {n.escalation_step}</span>}
                    <time dateTime={n.at} className="notif-time">{relTime(n.at)}</time>
                  </div>
                  <b className="ln-title">{n.title}</b>
                  <p className="ln-text">{n.text}</p>
                  <div className="ln-chips">{n.deliveries.map((x) => <DeliveryChip key={x.channel} d={x} />)}</div>
                  <div className="ln-actions">
                    {n.ack_at
                      ? <span className="ack-ok"><CheckCircle2 size={15} aria-hidden /> {t('Acknowledged')} {relTime(n.ack_at)} ({n.ack_via === 'link' ? t('action link') : t('opened')})</span>
                      : <button className="btn btn-sm" onClick={() => open(n)}>{t('Open and acknowledge')}</button>}
                    {n.ref?.startsWith('FDR') && <button className="btn btn-sm btn-ghost" onClick={() => nav(`${base}/fdr/${n.ref}`)}>{t('Open record')} <ArrowUpRight size={14} aria-hidden /></button>}
                    <button className="btn btn-sm btn-ghost" onClick={() => setOpenId(openId === n.id ? null : n.id)} aria-expanded={openId === n.id}>{t('Ladder history')}</button>
                  </div>
                  {openId === n.id && <Family id={n.id} />}
                </li>
              ))}
            </ul>
          )}
        </Panel>
      </div>
      <Prefs />
    </Stagger>
  );
}

function Family({ id }: { id: number }) {
  const t = useT();
  const d = useApi<{ ladder: { id: number; at: string; rung: Rung; rung_label: string; audience: string; template: string; title: string; ack_at: string | null; escalation_step: number }[] }>(`/nudge/notifications/${id}`);
  if (!d.data) return <Loading rows={2} />;
  return (
    <ol className="family" aria-label={t('Ladder history')}>
      {d.data.ladder.map((x) => (
        <li key={x.id}>
          <RungPill rung={x.rung} label={x.rung_label} /> <span className="muted">{fmtDateTime(x.at)}</span> · {x.title}
          <span className="muted"> → {x.audience.replace('competent_authority', 'competent authority')}</span>
          {x.ack_at && <span className="ack-ok"> · {t('acknowledged')} {fmtDateTime(x.ack_at)}</span>}
        </li>
      ))}
    </ol>
  );
}

function Prefs() {
  const t = useT();
  const { run } = useStore();
  const d = useApi<{ lang: 'en' | 'hi'; email: boolean; sms: boolean; whatsapp: boolean; push: boolean; digest: boolean; note: string }>('/nudge/prefs');
  const [p, setP] = useState(d.data);
  useEffect(() => setP(d.data), [d.data]);
  if (!p) return null;
  const ch = ['email', 'sms', 'whatsapp', 'push', 'digest'] as const;
  return (
    <Panel title="My notification preferences" sub={d.data?.note}>
      <div className="prefs-row">
        <label className="lfield">{t('Language of notices')}
          <select className="sel" value={p.lang} onChange={(e) => setP({ ...p, lang: e.target.value as 'en' | 'hi' })}>
            <option value="en">English</option><option value="hi">हिंदी (Hindi)</option>
          </select>
        </label>
        {ch.map((c) => (
          <label key={c} className="check">
            <input type="checkbox" checked={p[c]} onChange={(e) => setP({ ...p, [c]: e.target.checked })} />
            {c === 'digest' ? t('Daily digest for informational notices') : CH_LABEL[c as Delivery['channel']]}
          </label>
        ))}
        <button className="btn" onClick={() => run(() => api('/nudge/prefs', { method: 'PUT', json: p }), 'Preferences saved')}>{t('Save')}</button>
      </div>
    </Panel>
  );
}

/** "What changed since you last looked": built from the audit trail since the previous sign-in. */
export function WhatChanged() {
  const t = useT();
  const { base } = useRole();
  const d = useApi<{ since: string; first_visit: boolean; items: { type: string; count: number; text: string; examples: string[]; link: string }[];
    attention: { id: number; rung: Rung; title: string; at: string; ref: string | null }[]; open_observations: number }>('/nudge/what-changed');
  if (d.error) return null;
  if (!d.data) return <div className="card wc"><Loading rows={2} /></div>;
  const w = d.data;
  return (
    <section className="card wc" aria-labelledby="wc-h">
      <div className="wc-head">
        <Sparkles size={18} aria-hidden />
        <h2 id="wc-h">{w.first_visit ? t('In the last 7 days') : t('Since you last looked')}</h2>
        <span className="muted small">{t('from')} {fmtDateTime(w.since)} · {t('built from the audit trail')}</span>
      </div>
      {w.items.length === 0 && w.attention.length === 0 ? <p className="muted">{t('Nothing new needs you.')}</p> : (
        <div className="wc-body">
          <ul className="wc-items">
            {w.items.slice(0, 6).map((i) => (
              <li key={i.type}><Link to={i.link}><b className="num">{i.count}</b> {i.text.replace(/^\d+ /, '')}{i.examples.length > 0 && <span className="muted"> · {i.examples.join(', ')}</span>} <ChevronRight size={14} aria-hidden /></Link></li>
            ))}
          </ul>
          {(w.attention.length > 0 || w.open_observations > 0) && (
            <div className="wc-att">
              <b>{t('Needs your attention')}</b>
              <ul>
                {w.attention.map((a) => <li key={a.id}><RungPill rung={a.rung} /> <Link to={`${base}/notifications`}>{a.title}</Link></li>)}
                {w.open_observations > 0 && <li><Link to={base === '/institution' ? `${base}/fdrs` : `${base}/verification`}>{w.open_observations} {base === '/institution' ? t('scrutiny observations waiting for your reply') : t('observation replies to review')}</Link></li>}
              </ul>
            </div>
          )}
        </div>
      )}
    </section>
  );
}

interface Health {
  window_days: number; generated_at: string; providers: Record<string, { provider: string; simulated: boolean }>;
  totals: { notices: number; deliveries: number; acknowledged: number; ack_rate: number | null; escalated: number; escalation_notices: number; median_hours_to_action: number | null };
  by_channel: Record<string, Record<string, number>>;
  by_rung: Record<Rung, { notices: number; acknowledged: number; median_hours_to_action: number | null }>;
  per_institution: { institution_id: string; institution: string; notices: number; acknowledged: number; ack_rate: number; median_hours_to_action: number | null; escalated: number }[];
  note: string;
}

export function NotificationHealth() {
  const { base } = useRole();
  const t = useT();
  const [days, setDays] = useState(30);
  const d = useApi<Health>(`/nudge/health?days=${days}`, [days]);
  const h = d.data;
  const pct = (x: number | null) => (x == null ? '—' : `${(x * 100).toFixed(1)}%`);
  return (
    <Stagger>
      <PageHead title="Notification health" sub="Measured from outbox and delivery rows: sent, delivered (provider receipts only), acknowledged, escalated, time-to-action"
        crumbs={[{ label: 'Dashboard', to: base }, { label: 'Notification health' }]}
        actions={<select className="sel" aria-label={t('Window')} value={days} onChange={(e) => setDays(Number(e.target.value))}><option value={7}>7 days</option><option value={30}>30 days</option><option value={90}>90 days</option></select>} />
      {d.error ? <ErrorBox text={d.error} /> : !h ? <Loading rows={6} /> : (
        <>
          <div className="kpis k4">
            <Kpi compact tone="blue" icon={<BellRing size={30} />} label="Notices" value={h.totals.notices} sub={`${h.totals.deliveries} deliveries`} />
            <Kpi compact tone="green" icon={<CheckCircle2 size={30} />} label="Acknowledged" value={h.totals.acknowledged} sub={`ack rate ${pct(h.totals.ack_rate)}`} />
            <Kpi compact tone="orange" icon={<TrendingUp size={30} />} label="Escalated" value={h.totals.escalated} sub={`${h.totals.escalation_notices} escalation notices`} />
            <Kpi compact tone="purple" icon={<Clock3 size={30} />} label="Median time to action" value={h.totals.median_hours_to_action == null ? '—' : `${h.totals.median_hours_to_action} h`} sub="created → acknowledged" />
          </div>
          <div className="row g-2">
            <Panel title="By channel" sub={h.note}>
              <TableWrap label="Notification health by channel" simulated>
                <table className="tbl">
                  <thead><tr><th>Channel</th><th>Provider</th><th className="r">Total</th><th className="r">Sent</th><th className="r">Delivered (receipt)</th><th className="r">Delivered (simulated receipt)</th><th className="r">Deferred</th><th className="r">Batched / digested</th><th className="r">Failed</th></tr></thead>
                  <tbody>
                    {Object.entries(h.by_channel).map(([ch, c]) => (
                      <tr key={ch}>
                        <td>{CH_LABEL[ch as Delivery['channel']] ?? ch}</td>
                        <td>{h.providers[ch]?.provider} {h.providers[ch]?.simulated && <SimBadge title="Provider simulator: nothing leaves this machine." />}</td>
                        <td className="r num">{c.total ?? 0}</td><td className="r num">{c.sent ?? 0}</td><td className="r num">{c.delivered_receipt ?? 0}</td>
                        <td className="r num">{c.delivered_simulated ?? 0}</td><td className="r num">{c.deferred ?? 0}</td>
                        <td className="r num">{(c.batched ?? 0) + (c.digested ?? 0)}</td><td className="r num">{c.failed ?? 0}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </TableWrap>
            </Panel>
            <Panel title="Time to action by stage" sub="Median hours from notice to acknowledgement, per rung">
              <TableWrap label="Time to action by rung">
                <table className="tbl">
                  <thead><tr><th>Rung</th><th className="r">Notices</th><th className="r">Acknowledged</th><th className="r">Median hours</th></tr></thead>
                  <tbody>
                    {RUNGS.map((r) => (
                      <tr key={r.key}><td><RungPill rung={r.key} /></td><td className="r num">{h.by_rung[r.key].notices}</td><td className="r num">{h.by_rung[r.key].acknowledged}</td>
                        <td className="r num">{h.by_rung[r.key].median_hours_to_action ?? '—'}</td></tr>
                    ))}
                  </tbody>
                </table>
              </TableWrap>
            </Panel>
          </div>
          <Panel title="Acknowledgement and time-to-action per institution" sub="Lowest acknowledgement rate first">
            {h.per_institution.length === 0 ? <Empty text="No institution notices in this window" /> : (
              <TableWrap label="Acknowledgement per institution" tall>
                <table className="tbl">
                  <thead><tr><th>Institution</th><th className="r">Notices</th><th className="r">Acknowledged</th><th className="r">Ack rate</th><th className="r">Median hours to action</th><th className="r">Escalated</th></tr></thead>
                  <tbody>
                    {h.per_institution.map((r) => (
                      <tr key={r.institution_id}><td><Link to={`${base}/institutions/${r.institution_id}`}>{r.institution}</Link></td><td className="r num">{r.notices}</td>
                        <td className="r num">{r.acknowledged}</td><td className="r num">{pct(r.ack_rate)}</td><td className="r num">{r.median_hours_to_action ?? '—'}</td><td className="r num">{r.escalated}</td></tr>
                    ))}
                  </tbody>
                </table>
              </TableWrap>
            )}
          </Panel>
        </>
      )}
    </Stagger>
  );
}

export function Escalations() {
  const { base } = useRole();
  const t = useT();
  const d = useApi<{ items: { root_id: number; ref: string | null; institution_id: string | null; title: string; acknowledged: boolean;
    steps: { id: number; at: string; rung: Rung; audience: string; template: string; step: number; ack_at: string | null; ack_by: string | null }[] }[] }>('/nudge/escalations');
  const who = (a: string) => (a.startsWith('institution:') ? t('Institution') : a === 'aicte' ? t('AICTE scrutiny officer') : a === 'competent_authority' ? t('Competent authority') : a);
  return (
    <Stagger>
      <PageHead title="Escalations" sub="Unacknowledged notices climb the ladder and move along institution → AICTE officer → competent authority. Each step is in the audit trail."
        crumbs={[{ label: 'Dashboard', to: base }, { label: 'Escalations' }]} />
      <Panel>
        {d.error ? <ErrorBox text={d.error} /> : !d.data ? <Loading layout="list" rows={5} /> : d.data.items.length === 0 ? <Empty text="No escalations" hint="Notices escalate only when they are not acknowledged in time." /> : (
          <ul className="esc-list">
            {d.data.items.map((f) => (
              <li key={f.root_id} className="card esc-card">
                <div className="esc-head">
                  <b>{f.title}</b>
                  {f.ref?.startsWith('FDR') && <Link to={`${base}/fdr/${f.ref}`}>{f.ref}</Link>}
                  <span className={`pill ${f.acknowledged ? 'p-active' : 'p-discrepancy'}`}>{f.acknowledged ? t('Acknowledged: stopped') : t('Not acknowledged')}</span>
                </div>
                <ol className="esc-steps">
                  {f.steps.map((s) => (
                    <li key={s.id} className={`esc-step rung-edge-${s.rung}`}>
                      <RungPill rung={s.rung} />
                      <span><b>{who(s.audience)}</b> · {fmtDateTime(s.at)} · {s.template === 'escalation_copy' ? t('copied up the chain') : s.template === 'rung_up' ? t('moved up a rung') : t('first notice')}</span>
                      {s.ack_at && <span className="ack-ok"><CheckCircle2 size={14} aria-hidden /> {fmtDateTime(s.ack_at)}</span>}
                    </li>
                  ))}
                </ol>
              </li>
            ))}
          </ul>
        )}
      </Panel>
    </Stagger>
  );
}

interface MissingRow { institution_id: string; institution: string; instrument: string; class: string; bank: string; amount: string; maturity_date: string; required_label: string; state: string; detail: string }

export function MissingDocuments() {
  const { base, role } = useRole();
  const t = useT();
  const { toast } = useStore();
  const [state, setState] = useState<'' | 'absent' | 'expired' | 'unverified'>('');
  const q = `/reports/missing-documents?size=300${state ? `&state=${state}` : ''}`;
  const d = useApi<{ as_of: string; summary: Record<string, number>; institutions: number; total: number; items: MissingRow[]; required: Record<string, { type: string; label: string }[]>; planned: string }>(q, [q]);
  const exp = (fmt: 'csv' | 'pdf') => downloadFile(`/reports/missing-documents.${fmt}${state ? `?state=${state}` : ''}`, `missing-documents.${fmt}`).catch((e) => toast(errorText(e), 'error'));
  return (
    <Stagger>
      <PageHead title="Missing documents and exceptions" sub="Required documents per instrument class that are absent, expired or unverified"
        crumbs={[{ label: 'Dashboard', to: base }, { label: 'Missing documents' }]}
        actions={<><button className="btn btn-ghost" onClick={() => exp('csv')}><FileSpreadsheet size={16} aria-hidden /> CSV</button><button className="btn btn-ghost" onClick={() => exp('pdf')}><FileDown size={16} aria-hidden /> PDF</button></>} />
      {d.error ? <ErrorBox text={d.error} /> : !d.data ? <Loading rows={6} /> : (
        <>
          <div className="kpis k3">
            <Kpi compact tone="red" icon={<AlertOctagon size={30} />} label="Absent" value={d.data.summary.absent} sub="no document of the required type" onClick={() => setState('absent')} />
            <Kpi compact tone="orange" icon={<Clock3 size={30} />} label="Expired" value={d.data.summary.expired} sub="instrument matured, not renewed" onClick={() => setState('expired')} />
            <Kpi compact tone="purple" icon={<Info size={30} />} label="Unverified" value={d.data.summary.unverified} sub="on record but not yet trusted" onClick={() => setState('unverified')} />
          </div>
          <Panel title={state ? `${t(state[0].toUpperCase() + state.slice(1))} (${d.data.total})` : `${t('All exceptions')} (${d.data.total})`}
            sub={`${t('As of')} ${d.data.as_of} · ${role === 'institution' ? t('your institution only') : `${d.data.institutions} ${t('institutions')}`}`}
            action={state && <button className="btn btn-sm btn-ghost" onClick={() => setState('')}>{t('Show all')}</button>}>
            <p className="muted small">{t('Required')}: FDR — {d.data.required.FDR.map((x) => x.label).join(', ')}; {t('renewal FDR adds')} {d.data.required.FDR_RENEWAL.at(-1)?.label}; {t('online deposit')} — {d.data.required.ONLINE[0].label}. {d.data.planned}</p>
            {d.data.items.length === 0 ? <Empty text="No exceptions" /> : (
              <TableWrap label="Missing documents" exportName="missing-documents" tall simulated>
                <table className="tbl">
                  <thead><tr><th>Institution</th><th>Instrument</th><th>Class</th><th>Required document</th><th>State</th><th>Detail</th><th>Maturity</th></tr></thead>
                  <tbody>
                    {d.data.items.map((r) => (
                      <tr key={`${r.instrument}-${r.required_label}`}>
                        <td className="ell" title={r.institution}>{r.institution}</td>
                        <td>{r.class === 'FDR' ? <Link to={`${base}/fdr/${r.instrument}`}>{r.instrument}</Link> : r.instrument}</td>
                        <td>{r.class}</td><td>{r.required_label}</td>
                        <td><span className={`pill ${r.state === 'absent' ? 'p-discrepancy' : r.state === 'expired' ? 'p-pending' : 'p-maturing'}`}>{r.state}</span></td>
                        <td className="wrap-cell">{r.detail}</td><td>{r.maturity_date}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </TableWrap>
            )}
          </Panel>
        </>
      )}
    </Stagger>
  );
}

/** AICTE officials edit reminder windows, ladder thresholds and quiet hours; every change is versioned and audited. */
export function NotifyPolicyEditor() {
  const t = useT();
  const { run } = useStore();
  const d = useApi<{ policy: Record<string, any>; version: number; updated_by: string; updated_at: string | null; editable: boolean }>('/nudge/policy');
  const [before, setBefore] = useState('');
  const [deadline, setDeadline] = useState(7);
  const [action, setAction] = useState(30);
  const [reason, setReason] = useState('');
  useEffect(() => {
    if (!d.data) return;
    setBefore(d.data.policy.reminders.before_maturity_days.join(', '));
    setDeadline(d.data.policy.ladder.deadline_within_days);
    setAction(d.data.policy.ladder.action_needed_within_days);
  }, [d.data]);
  if (!d.data) return <Panel title="Notification policy"><Loading rows={3} /></Panel>;
  const p = d.data.policy;
  const next = { ...p, reminders: { ...p.reminders, before_maturity_days: before.split(',').map((x) => Number(x.trim())).filter(Boolean) },
    ladder: { ...p.ladder, deadline_within_days: deadline, action_needed_within_days: action } };
  const changes = diffLeaves(p, next);
  const save = async () => {
    if (await run(() => api('/nudge/policy', { method: 'PUT', json: { reason, policy: next } }), 'Notification policy published') !== undefined) setReason('');
  };
  return (
    <Panel title="Notification policy (Nudge Ladder)" sub={`${t('Version')} ${d.data.version} · ${d.data.updated_by}${d.data.updated_at ? ` · ${fmtDateTime(d.data.updated_at)}` : ''}`}>
      <dl className="pk-kv">
        <dt>{t('Daily sweep')}</dt><dd>{p.reminders.run_at} IST</dd>
        <dt>{t('Quiet hours')}</dt><dd>{p.quiet_hours.start}–{p.quiet_hours.end} IST ({p.quiet_hours.channels.join(', ')}; {t('not for overdue')})</dd>
        <dt>{t('Escalation chain')}</dt><dd>{p.escalation.chain.join(' → ')}, {t('every')} {p.escalation.step_after_days} {t('days')}; {t('holds')}: {p.escalation.hold_review_days} {t('days')}</dd>
      </dl>
      {d.data.editable ? (
        <>
          <div className="pol-form">
            <label>{t('Reminder windows (days before maturity)')}<input className="inp" value={before} onChange={(e) => setBefore(e.target.value)} /></label>
            <label>{t('Deadline rung within (days)')}<input className="inp num" type="number" min={1} value={deadline} onChange={(e) => setDeadline(Number(e.target.value))} /></label>
            <label>{t('Action-needed rung within (days)')}<input className="inp num" type="number" min={2} value={action} onChange={(e) => setAction(Number(e.target.value))} /></label>
          </div>
          <h3 className="small" style={{ marginTop: 14, color: 'var(--navy)' }}>{t('Before and after')}</h3>
          <DiffTable changes={changes} caption="Notification policy: values before and after this change" />
          <div className="pol-form">
            <label>{t('Reason for the change (required, recorded in the audit trail)')}<input className="inp" value={reason} onChange={(e) => setReason(e.target.value)} placeholder="e.g. circular AICTE/2026/14" /></label>
            <div><button className="btn btn-primary" disabled={!changes.length || reason.trim().length < 5} onClick={save}>{t('Publish new version')}</button></div>
          </div>
        </>
      ) : <p className="muted small">{t('Only AICTE officials can change the notification policy.')}</p>}
    </Panel>
  );
}

/** /l/:token — an action link from an e-mail, SMS or WhatsApp. It opens the record; it never acts on its own. */
export function LinkLanding() {
  const { token } = useParams();
  const { user, checking } = useStore();
  const resolving = useRef<string | null>(null);
  const nav = useNavigate();
  const t = useT();
  const [msg, setMsg] = useState<string | null>(null);
  useEffect(() => {
    if (checking) return;
    if (!user) {
      nav(`/login?next=${encodeURIComponent(`/l/${token}`)}`, { replace: true });
      return;
    }
    const requestKey = `${user.id}:${token}`;
    if (resolving.current === requestKey) return;
    resolving.current = requestKey;
    setMsg(null);
    post<{ path: string; step_up: string | null }>('/nudge/links/resolve', { token })
      .then((r) => nav(r.path + (r.step_up ? '?step_up=dsc' : ''), { replace: true }))
      .catch((e) => setMsg(errorText(e)));
  }, [checking, user, token, nav]);
  return (
    <main className="link-landing" id="main">
      <div className="card" style={{ padding: 24, maxWidth: 520, margin: '80px auto' }}>
        <h1 style={{ fontSize: 20 }}>{t('Opening your notice')}</h1>
        {msg ? <ErrorBox text={msg} /> : <Loading rows={2} />}
        {msg && <p><Link to="/login">{t('Sign in to the portal')}</Link></p>}
      </div>
    </main>
  );
}
