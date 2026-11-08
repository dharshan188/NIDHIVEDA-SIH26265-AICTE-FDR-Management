import { AnimatePresence, motion } from 'framer-motion';
import { useCallback, useEffect, useLayoutEffect, useRef, useState } from 'react';
import { useLocation } from 'react-router-dom';
import { T } from '../lib/motion';
import { useT } from '../lib/prefs';
import { ROLE_META, type Role } from './nav';
import { useFocusTrap } from './ui';

/**
 * First-sign-in tour, four steps at most, skippable.
 * Remembered for the browser session only (sessionStorage). The brief asks for the server profile; the backend has no
 * per-user preference store and the backend is frozen for this work, so that part is not done (see CHANGELOG).
 */
const STEPS: Record<Role, { target: string; title: string; text: string }[]> = {
  aicte: [
    { target: 'nav', title: 'Your work queues', text: 'Submissions, verification, releases and payments. Badges count items waiting for you.' },
    { target: 'kpis', title: 'Figures from the ledger', text: 'Every number comes from the database. Select a card to open the matching list.' },
    { target: 'palette', title: 'Find anything', text: 'Press Ctrl+K to jump to an institution, an FDR number or a page. Press ? for all shortcuts.' },
    { target: 'notif', title: 'Alerts', text: 'Bank returns, overdue confirmations and clarifications arrive here, grouped by day.' },
  ],
  institution: [
    { target: 'kpis', title: 'Your deposits', text: 'Totals for your FDRs. Values stay “institution declared” until the issuing bank confirms them.' },
    { target: 'nav', title: 'Upload, renew, release', text: 'Submit a new FDR, a renewal, or a release request from the menu.' },
    { target: 'palette', title: 'Find anything', text: 'Press Ctrl+K to jump to an FDR or a page. Press ? for all shortcuts.' },
    { target: 'notif', title: 'Alerts', text: 'Maturity reminders, clarifications and refund status updates arrive here.' },
  ],
  auditor: [
    { target: 'kpis', title: 'Read-only overview', text: 'Counts and values from the ledger. Select a card to open the records behind it.' },
    { target: 'nav', title: 'Audit work', text: 'Assignments, discrepancies, compliance and the audit trail are in the menu.' },
    { target: 'palette', title: 'Find anything', text: 'Press Ctrl+K to jump to an institution, an FDR number or a page.' },
    { target: 'notif', title: 'Alerts', text: 'Discrepancies, returns and anomalies arrive here, grouped by day.' },
  ],
};

const key = (role: Role) => `tl.tour.${role}`;
const seen = (role: Role) => {
  try {
    return sessionStorage.getItem(key(role)) === '1' || sessionStorage.getItem('tl.tour.done') === '1';
  } catch {
    return true;
  }
};
const remember = (role: Role) => {
  try {
    sessionStorage.setItem(key(role), '1');
  } catch {
    /* storage blocked: the tour simply ends */
  }
};

const visible = (el: Element | null): el is HTMLElement => {
  if (!el) return false;
  const r = (el as HTMLElement).getBoundingClientRect();
  return r.width > 0 && r.height > 0 && getComputedStyle(el).visibility !== 'hidden';
};

export default function Tour({ role }: { role: Role }) {
  const t = useT();
  const loc = useLocation();
  const onDash = loc.pathname === ROLE_META[role].base;
  const [active, setActive] = useState(false);
  const [i, setI] = useState(0);
  const [rect, setRect] = useState<DOMRect | null>(null);
  const card = useRef<HTMLDivElement>(null);

  const steps = STEPS[role].filter((s) => active && visible(document.querySelector(`[data-tour="${s.target}"]`)));
  const step = steps[i];

  useEffect(() => {
    if (!onDash || seen(role)) return;
    // start once the dashboard figures are on screen and the reveal has finished
    const tm = setInterval(() => {
      if (document.querySelector('[data-tour="kpis"]')) {
        clearInterval(tm);
        setTimeout(() => setActive(true), 700);
      }
    }, 200);
    return () => clearInterval(tm);
  }, [onDash, role]);

  const end = useCallback(() => {
    remember(role);
    setActive(false);
  }, [role]);
  useFocusTrap(active && !!step, card, end);

  useLayoutEffect(() => {
    if (!step) return;
    const el = document.querySelector(`[data-tour="${step.target}"]`);
    if (!visible(el)) return;
    el.scrollIntoView({ block: 'nearest' });
    const update = () => setRect(el.getBoundingClientRect());
    update();
    window.addEventListener('resize', update);
    window.addEventListener('scroll', update, true);
    return () => {
      window.removeEventListener('resize', update);
      window.removeEventListener('scroll', update, true);
    };
  }, [step]);

  useEffect(() => {
    if (!onDash && active) end();
  }, [onDash, active, end]);

  if (!active || !step || !rect) return null;
  const pad = 6;
  const below = rect.bottom + 220 < window.innerHeight;
  const left = Math.min(Math.max(16, rect.left), window.innerWidth - 356);
  const top = below ? rect.bottom + 12 : Math.max(16, rect.top - 12 - 200);
  const sideways = rect.height > window.innerHeight * 0.5;

  return (
    <AnimatePresence>
      <div className="tour-layer">
        <div className="tour-spot" style={{ left: rect.left - pad, top: rect.top - pad, width: rect.width + pad * 2, height: rect.height + pad * 2 }} aria-hidden />
        <motion.div ref={card} key={i} className="tour-card" role="dialog" aria-modal="true" aria-labelledby="tour-h" aria-describedby="tour-p"
          style={sideways ? { left: Math.min(rect.right + 16, window.innerWidth - 356), top: 120 } : { left, top }}
          initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0, transition: T.item }}>
          <span className="tour-step">{i + 1} / {steps.length}</span>
          <h2 id="tour-h">{t(step.title)}</h2>
          <p id="tour-p">{t(step.text)}</p>
          <div className="tour-actions">
            <button className="btn btn-ghost btn-sm" onClick={end}>{t('Skip tour')}</button>
            <span style={{ flex: 1 }} />
            {i > 0 && <button className="btn btn-ghost btn-sm" onClick={() => setI(i - 1)}>{t('Back')}</button>}
            <button className="btn btn-primary btn-sm" data-autofocus onClick={() => (i + 1 < steps.length ? setI(i + 1) : end())}>{t(i + 1 < steps.length ? 'Next' : 'Finish')}</button>
          </div>
        </motion.div>
      </div>
    </AnimatePresence>
  );
}
