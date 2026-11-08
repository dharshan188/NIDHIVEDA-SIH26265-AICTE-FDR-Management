import { motion } from 'framer-motion';
import { Bell, Clock3, Database, Home, LayoutGrid } from 'lucide-react';
import { useEffect, useState } from 'react';
import { Navigate, NavLink, useLocation, useOutlet } from 'react-router-dom';
import { api } from '../api/client';
import type { Paged } from '../api/types';
import sideDark from '../assets/side-dark.jpg';
import sideLight from '../assets/side-light.jpg';
import { fmtDateTime } from '../lib/format';
import { SPRING, routeVariants } from '../lib/motion';
import { useT } from '../lib/prefs';
import { ROLE_BASE, useApi, useStore } from '../store/Store';
import CommandPalette from './CommandPalette';
import Header from './Header';
import { NAV, ROLE_META, roleKey, type Role } from './nav';
import Tour from './Tour';
import { SimBadge } from './ui';

function Sidebar({ role, open, onNavigate }: { role: Role; open: boolean; onNavigate: () => void }) {
  const meta = ROLE_META[role];
  const t = useT();
  const light = role === 'institution';
  const notices = useApi<{ unread: number }>('/notifications?limit=1');
  const pending = useApi<Paged<unknown>>(role === 'aicte' ? '/fdrs?bucket=pending&size=1' : null);
  const disc = useApi<Paged<unknown>>(role === 'auditor' ? '/fdrs?bucket=discrepancy&size=1' : null);
  const counts = { pending: pending.data?.total ?? 0, discrepancy: disc.data?.total ?? 0, notices: notices.data?.unread ?? 0 };
  return (
    <aside className={`sidebar${light ? ' light' : ''}${open ? ' open' : ''}`} aria-label={t('Main navigation')} data-tour="nav">
      <nav>
        {NAV[role].map((n) => (
          <NavLink key={n.to} to={n.to ? `${meta.base}/${n.to}` : meta.base} end={!n.to} onClick={onNavigate} className={({ isActive }) => `nav-item${isActive ? ' active' : ''}`}>
            {({ isActive }) => (
              <>
                {isActive && <motion.span layoutId={`nav-${role}`} className="pill-bg" transition={SPRING.nav} />}
                <span aria-hidden style={{ display: 'grid' }}>{n.icon}</span>
                <span>{t(n.label)}</span>
                {n.badge && counts[n.badge] > 0 && (
                  <span className="nav-count num" aria-label={`${counts[n.badge]} items`}>{counts[n.badge] > 99 ? '99+' : counts[n.badge]}</span>
                )}
              </>
            )}
          </NavLink>
        ))}
      </nav>
      <div className="side-foot" aria-hidden>
        <img src={light ? sideLight : sideDark} alt="" />
        <p>
          {meta.tagline.map((l) => <span key={l} style={{ display: 'block' }}>{l}</span>)}
          <span className="tricolor"><i /><i /></span>
        </p>
      </div>
    </aside>
  );
}

/** Phone navigation (under 768 px): four destinations and "More", which opens the full menu. 44 px+ targets. */
function BottomNav({ role, onMore, menuOpen }: { role: Role; onMore: () => void; menuOpen: boolean }) {
  const t = useT();
  const base = ROLE_META[role].base;
  const fdrs = role === 'aicte' ? 'submissions' : 'fdrs';
  const third = role === 'institution' ? { to: 'upload', label: 'Upload New FDR', icon: <LayoutGrid size={22} /> } : { to: 'audit-trail', label: 'Audit Trail', icon: <LayoutGrid size={22} /> };
  const items = [
    { to: base, end: true, label: 'Home', icon: <Home size={22} /> },
    { to: `${base}/${fdrs}`, label: 'FDRs', icon: <Database size={22} /> },
    { to: `${base}/${third.to}`, label: third.label, icon: third.icon },
    { to: `${base}/notifications`, label: 'Alerts', icon: <Bell size={22} /> },
  ];
  return (
    <nav className="bottom-nav" aria-label={t('Main navigation')}>
      {items.map((i) => (
        <NavLink key={i.to} to={i.to} end={i.end} className={({ isActive }) => `bn-item${isActive ? ' on' : ''}`}>
          <span aria-hidden>{i.icon}</span>
          <span>{t(i.label)}</span>
        </NavLink>
      ))}
      <button className={`bn-item${menuOpen ? ' on' : ''}`} onClick={onMore} aria-expanded={menuOpen} aria-controls="side-menu">
        <span aria-hidden><LayoutGrid size={22} /></span>
        <span>{t('More')}</span>
      </button>
    </nav>
  );
}

/** On every page: when the figures were read (server clock, IST) and the newest bank message behind them. */
function DataAsOf({ path }: { path: string }) {
  const { version } = useStore();
  const t = useT();
  const [f, setF] = useState<{ data_as_of: string; last_bank_message_at: string | null } | null>(null);
  useEffect(() => {
    api<{ data_as_of: string; last_bank_message_at: string | null }>('/meta/freshness').then(setF).catch(() => setF(null));
  }, [path, version]);
  if (!f) return null;
  return (
    <p className="data-as-of" role="note">
      <Clock3 size={13} aria-hidden /> {t('Data as of')} {fmtDateTime(f.data_as_of)} IST · {t('every figure on this page is a live database query')}
      {' · '}{t('Last bank message')}: {f.last_bank_message_at ? fmtDateTime(f.last_bank_message_at) : t('none yet')} <SimBadge />
    </p>
  );
}

export default function AppShell({ role }: { role: Role }) {
  const { user, checking } = useStore();
  const loc = useLocation();
  const outlet = useOutlet();
  const [open, setOpen] = useState(false);

  useEffect(() => {
    window.scrollTo({ top: 0 });
    setOpen(false);
  }, [loc.pathname]);

  if (checking) return <div className="empty" role="status" style={{ paddingTop: 160 }}>Checking your session…</div>;
  if (!user) return <Navigate to="/login" replace state={{ from: loc.pathname }} />;
  if (roleKey(user.role) !== role) return <Navigate to={ROLE_BASE[user.role]} replace />;

  return (
    <div className="app">
      <a className="skip-link" href="#main">Skip to content</a>
      <Header role={role} onBurger={() => setOpen(!open)} menuOpen={open} />
      <div className={`shell${role === 'institution' ? ' light' : ''}`} id="side-menu">
        <Sidebar role={role} open={open} onNavigate={() => setOpen(false)} />
        {open && <div className="scrim" onClick={() => setOpen(false)} aria-hidden />}
        <main className="main" id="main" tabIndex={-1}>
          {/* One transition per navigation: fade + 10 px rise, 240 ms. The old page is replaced in the same render (no
              exit wait), which is also what lets a row's reference and status travel into the detail header. */}
          <motion.div key={loc.pathname} variants={routeVariants} initial="initial" animate="enter">
            {outlet}
          </motion.div>
          <DataAsOf path={loc.pathname} />
        </main>
      </div>
      <BottomNav role={role} onMore={() => setOpen(!open)} menuOpen={open} />
      <CommandPalette role={role} />
      <Tour role={role} />
    </div>
  );
}
