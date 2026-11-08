import { createContext, useCallback, useContext, useEffect, useRef, useState, type ReactNode } from 'react';
import { api, errorText, onAuthError, post, setCsrf } from '../api/client';
import type { Role, User } from '../api/types';

/** Session state comes from the server (/api/auth/me). No financial data lives here. */

export interface Toast {
  id: number;
  tone: 'success' | 'error' | 'info';
  text: string;
  /** Present only when the action can really be reversed. */
  undo?: () => void;
}

export const TOAST_MS = 5000;

interface Ctx {
  user: User | null;
  checking: boolean;
  toasts: Toast[];
  version: number;
  toast: (text: string, tone?: Toast['tone'], opts?: { undo?: () => void }) => void;
  dismissToast: (id: number) => void;
  setUser: (u: User | null) => void;
  logout: (reason?: string) => Promise<void>;
  refresh: () => void;
  run: <T>(fn: () => Promise<T>, ok?: string) => Promise<T | undefined>;
}

const StoreCtx = createContext<Ctx | null>(null);

export const ROLE_BASE: Record<Role, string> = { AICTE_OFFICIAL: '/aicte', INSTITUTION: '/institution', AUDITOR: '/auditor' };

export function StoreProvider({ children }: { children: ReactNode }) {
  const [user, setUserState] = useState<User | null>(null);
  const [checking, setChecking] = useState(true);
  const [toasts, setToasts] = useState<Toast[]>([]);
  const [version, setVersion] = useState(0);
  const id = useRef(0);

  const dismissToast = useCallback((tid: number) => setToasts((t) => t.filter((x) => x.id !== tid)), []);

  const toast = useCallback((text: string, tone: Toast['tone'] = 'success', opts?: { undo?: () => void }) => {
    const tid = ++id.current;
    setToasts((t) => [...t.slice(-3), { id: tid, text, tone, undo: opts?.undo }]);
    setTimeout(() => setToasts((t) => t.filter((x) => x.id !== tid)), TOAST_MS);
  }, []);

  const setUser = useCallback((u: User | null) => {
    setCsrf(u?.csrf_token ?? '');
    setUserState(u);
  }, []);

  useEffect(() => {
    // The CSRF cookie is readable and is set together with the session cookie: without it there is no session to
    // look up, so skip the call (it would only log a 401 in the console).
    if (!document.cookie.split('; ').some((c) => c.startsWith('tl_csrf='))) {
      setUser(null);
      setChecking(false);
      return;
    }
    api<{ user: User }>('/auth/me')
      .then((r) => setUser(r.user))
      .catch(() => setUser(null))
      .finally(() => setChecking(false));
  }, [setUser]);

  useEffect(
    () =>
      onAuthError((e) => {
        setUser(null);
        if (e.message === 'session expired') toast('Session expired after 15 minutes of inactivity. Please sign in again.', 'info');
      }),
    [setUser, toast],
  );

  const logout = useCallback(
    async (reason?: string) => {
      try {
        await post('/auth/logout');
      } catch {
        /* already gone */
      }
      setUser(null);
      if (reason) toast(reason, 'info');
    },
    [setUser, toast],
  );

  const refresh = useCallback(() => setVersion((v) => v + 1), []);

  const run = useCallback(
    async <T,>(fn: () => Promise<T>, ok?: string) => {
      try {
        const r = await fn();
        if (ok) toast(ok);
        setVersion((v) => v + 1);
        return r;
      } catch (e) {
        toast(errorText(e), 'error');
        return undefined;
      }
    },
    [toast],
  );

  return <StoreCtx.Provider value={{ user, checking, toasts, version, toast, dismissToast, setUser, logout, refresh, run }}>{children}</StoreCtx.Provider>;
}

export function useStore() {
  const c = useContext(StoreCtx);
  if (!c) throw new Error('useStore outside provider');
  return c;
}

/** GET with loading / error state; refetches when `deps` change or after any successful mutation (run()). */
export function useApi<T>(path: string | null, deps: unknown[] = []) {
  const { version } = useStore();
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    if (!path) return;
    let live = true;
    setLoading(true);
    api<T>(path)
      .then((d) => {
        if (live) {
          setData(d);
          setError(null);
        }
      })
      .catch((e) => live && setError(errorText(e)))
      .finally(() => live && setLoading(false));
    return () => {
      live = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [path, version, ...deps]);
  return { data, error, loading };
}
