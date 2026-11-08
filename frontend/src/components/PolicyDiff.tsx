import { fmtDateTime } from '../lib/format';
import { useApi } from '../store/Store';
import { Empty, ErrorBox, Loading, Panel } from './ui';

export interface Change { path: string; before: unknown; after: unknown }

/** Leaf-level differences between two JSON values, the same rule as the server (portal_audit.changes). */
export function diffLeaves(a: unknown, b: unknown, path = ''): Change[] {
  const obj = (x: unknown): x is Record<string, unknown> => typeof x === 'object' && x !== null && !Array.isArray(x);
  if (obj(a) && obj(b)) {
    return [...new Set([...Object.keys(a), ...Object.keys(b)])].sort().flatMap((k) => diffLeaves(a[k], b[k], path ? `${path}.${k}` : k));
  }
  return JSON.stringify(a) === JSON.stringify(b) ? [] : [{ path, before: a, after: b }];
}

const show = (v: unknown) => (v === undefined || v === null ? '—' : typeof v === 'string' ? v : JSON.stringify(v));

export function DiffTable({ changes, caption }: { changes: Change[]; caption: string }) {
  if (!changes.length) return <p className="muted small" style={{ marginTop: 10 }}>No change yet: edit a value to see it here before publishing.</p>;
  return (
    <table className="diff">
      <caption className="sr-only">{caption}</caption>
      <thead><tr><th scope="col">Setting</th><th scope="col">Before</th><th scope="col">After</th></tr></thead>
      <tbody>
        {changes.map((c) => (
          <tr key={c.path}><td><code>{c.path}</code></td><td className="before">{show(c.before)}</td><td className="after">{show(c.after)}</td></tr>
        ))}
      </tbody>
    </table>
  );
}

interface PolicyChange { seq: number; hash: string; at: string; actor: string; policy: 'release' | 'notification'; version: number | null; reason: string; changes: Change[] | null; sections: string[] | null }

/** Every policy change, newest first, as recorded in the portal hash chain. */
export function PolicyHistory({ reload }: { reload: number }) {
  const d = useApi<{ items: PolicyChange[] }>('/policy/changes', [reload]);
  return (
    <Panel title="Policy change history" sub="From the hash-chained portal audit trail: who, when, why, and every value before and after">
      {d.error ? <ErrorBox text={d.error} /> : !d.data ? <Loading rows={3} /> : d.data.items.length === 0 ? <Empty text="No policy changes yet" hint="The defaults from the solution document are in force." /> : (
        <ol className="esc-list">
          {d.data.items.map((c) => (
            <li key={c.seq} className="card esc-card">
              <div className="esc-head">
                <b>{c.policy === 'release' ? 'Release policy' : 'Notification policy'}{c.version ? ` v${c.version}` : ''}</b>
                <span className="muted small">{fmtDateTime(c.at)} · {c.actor} · audit #{c.seq} · <code title={c.hash}>{c.hash.slice(0, 12)}…</code></span>
              </div>
              <p className="small" style={{ margin: '6px 0 0' }}>Reason: {c.reason}</p>
              {c.changes ? <DiffTable changes={c.changes} caption={`Changes in audit entry ${c.seq}`} />
                : <p className="muted small">Recorded before per-value history was kept; sections: {(c.sections ?? []).join(', ') || 'not listed'}.</p>}
            </li>
          ))}
        </ol>
      )}
    </Panel>
  );
}
