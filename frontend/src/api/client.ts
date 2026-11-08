/** Thin fetch wrapper: same-origin cookies, the client header, and the CSRF token on state-changing calls. */
let csrf = '';

export function setCsrf(token: string) {
  csrf = token;
}

export class ApiError extends Error {
  status: number;
  detail: unknown;
  constructor(status: number, detail: unknown) {
    super(typeof detail === 'string' ? detail : (detail as { message?: string })?.message ?? `Request failed (${status})`);
    this.status = status;
    this.detail = detail;
  }
}

type Listener = (e: ApiError) => void;
const authListeners = new Set<Listener>();
export const onAuthError = (fn: Listener) => {
  authListeners.add(fn);
  return () => {
    authListeners.delete(fn);
  };
};

export async function api<T = unknown>(path: string, init: RequestInit & { json?: unknown } = {}): Promise<T> {
  const method = (init.method ?? (init.json !== undefined ? 'POST' : 'GET')).toUpperCase();
  const headers = new Headers(init.headers);
  headers.set('X-TL-Client', 'web');
  if (method !== 'GET' && csrf) headers.set('X-CSRF-Token', csrf);
  let body = init.body;
  if (init.json !== undefined) {
    headers.set('Content-Type', 'application/json');
    body = JSON.stringify(init.json);
  }
  const res = await fetch(`/api${path}`, { ...init, method, headers, body, credentials: 'same-origin' });
  const text = await res.text();
  const data = text ? safeJson(text) : null;
  if (!res.ok) {
    const err = new ApiError(res.status, (data as { detail?: unknown })?.detail ?? data);
    if (res.status === 401 && !path.startsWith('/auth/')) authListeners.forEach((f) => f(err));
    throw err;
  }
  return data as T;
}

function safeJson(t: string) {
  try {
    return JSON.parse(t);
  } catch {
    return t;
  }
}

export const post = <T = unknown>(path: string, json: unknown = {}) => api<T>(path, { method: 'POST', json });

export function errorText(e: unknown): string {
  if (e instanceof ApiError) {
    const d = e.detail as { message?: string; problems?: string[]; decision?: { checks: { code: string; ok: boolean; detail: string }[] } } | string;
    if (typeof d === 'string') return d;
    if (d?.decision) return `${d.message ?? 'Blocked'}: ` + d.decision.checks.filter((c) => !c.ok).map((c) => `${c.code} (${c.detail})`).join('; ');
    if (d?.problems) return `${d.message}: ${d.problems.join('; ')}`;
    if (Array.isArray(d)) return (d as { msg: string }[]).map((x) => x.msg).join('; ');
    return d?.message ?? e.message;
  }
  return e instanceof Error ? e.message : String(e);
}

/** Fetches a file the API generates (PDF, CSV) with the session and CSRF headers, and hands it to the browser to save. */
export async function downloadFile(path: string, fallbackName: string, json?: unknown): Promise<void> {
  const headers = new Headers({ 'X-TL-Client': 'web' });
  if (json !== undefined) {
    headers.set('Content-Type', 'application/json');
    if (csrf) headers.set('X-CSRF-Token', csrf);
  }
  const res = await fetch(`/api${path}`, { method: json === undefined ? 'GET' : 'POST', headers, credentials: 'same-origin',
    body: json === undefined ? undefined : JSON.stringify(json) });
  if (!res.ok) {
    const text = await res.text();
    throw new ApiError(res.status, (safeJson(text) as { detail?: unknown })?.detail ?? text);
  }
  const name = /filename="([^"]+)"/.exec(res.headers.get('content-disposition') ?? '')?.[1] ?? fallbackName;
  const url = URL.createObjectURL(await res.blob());
  const a = document.createElement('a');
  a.href = url;
  a.download = name;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
