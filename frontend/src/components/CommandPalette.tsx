import { AnimatePresence, motion } from 'framer-motion';
import { Command, CornerDownLeft, Database, FileText, Keyboard, Landmark, Languages, LogOut, Moon, RotateCcw, Search, Sun } from 'lucide-react';
import { useCallback, useEffect, useId, useMemo, useRef, useState, type ReactNode } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../api/client';
import type { Fdr, Institution, Paged } from '../api/types';
import { T, modalVariants } from '../lib/motion';
import { usePrefs } from '../lib/prefs';
import { useStore } from '../store/Store';
import { NAV, ROLE_META, type Role } from './nav';
import { useFocusTrap } from './ui';

const DEV = import.meta.env.DEV;

interface Item { id: string; group: 'Pages' | 'Institutions' | 'FDR Records' | 'Commands'; label: string; hint?: string; icon: ReactNode; run: () => void }

/** Opens the palette from anywhere (the header button dispatches this event). */
export const openPalette = () => window.dispatchEvent(new CustomEvent('tl:palette'));
export const openShortcuts = () => window.dispatchEvent(new CustomEvent('tl:shortcuts'));

const typing = (e: KeyboardEvent) => {
  const el = e.target as HTMLElement | null;
  return !!el && (el.isContentEditable || ['INPUT', 'TEXTAREA', 'SELECT'].includes(el.tagName));
};

export default function CommandPalette({ role }: { role: Role }) {
  const nav = useNavigate();
  const { t, theme, setThemePref, lang, setLang } = usePrefs();
  const { logout, toast } = useStore();
  const [open, setOpen] = useState(false);
  const [help, setHelp] = useState(false);
  const [q, setQ] = useState('');
  const [hits, setHits] = useState<Item[]>([]);
  const [sel, setSel] = useState(0);
  const box = useRef<HTMLDivElement>(null);
  const helpBox = useRef<HTMLDivElement>(null);
  const listId = useId();
  const base = ROLE_META[role].base;
  const fdrPage = role === 'aicte' ? 'submissions' : 'fdrs';

  const close = useCallback(() => {
    setOpen(false);
    setQ('');
  }, []);
  const closeHelp = useCallback(() => setHelp(false), []);
  useFocusTrap(open, box, close);
  useFocusTrap(help, helpBox, closeHelp);

  // ---- keyboard shortcuts: Ctrl/Cmd+K, "/", "?", "g d", "g f"
  useEffect(() => {
    let g = 0;
    const onKey = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault();
        setOpen((o) => !o);
        return;
      }
      if (typing(e) || e.altKey || e.ctrlKey || e.metaKey) return;
      if (e.key === '?') {
        e.preventDefault();
        setHelp(true);
      } else if (e.key === '/') {
        e.preventDefault();
        const s = document.querySelector<HTMLInputElement>('#global-search');
        if (s && s.offsetParent !== null) s.focus();
        else setOpen(true);
      } else if (e.key === 'g') {
        g = Date.now();
      } else if (Date.now() - g < 1200 && (e.key === 'd' || e.key === 'f')) {
        g = 0;
        nav(e.key === 'd' ? base : `${base}/${fdrPage}`);
      }
    };
    const onOpen = () => setOpen(true);
    const onHelp = () => setHelp(true);
    window.addEventListener('keydown', onKey);
    window.addEventListener('tl:palette', onOpen);
    window.addEventListener('tl:shortcuts', onHelp);
    return () => {
      window.removeEventListener('keydown', onKey);
      window.removeEventListener('tl:palette', onOpen);
      window.removeEventListener('tl:shortcuts', onHelp);
    };
  }, [nav, base, fdrPage]);

  const go = useCallback((to: string) => {
    close();
    nav(to);
  }, [close, nav]);

  const staticItems = useMemo<Item[]>(() => {
    const pages: Item[] = NAV[role].map((n) => ({ id: `p:${n.to}`, group: 'Pages', label: t(n.label), icon: n.icon, run: () => go(n.to ? `${base}/${n.to}` : base) }));
    const cmds: Item[] = [
      { id: 'c:theme', group: 'Commands', label: t('Toggle dark mode'), hint: theme === 'dark' ? t('Light') : t('Dark'), icon: theme === 'dark' ? <Sun size={18} /> : <Moon size={18} />, run: () => { setThemePref(theme === 'dark' ? 'light' : 'dark'); close(); } },
      { id: 'c:lang', group: 'Commands', label: t('Switch language'), hint: lang === 'hi' ? 'English' : 'हिन्दी', icon: <Languages size={18} />, run: () => { setLang(lang === 'hi' ? 'en' : 'hi'); close(); } },
      { id: 'c:keys', group: 'Commands', label: t('Keyboard shortcuts'), hint: '?', icon: <Keyboard size={18} />, run: () => { close(); setHelp(true); } },
      { id: 'c:out', group: 'Commands', label: t('Sign out'), icon: <LogOut size={18} />, run: async () => { close(); await logout(); nav('/login'); } },
    ];
    if (DEV) {
      // There is no reset endpoint (adding one would change the backend), so this hands over the seed command.
      cmds.push({
        id: 'c:reset', group: 'Commands', label: t('Reset demo data (dev build)'), hint: 'scripts/seed.py --reset', icon: <RotateCcw size={18} />,
        run: () => {
          const cmd = 'cd backend && ../.venv/bin/python scripts/seed.py --reset';
          navigator.clipboard?.writeText(cmd).catch(() => {});
          close();
          toast(`No reset API exists. Stop the backend and run: ${cmd} (copied)`, 'info');
        },
      });
    }
    return [...pages, ...cmds];
  }, [role, t, base, go, theme, lang, setThemePref, setLang, close, logout, nav, toast]);

  useEffect(() => {
    const s = q.trim();
    if (s.length < 2) {
      setHits([]);
      return;
    }
    const tm = setTimeout(async () => {
      const enc = encodeURIComponent(s);
      const [f, i] = await Promise.all([
        api<Paged<Fdr>>(`/fdrs?q=${enc}&size=6`).catch(() => ({ items: [] as Fdr[], total: 0 })),
        role === 'institution' ? Promise.resolve({ items: [] as Institution[], total: 0 }) : api<Paged<Institution>>(`/institutions?q=${enc}&size=5`).catch(() => ({ items: [] as Institution[], total: 0 })),
      ]);
      setHits([
        ...i.items.map((x): Item => ({ id: `i:${x.id}`, group: 'Institutions', label: x.name, hint: `${x.city}, ${x.state}`, icon: <Landmark size={18} />, run: () => go(`${base}/institutions/${x.id}`) })),
        ...f.items.map((x): Item => ({ id: `f:${x.id}`, group: 'FDR Records', label: x.id, hint: `${x.institution_name ?? ''} · ${x.bank_name}`, icon: <FileText size={18} />,
          run: () => { close(); nav(`${base}/fdr/${x.id}`, { state: { fdr: { id: x.id, bucket: x.bucket } } }); } })),
      ]);
    }, 180);
    return () => clearTimeout(tm);
  }, [q, role, base, go, close, nav]);

  const s = q.trim().toLowerCase();
  const items = [...staticItems.filter((x) => !s || x.label.toLowerCase().includes(s) || x.hint?.toLowerCase().includes(s)), ...hits];
  useEffect(() => setSel(0), [q, hits.length]);
  const groups = (['Pages', 'Institutions', 'FDR Records', 'Commands'] as const).filter((g) => items.some((x) => x.group === g));

  const onKey = (e: React.KeyboardEvent) => {
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setSel((v) => Math.min(v + 1, items.length - 1));
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setSel((v) => Math.max(v - 1, 0));
    } else if (e.key === 'Enter' && items[sel]) {
      e.preventDefault();
      items[sel].run();
    }
  };

  const SHORTCUTS: [string[], string][] = [
    [['Ctrl', 'K'], 'Open command palette'],
    [['/'], 'Focus search'],
    [['g', 'd'], 'Go to dashboard'],
    [['g', 'f'], 'Go to FDRs'],
    [['?'], 'Show this help'],
    [['Esc'], 'Close'],
  ];

  return (
    <>
      <AnimatePresence>
        {open && (
          <motion.div className="overlay palette-overlay" initial={{ opacity: 0 }} animate={{ opacity: 1, transition: T.fast }} exit={{ opacity: 0, transition: T.fast }} onMouseDown={close}>
            <motion.div ref={box} className="palette" role="dialog" aria-modal="true" aria-label={t('Command palette')} variants={modalVariants} initial="initial" animate="enter" exit="exit"
              onMouseDown={(e) => e.stopPropagation()}>
              <div className="palette-in">
                <Search size={18} aria-hidden />
                <input data-autofocus value={q} onChange={(e) => setQ(e.target.value)} onKeyDown={onKey} placeholder={t('Type a page, institution or FDR number')}
                  role="combobox" aria-expanded="true" aria-controls={listId} aria-autocomplete="list" aria-activedescendant={items[sel] ? `pi-${items[sel].id}` : undefined} aria-label={t('Command palette')} />
                <kbd>Esc</kbd>
              </div>
              <div className="palette-list" id={listId} role="listbox" aria-label={t('Command palette')}>
                {items.length === 0 && <div className="empty" style={{ padding: 24 }}><b>{t('No matches')}</b></div>}
                {groups.map((g) => (
                  <div key={g} role="group" aria-label={t(g)}>
                    <div className="palette-grp" aria-hidden>{t(g)}</div>
                    {items.map((x, i) => x.group === g && (
                      <div key={x.id} id={`pi-${x.id}`} role="option" aria-selected={i === sel} className={`palette-item${i === sel ? ' on' : ''}`}
                        onMouseEnter={() => setSel(i)} onClick={() => x.run()}>
                        <span className="pi-ico" aria-hidden>{x.icon}</span>
                        <span className="pi-label">{x.label}</span>
                        {x.hint && <small>{x.hint}</small>}
                        {i === sel && <CornerDownLeft size={14} aria-hidden className="pi-enter" />}
                      </div>
                    ))}
                  </div>
                ))}
              </div>
              <div className="palette-foot" aria-hidden>
                <span><kbd>↑</kbd><kbd>↓</kbd> move</span><span><kbd>Enter</kbd> open</span><span><Database size={12} /> searches the live API</span>
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
      <AnimatePresence>
        {help && (
          <motion.div className="overlay" initial={{ opacity: 0 }} animate={{ opacity: 1, transition: T.fast }} exit={{ opacity: 0, transition: T.fast }} onMouseDown={closeHelp}>
            <motion.div ref={helpBox} className="modal" style={{ width: 'min(440px, 100%)' }} role="dialog" aria-modal="true" aria-labelledby="kbd-h" tabIndex={-1}
              variants={modalVariants} initial="initial" animate="enter" exit="exit" onMouseDown={(e) => e.stopPropagation()}>
              <header>
                <div><h2 id="kbd-h"><Command size={18} aria-hidden style={{ verticalAlign: -3, marginRight: 8 }} />{t('Keyboard shortcuts')}</h2></div>
                <button className="icon-btn" onClick={closeHelp} aria-label={t('Close')} data-autofocus>✕</button>
              </header>
              <div className="body">
                <dl className="kbd-list">
                  {SHORTCUTS.map(([keys, what]) => (
                    <div key={what}>
                      <dt>{keys.map((k, i) => <span key={k}>{i > 0 && <span className="kbd-then">{keys[0] === 'g' ? 'then' : '+'}</span>}<kbd>{k}</kbd></span>)}</dt>
                      <dd>{t(what)}</dd>
                    </div>
                  ))}
                </dl>
                <p className="hint">On a Mac use ⌘ instead of Ctrl. Shortcuts are ignored while you type in a field.</p>
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </>
  );
}
