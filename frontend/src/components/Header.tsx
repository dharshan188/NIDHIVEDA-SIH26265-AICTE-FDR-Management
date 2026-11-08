import { AnimatePresence, motion } from 'framer-motion';
import { Bell, Check, ChevronDown, CircleHelp, Clock, Command, FileText, Keyboard, Landmark, LogOut, Menu, Moon, Search, ShieldCheck, Sun, User } from 'lucide-react';
import { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { api, post } from '../api/client';
import type { Fdr, Institution, Notice, Paged } from '../api/types';
import logo from '../assets/aicte-logo.png';
import { groupByDay, relTime } from '../lib/format';
import { T } from '../lib/motion';
import { usePrefs } from '../lib/prefs';
import { useApi, useStore } from '../store/Store';
import { openPalette, openShortcuts } from './CommandPalette';
import { ROLE_META, type Role } from './nav';

function useOutside(ref: React.RefObject<HTMLElement | null>, fn: () => void) {
  useEffect(() => {
    const h = (e: MouseEvent) => ref.current && !ref.current.contains(e.target as Node) && fn();
    document.addEventListener('mousedown', h);
    return () => document.removeEventListener('mousedown', h);
  }, [ref, fn]);
}

const pop = { initial: { opacity: 0, y: -6, scale: 0.98 }, animate: { opacity: 1, y: 0, scale: 1 }, exit: { opacity: 0, y: -6, scale: 0.98 }, transition: T.fast };

export function Brand() {
  return (
    <div className="brand">
      <img src={logo} alt="AICTE logo" />
      <div className="brand-text">
        <div className="hi" lang="hi">अखिल भारतीय तकनीकी शिक्षा परिषद</div>
        <div className="en">All India Council for Technical Education</div>
        <div className="min">Ministry of Education, Government of India</div>
      </div>
    </div>
  );
}

/** EN / हिं switch and light / dark toggle; used in the app header and on the login page. */
export function PrefControls() {
  const { t, theme, setThemePref, lang, setLang } = usePrefs();
  return (
    <div className="pref-controls">
      <div className="lang-switch" role="group" aria-label={t('Language')}>
        <button aria-pressed={lang === 'en'} onClick={() => setLang('en')} lang="en">EN</button>
        <button aria-pressed={lang === 'hi'} onClick={() => setLang('hi')} lang="hi">हिं</button>
      </div>
      <button className="icon-btn" onClick={() => setThemePref(theme === 'dark' ? 'light' : 'dark')} aria-label={t('Toggle dark mode')} aria-pressed={theme === 'dark'} title={t('Toggle dark mode')}>
        {theme === 'dark' ? <Sun size={21} /> : <Moon size={21} />}
      </button>
    </div>
  );
}

interface Hit {
  kind: 'FDR' | 'Institution';
  id: string;
  label: string;
  hint: string;
  to: string;
  bucket?: Fdr['bucket'];
}

/** Notification centre: unread / all, grouped by day, each item marks itself read. */
function NotificationCentre({ role, onClose }: { role: Role; onClose: () => void }) {
  const { run } = useStore();
  const { t } = usePrefs();
  const nav = useNavigate();
  const [tab, setTab] = useState<'unread' | 'all'>('unread');
  const notices = useApi<{ unread: number; items: Notice[] }>('/notifications?limit=30');
  const items = (notices.data?.items ?? []).filter((n) => tab === 'all' || !n.read);
  return (
    <motion.div className="menu notif-pop" {...pop} role="dialog" aria-label={t('Notifications')}>
      <header>
        <span>{t('Notifications')}</span>
        <button onClick={() => run(() => post('/notifications/read'), t('Mark all as read'))} disabled={!notices.data?.unread}>{t('Mark all as read')}</button>
      </header>
      <div className="notif-tabs" role="tablist">
        {(['unread', 'all'] as const).map((k) => (
          <button key={k} role="tab" aria-selected={tab === k} className={tab === k ? 'on' : ''} onClick={() => setTab(k)}>
            {t(k === 'unread' ? 'Unread' : 'All')} {k === 'unread' && notices.data ? <span className="num">({notices.data.unread})</span> : null}
          </button>
        ))}
      </div>
      <div className="notif-scroll">
        {groupByDay(items).map((g) => (
          <section key={g.day} aria-label={t(g.day)}>
            <h3 className="notif-day">{t(g.day)}</h3>
            <ul>
              {g.items.map((n) => (
                <li key={n.id}>
                  <button className={`notif-item${n.read ? '' : ' unread'}`} onClick={() => !n.read && run(() => post(`/notifications/read?id=${n.id}`))}>
                    <span className="tone-dot" aria-hidden />
                    <span style={{ flex: 1, minWidth: 0 }}>
                      <b>{n.kind.replace(/_/g, ' ')}</b>
                      <span className="nt">{n.text}</span>
                      <time dateTime={n.at}>{relTime(n.at)}</time>
                    </span>
                    <span className="sr-only">{n.read ? t('Read') : t('Unread')}</span>
                    {!n.read && <Check size={15} aria-hidden className="mark" />}
                  </button>
                </li>
              ))}
            </ul>
          </section>
        ))}
        {notices.data && items.length === 0 && <div className="empty"><b>{t("You're all caught up")}</b></div>}
      </div>
      <button className="notif-all" onClick={() => { onClose(); nav(`${ROLE_META[role].base}/notifications`); }}>
        {t('View all notifications')}
      </button>
    </motion.div>
  );
}

export default function Header({ role, onBurger, menuOpen }: { role: Role; onBurger: () => void; menuOpen: boolean }) {
  const { user, logout } = useStore();
  const { t } = usePrefs();
  const nav = useNavigate();
  const meta = ROLE_META[role];
  const [open, setOpen] = useState<'notif' | 'user' | null>(null);
  const [q, setQ] = useState('');
  const [hits, setHits] = useState<Hit[]>([]);
  const [sel, setSel] = useState(0);
  const notifRef = useRef<HTMLDivElement>(null);
  const userRef = useRef<HTMLDivElement>(null);
  const searchRef = useRef<HTMLDivElement>(null);
  useOutside(notifRef, () => open === 'notif' && setOpen(null));
  useOutside(userRef, () => open === 'user' && setOpen(null));
  useOutside(searchRef, () => setQ(''));
  const unreadQ = useApi<{ unread: number }>('/notifications?limit=1');

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
        ...i.items.map((x) => ({ kind: 'Institution' as const, id: x.id, label: x.name, hint: `${x.city}, ${x.state}`, to: `${meta.base}/institutions/${x.id}` })),
        ...f.items.map((x) => ({ kind: 'FDR' as const, id: x.id, label: x.id, hint: `${x.institution_name} · ${x.bank_name}`, to: `${meta.base}/fdr/${x.id}`, bucket: x.bucket })),
      ]);
      setSel(0);
    }, 220);
    return () => clearTimeout(tm);
  }, [q, role, meta.base]);

  useEffect(() => {
    if (!open) return;
    const h = (e: KeyboardEvent) => e.key === 'Escape' && setOpen(null);
    window.addEventListener('keydown', h);
    return () => window.removeEventListener('keydown', h);
  }, [open]);

  const go = (h: Hit) => {
    setQ('');
    nav(h.to, h.bucket ? { state: { fdr: { id: h.id, bucket: h.bucket } } } : undefined);
  };
  const unread = unreadQ.data?.unread ?? 0;
  const who = user?.role === 'INSTITUTION' ? user.full_name : user?.full_name ?? meta.title;
  const sub = user?.role === 'INSTITUTION' ? `AICTE ID: ${user.username}` : user?.designation ?? meta.sub;

  return (
    <header className="app-header">
      <button className="icon-btn burger" onClick={onBurger} aria-label={t('Menu')} aria-expanded={menuOpen} aria-controls="side-menu"><Menu size={22} /></button>
      <Brand />
      <div className="v-div first" />
      <div className="product">
        <b>{t('NIDHIVEDA')}</b>
        <span>{t('Security Deposit & FDR Management Portal')}</span>
      </div>
      <div className="header-right">
        {role !== 'institution' && (
          <div className="search" ref={searchRef} role="search">
            <Search size={18} aria-hidden />
            <input
              id="global-search"
              aria-label={t('Search institutions and FDRs')}
              value={q}
              onChange={(e) => setQ(e.target.value)}
              placeholder={t(role === 'auditor' ? 'Search institution, FDR no., bank, status...' : 'Search institution, FDR no., bank, etc...')}
              onKeyDown={(e) => {
                if (e.key === 'ArrowDown') setSel((s) => Math.min(s + 1, hits.length - 1));
                if (e.key === 'ArrowUp') setSel((s) => Math.max(s - 1, 0));
                if (e.key === 'Enter' && hits[sel]) go(hits[sel]);
                if (e.key === 'Escape') setQ('');
              }}
            />
            <kbd className="search-kbd" aria-hidden>/</kbd>
            <AnimatePresence>
              {q.trim().length >= 2 && (
                <motion.div className="search-pop" {...pop} role="listbox" aria-label={t('Search')}>
                  {hits.length === 0 && <div className="empty" style={{ padding: 16 }}><b>{t('No matches')}</b></div>}
                  {(['Institution', 'FDR'] as const).map((k) => hits.some((r) => r.kind === k) && (
                    <div key={k} role="group" aria-label={k === 'FDR' ? t('FDR Records') : t('All Institutions')}>
                      <div className="grp" aria-hidden>{k === 'FDR' ? t('FDR Records') : t('All Institutions')}</div>
                      {hits.map((r, i) => r.kind === k && (
                        <button key={r.id} role="option" aria-selected={i === sel} className={i === sel ? 'on' : ''} onMouseEnter={() => setSel(i)} onClick={() => go(r)}>
                          {k === 'FDR' ? <FileText size={16} aria-hidden /> : <Landmark size={16} aria-hidden />}
                          <span>{r.label}</span>
                          <small>{r.hint}</small>
                        </button>
                      ))}
                    </div>
                  ))}
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        )}
        <button className="icon-btn palette-btn" onClick={openPalette} aria-label={`${t('Command palette')} (Ctrl+K)`} title={`${t('Command palette')} (Ctrl+K)`} data-tour="palette">
          <Command size={20} />
        </button>
        <PrefControls />
        <div style={{ position: 'relative' }} ref={notifRef} data-tour="notif">
          <button className="icon-btn" aria-label={`${t('Notifications')}, ${unread} ${t('Unread').toLowerCase()}`} aria-expanded={open === 'notif'} onClick={() => setOpen(open === 'notif' ? null : 'notif')}>
            <Bell size={23} strokeWidth={1.8} />
            {unread > 0 && <span className="badge-dot num" aria-hidden>{unread > 99 ? '99+' : unread}</span>}
          </button>
          <AnimatePresence>{open === 'notif' && <NotificationCentre role={role} onClose={() => setOpen(null)} />}</AnimatePresence>
        </div>
        <button className="icon-btn hide-sm" aria-label={t('Help and guidelines')} onClick={() => nav(role === 'institution' ? '/institution/help' : `${meta.base}/guidelines`)}>
          <CircleHelp size={23} strokeWidth={1.8} />
        </button>
        <div className="v-div hide-sm" style={{ margin: '16px 4px' }} />
        <div style={{ position: 'relative' }} ref={userRef}>
          <button className="user-chip" aria-haspopup="menu" aria-expanded={open === 'user'} onClick={() => setOpen(open === 'user' ? null : 'user')}>
            <span className="av" aria-hidden>{role === 'institution' ? <Landmark size={24} /> : <User size={26} fill="currentColor" strokeWidth={0} />}</span>
            <span className="who">
              <b>{who}</b>
              <span>{sub}</span>
            </span>
            <ChevronDown size={18} aria-hidden />
          </button>
          <AnimatePresence>
            {open === 'user' && (
              <motion.div className="menu" {...pop} role="menu">
                <div className="menu-note">{user?.username}</div>
                <div className="menu-note"><ShieldCheck size={15} aria-hidden /> {t('Two-factor session')}</div>
                <div className="menu-note"><Clock size={15} aria-hidden /> {t('Signs out after 15 min idle')}</div>
                <hr />
                {role === 'institution' && <button role="menuitem" onClick={() => { setOpen(null); nav('/institution/profile'); }}><User size={16} aria-hidden /> {t('My Profile')}</button>}
                <button role="menuitem" onClick={() => { setOpen(null); openShortcuts(); }}><Keyboard size={16} aria-hidden /> {t('Keyboard shortcuts')}</button>
                <button role="menuitem" className="danger" onClick={async () => { await logout(); nav('/login'); }}><LogOut size={16} aria-hidden /> {t('Sign out')}</button>
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </div>
    </header>
  );
}
