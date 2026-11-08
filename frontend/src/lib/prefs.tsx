import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react';
import { HI } from './hi';

/** Per-viewer display preferences: theme and language. Stored in the browser only (they are conveniences, not records). */

export type ThemePref = 'system' | 'light' | 'dark';
export type Lang = 'en' | 'hi';

const read = (k: string) => {
  try {
    return localStorage.getItem(k);
  } catch {
    return null;
  }
};
const write = (k: string, v: string) => {
  try {
    localStorage.setItem(k, v);
  } catch {
    /* storage blocked: the choice lasts for this page only */
  }
};

const darkMq = typeof window !== 'undefined' && window.matchMedia ? window.matchMedia('(prefers-color-scheme: dark)') : null;

interface Ctx {
  themePref: ThemePref;
  theme: 'light' | 'dark';
  setThemePref: (t: ThemePref) => void;
  lang: Lang;
  setLang: (l: Lang) => void;
  t: (en: string) => string;
}

const PrefsCtx = createContext<Ctx | null>(null);

export function PrefsProvider({ children }: { children: ReactNode }) {
  const [themePref, setPref] = useState<ThemePref>(() => (read('tl.theme') as ThemePref) || 'system');
  const [osDark, setOsDark] = useState(() => !!darkMq?.matches);
  const [lang, setLangState] = useState<Lang>(() => (read('tl.lang') === 'hi' ? 'hi' : 'en'));

  useEffect(() => {
    if (!darkMq) return;
    const h = () => setOsDark(darkMq.matches);
    darkMq.addEventListener('change', h);
    return () => darkMq.removeEventListener('change', h);
  }, []);

  const theme: 'light' | 'dark' = themePref === 'system' ? (osDark ? 'dark' : 'light') : themePref;

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
  }, [theme]);

  useEffect(() => {
    document.documentElement.lang = lang;
  }, [lang]);

  const setThemePref = useCallback((t: ThemePref) => {
    write('tl.theme', t);
    setPref(t);
  }, []);
  const setLang = useCallback((l: Lang) => {
    write('tl.lang', l);
    setLangState(l);
  }, []);
  const t = useCallback((en: string) => (lang === 'hi' ? HI[en] ?? en : en), [lang]);

  const value = useMemo(() => ({ themePref, theme, setThemePref, lang, setLang, t }), [themePref, theme, setThemePref, lang, setLang, t]);
  return <PrefsCtx.Provider value={value}>{children}</PrefsCtx.Provider>;
}

export function usePrefs() {
  const c = useContext(PrefsCtx);
  if (!c) throw new Error('usePrefs outside provider');
  return c;
}

/** Shorthand for the translator. */
export const useT = () => usePrefs().t;
