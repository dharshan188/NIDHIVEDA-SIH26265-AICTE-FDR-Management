import { AnimatePresence, animate, motion, useInView } from 'framer-motion';
import { AlertTriangle, ArrowRight, Check, ChevronRight, Info, Inbox, RotateCcw, X } from 'lucide-react';
import { useEffect, useId, useLayoutEffect, useRef, useState, type ReactNode } from 'react';
import { Link, useLocation } from 'react-router-dom';
import type { Bucket, FdrStatus } from '../api/types';
import { DUR, EASE, REVEAL_Y, T, firstTime, hasHappened, lastSeen, markSeen, modalVariants, prefersReducedMotion, restItem, revealItem, revealList } from '../lib/motion';
import { useT } from '../lib/prefs';
import { useStore } from '../store/Store';
import { NAV, ROLE_META, type Role } from './nav';

const fmtNum = (v: number, decimals: number, format?: (n: number) => string) =>
  format ? format(v) : v.toLocaleString('en-IN', { minimumFractionDigits: decimals, maximumFractionDigits: decimals });

/**
 * Counts up from 0 over 900 ms the first time a value is seen in this session; afterwards it shows the value at once,
 * and when the value changes it ticks from the old value to the new one and pulses once. Reduced motion: final value
 * immediately. Screen readers always get the final value.
 */
export function CountUp({ value, id, decimals = 0, format }: { value: number; id?: string; decimals?: number; format?: (n: number) => string }) {
  const ref = useRef<HTMLSpanElement>(null);
  const inView = useInView(ref, { once: true });
  const [start] = useState(() => {
    if (prefersReducedMotion()) return value;
    const prev = id ? lastSeen(id) : undefined;
    return prev ?? 0;
  });
  const shown = useRef(start);
  const [pulse, setPulse] = useState(0);
  useEffect(() => {
    if (!inView || !ref.current) return;
    const node = ref.current;
    const from = shown.current;
    if (id) markSeen(id, value);
    if (from === value || prefersReducedMotion()) {
      node.textContent = fmtNum(value, decimals, format);
      shown.current = value;
      return;
    }
    const isDelta = from !== 0;
    if (isDelta) setPulse((p) => p + 1);
    const ctl = animate(from, value, {
      duration: isDelta ? DUR.pulse : DUR.count,
      ease: EASE.out,
      onUpdate: (v) => {
        node.textContent = fmtNum(v, decimals, format);
        shown.current = v;
      },
      onComplete: () => {
        shown.current = value;
      },
    });
    return () => ctl.stop();
  }, [value, inView, decimals, format, id]);
  return (
    <span className={`num count${pulse ? ' pulse-once' : ''}`} key={pulse}>
      <span ref={ref} aria-hidden>{fmtNum(start, decimals, format)}</span>
      <span className="sr-only">{fmtNum(value, decimals, format)}</span>
    </span>
  );
}

const LABEL: Record<FdrStatus | Bucket | 'done', string> = {
  pending: 'Pending Verification', verified: 'Verified', active: 'Active', discrepancy: 'Discrepancy',
  maturing: 'Maturing', released: 'Released', closed: 'Closed', done: 'Completed',
};

export function StatusPill({ status, wrap, label, layoutId }: { status: FdrStatus | Bucket | 'done'; wrap?: boolean; label?: string; layoutId?: string }) {
  const t = useT();
  const icon = status === 'discrepancy' ? <X size={8} strokeWidth={4} /> : status === 'pending' ? <span className="pd-dot" /> : <Check size={8} strokeWidth={4} />;
  return (
    <motion.span layoutId={layoutId} className={`pill p-${status}${wrap ? ' wrap' : ''}`} transition={T.route}>
      {status !== 'done' && <span className="pd" aria-hidden>{icon}</span>}
      {label ?? t(LABEL[status])}
    </motion.span>
  );
}

export function ViewAll({ to, label = 'View All' }: { to: string; label?: string }) {
  const t = useT();
  return (
    <Link to={to} className="view-all">
      {t(label)} <ArrowRight size={16} aria-hidden />
    </Link>
  );
}

/**
 * Fades content up by 16 px when it scrolls into view, once. Content that is already on screen when the page opens is
 * left alone, so nothing visible ever appears late. Uses IntersectionObserver; native scrolling is never touched.
 */
export function useScrollReveal<T extends HTMLElement>() {
  const ref = useRef<T>(null);
  useLayoutEffect(() => {
    const el = ref.current;
    if (!el || prefersReducedMotion() || typeof IntersectionObserver === 'undefined') return;
    const top = el.getBoundingClientRect().top;
    if (top < window.innerHeight) return; // already visible: never hide it
    el.style.opacity = '0';
    el.style.transform = `translateY(${REVEAL_Y}px)`;
    const io = new IntersectionObserver(
      ([e]) => {
        if (!e.isIntersecting) return;
        io.disconnect();
        const a = el.animate([{ opacity: 0, transform: `translateY(${REVEAL_Y}px)` }, { opacity: 1, transform: 'none' }], {
          duration: DUR.base * 1000,
          easing: `cubic-bezier(${EASE.out.join(',')})`,
        });
        el.style.opacity = '';
        el.style.transform = '';
        a.onfinish = () => a.cancel();
      },
      { rootMargin: '0px 0px -8% 0px' },
    );
    io.observe(el);
    return () => {
      io.disconnect();
      el.style.opacity = '';
      el.style.transform = '';
    };
  }, []);
  return ref;
}

export function Panel({ title, sub, action, children, className = '', style, id }: { title?: ReactNode; sub?: ReactNode; action?: ReactNode; children: ReactNode; className?: string; style?: React.CSSProperties; id?: string }) {
  const ref = useScrollReveal<HTMLElement>();
  const hid = useId();
  const t = useT();
  return (
    <section ref={ref} className={`card panel ${className}`} style={style} id={id} aria-labelledby={title ? hid : undefined}>
      {(title || action) && (
        <div className="panel-head">
          <div>
            {title && <h2 className="panel-title" id={hid}>{typeof title === 'string' ? t(title) : title}</h2>}
            {sub && <p>{typeof sub === 'string' ? t(sub) : sub}</p>}
          </div>
          {action}
        </div>
      )}
      {children}
    </section>
  );
}

/** Kept for the dashboard cards: they rise in once, after sign-in. */
export const item = revealItem;
export const stagger = revealList;

/**
 * Container for the one-time reveal. The first Stagger shown after sign-in plays the reveal (summary cards rise in
 * with a 40 ms stagger); every later one renders at rest, so navigation never replays it.
 */
export function Stagger({ children, className, style }: { children: ReactNode; className?: string; style?: React.CSSProperties }) {
  const { user } = useStore();
  const [reveal] = useState(() => !!user && !prefersReducedMotion() && firstTime(`reveal:${user.username}`));
  return (
    <motion.div className={className} style={style} variants={reveal ? revealList : { hidden: {}, show: {} }} initial={reveal ? 'hidden' : false} animate="show">
      {children}
    </motion.div>
  );
}
export const revealPlayed = (username: string) => hasHappened(`reveal:${username}`);

export function Kpi({ icon, tone, label, value, sub, extra, onClick, compact, chevron }: { icon: ReactNode; tone: string; label: string; value: ReactNode; sub?: ReactNode; extra?: ReactNode; onClick?: () => void; compact?: boolean; chevron?: boolean }) {
  const t = useT();
  const body = (
    <>
      <div className={`kpi-ico t-${tone}`} aria-hidden>{icon}</div>
      <div style={{ minWidth: 0 }}>
        <div className="lbl">{t(label)}</div>
        <div className="val">{value}</div>
        {sub && <div className="sub">{sub}</div>}
        {extra}
      </div>
      {chevron && <ChevronRight className="chev" size={20} aria-hidden />}
    </>
  );
  return onClick ? (
    <motion.button type="button" className={`card kpi${compact ? ' compact' : ''}`} variants={item} onClick={onClick}>
      {body}
    </motion.button>
  ) : (
    <motion.div className={`card kpi static${compact ? ' compact' : ''}`} variants={item}>
      {body}
    </motion.div>
  );
}

export function Tabs<K extends string>({ tabs, value, onChange, id }: { tabs: { key: K; label: string }[]; value: K; onChange: (k: K) => void; id: string }) {
  const t = useT();
  return (
    <div className="tabs" role="tablist">
      {tabs.map((tb) => (
        <button key={tb.key} role="tab" aria-selected={value === tb.key} className={`tab${value === tb.key ? ' on' : ''}`} onClick={() => onChange(tb.key)}>
          {t(tb.label)}
          {value === tb.key && <motion.span layoutId={`tab-${id}`} className="tab-line" transition={{ type: 'spring', stiffness: 500, damping: 38 }} />}
        </button>
      ))}
    </div>
  );
}

export function DaysLeft({ days }: { days: number }) {
  const cls = days < 0 ? 'over' : days <= 5 ? 'd1' : days <= 15 ? 'd2' : days <= 30 ? 'd3' : days <= 40 ? 'd4' : 'd5';
  return <span className={`dl ${cls} num`}>{days < 0 ? `${-days}d over` : days}</span>;
}

const FOCUSABLE = 'a[href], button:not([disabled]), textarea:not([disabled]), input:not([disabled]), select:not([disabled]), [tabindex]:not([tabindex="-1"])';

/** Traps Tab inside `ref`, focuses the first control, and returns focus to whatever opened it on close. */
export function useFocusTrap(open: boolean, ref: React.RefObject<HTMLElement | null>, onClose?: () => void) {
  useEffect(() => {
    if (!open) return;
    const opener = document.activeElement as HTMLElement | null;
    const t = setTimeout(() => {
      const el = ref.current;
      if (!el) return;
      const first = el.querySelector<HTMLElement>('[data-autofocus]') ?? el.querySelector<HTMLElement>(FOCUSABLE);
      (first ?? el).focus();
    }, 0);
    const key = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && onClose) {
        e.stopPropagation();
        onClose();
        return;
      }
      if (e.key !== 'Tab' || !ref.current) return;
      const items = Array.from(ref.current.querySelectorAll<HTMLElement>(FOCUSABLE)).filter((x) => x.offsetParent !== null);
      if (!items.length) return;
      const first = items[0];
      const last = items[items.length - 1];
      if (e.shiftKey && document.activeElement === first) {
        e.preventDefault();
        last.focus();
      } else if (!e.shiftKey && document.activeElement === last) {
        e.preventDefault();
        first.focus();
      }
    };
    document.addEventListener('keydown', key, true);
    return () => {
      clearTimeout(t);
      document.removeEventListener('keydown', key, true);
      if (opener && document.contains(opener)) opener.focus();
    };
  }, [open, ref, onClose]);
}

/** Where the dialog should grow from: the centre of the control that opened it, as a fraction of the dialog box. */
function useOriginFromTrigger(open: boolean, ref: React.RefObject<HTMLElement | null>) {
  const [origin, setOrigin] = useState({ x: 0.5, y: 0.5 });
  const trigger = useRef<DOMRect | null>(null);
  if (open && !trigger.current && typeof document !== 'undefined') {
    const a = document.activeElement;
    trigger.current = a && a !== document.body ? a.getBoundingClientRect() : null;
  }
  if (!open) trigger.current = null;
  useLayoutEffect(() => {
    if (!open || !ref.current || !trigger.current) return;
    const m = ref.current.getBoundingClientRect();
    const tx = trigger.current.left + trigger.current.width / 2;
    const ty = trigger.current.top + trigger.current.height / 2;
    setOrigin({ x: Math.min(1, Math.max(0, (tx - m.left) / m.width)), y: Math.min(1, Math.max(0, (ty - m.top) / m.height)) });
  }, [open, ref]);
  return origin;
}

export function Modal({ open, onClose, title, sub, children, footer, width }: { open: boolean; onClose: () => void; title: string; sub?: string; children: ReactNode; footer?: ReactNode; width?: number }) {
  const ref = useRef<HTMLDivElement>(null);
  const t = useT();
  const hid = useId();
  useFocusTrap(open, ref, onClose);
  const origin = useOriginFromTrigger(open, ref);
  return (
    <AnimatePresence>
      {open && (
        <motion.div className="overlay" initial={{ opacity: 0 }} animate={{ opacity: 1, transition: T.fast }} exit={{ opacity: 0, transition: T.fast }} onMouseDown={onClose}>
          <motion.div
            ref={ref} className="modal" role="dialog" aria-modal="true" aria-labelledby={hid} tabIndex={-1}
            style={{ ...(width ? { width: `min(${width}px, 100%)` } : {}), originX: origin.x, originY: origin.y }}
            variants={modalVariants} initial="initial" animate="enter" exit="exit" onMouseDown={(e) => e.stopPropagation()}
          >
            <header>
              <div>
                <h2 id={hid}>{title}</h2>
                {sub && <p>{sub}</p>}
              </div>
              <button className="icon-btn" onClick={onClose} aria-label={t('Close')}><X size={18} /></button>
            </header>
            <div className="body">{children}</div>
            {footer && <footer>{footer}</footer>}
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}

export function Toasts() {
  const { toasts, dismissToast } = useStore();
  const t = useT();
  return (
    <div className="toasts" role="region" aria-label={t('Notifications')}>
      <div aria-live="polite" aria-atomic="false" style={{ display: 'contents' }}>
        <AnimatePresence initial={false}>
          {toasts.map((x) => (
            <motion.div key={x.id} className={`toast ${x.tone}`} layout initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0, transition: T.item }} exit={{ opacity: 0, transition: T.fast }}
              role={x.tone === 'error' ? 'alert' : 'status'}>
              {x.tone === 'success' ? <Check size={18} aria-hidden /> : x.tone === 'error' ? <AlertTriangle size={18} aria-hidden /> : <Info size={18} aria-hidden />}
              <span className="toast-text">{x.text}</span>
              {x.undo && (
                <button className="toast-undo" onClick={() => { x.undo?.(); dismissToast(x.id); }}>
                  <RotateCcw size={14} aria-hidden /> {t('Undo')}
                </button>
              )}
              <button className="toast-x" onClick={() => dismissToast(x.id)} aria-label={t('Dismiss')}><X size={16} /></button>
            </motion.div>
          ))}
        </AnimatePresence>
      </div>
    </div>
  );
}

/** Breadcrumb trail. Pages may pass their own; otherwise it is built from the route and the menu labels. */
export function Breadcrumbs({ crumbs }: { crumbs?: { label: string; to?: string }[] }) {
  const t = useT();
  const loc = useLocation();
  const parts = loc.pathname.split('/').filter(Boolean);
  const role = (parts[0] ?? 'aicte') as Role;
  const auto = (() => {
    if (!ROLE_META[role]) return [];
    const out: { label: string; to?: string }[] = [{ label: 'Dashboard', to: ROLE_META[role].base }];
    const navItem = NAV[role].find((n) => n.to && n.to === parts[1]);
    if (navItem) out.push({ label: navItem.label, to: parts.length > 2 ? `${ROLE_META[role].base}/${navItem.to}` : undefined });
    if (parts.length > 2) out.push({ label: decodeURIComponent(parts[parts.length - 1]) });
    return out;
  })();
  const list = crumbs ?? auto;
  if (list.length < 2) return null;
  return (
    <nav aria-label={t('Breadcrumb')} className="crumbs">
      <ol>
        {list.map((c, i) => (
          <li key={i}>
            {i > 0 && <ChevronRight size={13} aria-hidden />}
            {c.to && i < list.length - 1 ? <Link to={c.to}>{t(c.label)}</Link> : <span aria-current={i === list.length - 1 ? 'page' : undefined}>{t(c.label)}</span>}
          </li>
        ))}
      </ol>
    </nav>
  );
}

export function PageHead({ title, sub, crumbs, actions, titleNode }: { title: string; sub?: string; crumbs?: { label: string; to?: string }[]; actions?: ReactNode; titleNode?: ReactNode }) {
  const t = useT();
  return (
    <div className="page-head">
      <div>
        <Breadcrumbs crumbs={crumbs} />
        <h1>{titleNode ?? t(title)}</h1>
        {sub && <p>{t(sub)}</p>}
      </div>
      {actions && <div className="actions">{actions}</div>}
    </div>
  );
}

export function usePaged<R>(rows: R[], size = 12) {
  const [page, setPage] = useState(0);
  const pages = Math.max(1, Math.ceil(rows.length / size));
  useEffect(() => {
    setPage(0);
  }, [rows.length]);
  const slice = rows.slice(page * size, page * size + size);
  const pager = (
    <nav className="pager" aria-label="Pagination">
      <span>
        Showing {rows.length ? page * size + 1 : 0}–{Math.min(rows.length, (page + 1) * size)} of {rows.length.toLocaleString('en-IN')}
      </span>
      <div className="pg">
        <button disabled={page === 0} onClick={() => setPage(page - 1)} aria-label="Previous page">‹</button>
        {Array.from({ length: pages }, (_, i) => i)
          .filter((i) => i === 0 || i === pages - 1 || Math.abs(i - page) <= 1)
          .map((i, k, arr) => (
            <span key={i} style={{ display: 'contents' }}>
              {k > 0 && i - arr[k - 1] > 1 && <button disabled aria-hidden>…</button>}
              <button className={i === page ? 'on' : ''} aria-current={i === page ? 'page' : undefined} onClick={() => setPage(i)}>{i + 1}</button>
            </span>
          ))}
        <button disabled={page >= pages - 1} onClick={() => setPage(page + 1)} aria-label="Next page">›</button>
      </div>
    </nav>
  );
  return { slice, pager, offset: page * size };
}

/** Marks every place where bank data appears: all bank channels are simulated in this build. */
export function SimBadge({ title = 'All bank messages in this build come from the bank simulator, not a real bank.' }: { title?: string }) {
  return (
    <span className="sim-badge" title={title}>
      SIMULATED<span className="sr-only">: bank data from the simulator</span>
    </span>
  );
}

/** A feature that is designed but not built. Never a working control. */
export function PlannedBadge({ what }: { what?: string }) {
  const t = useT();
  return (
    <span className="planned-badge" title={what ? `${what}: planned, not built in this version` : 'Planned, not built in this version'}>
      {t('Planned')}
    </span>
  );
}

export function Planned({ label, note }: { label: string; note?: string }) {
  return (
    <div className="planned-row">
      <PlannedBadge what={label} />
      <span><b>{label}</b>{note && <> · {note}</>}</span>
    </div>
  );
}

/** One-sentence explanation behind an "i" button; opens on hover, focus or tap. */
export function InfoTip({ label, text }: { label: string; text: string }) {
  const [open, setOpen] = useState(false);
  const id = useId();
  return (
    <span className="infotip" onMouseEnter={() => setOpen(true)} onMouseLeave={() => setOpen(false)}>
      <button type="button" className="infotip-btn" aria-label={`What is ${label}?`} aria-describedby={open ? id : undefined} aria-expanded={open}
        onFocus={() => setOpen(true)} onBlur={() => setOpen(false)} onClick={() => setOpen((o) => !o)}
        onKeyDown={(e) => e.key === 'Escape' && setOpen(false)}>
        <Info size={14} aria-hidden />
      </button>
      {open && <span role="tooltip" id={id} className="infotip-pop">{text}</span>}
    </span>
  );
}

type SkelLayout = 'dashboard' | 'table' | 'detail' | 'list' | 'lines';

/** Loading skeletons shaped like the final layout, so the page does not jump when data arrives. */
export function Loading({ rows = 4, layout = 'lines' }: { rows?: number; layout?: SkelLayout }) {
  const t = useT();
  const bar = (w: string | number, h = 14, extra: React.CSSProperties = {}) => <div className="skeleton" style={{ width: w, height: h, ...extra }} />;
  let body: ReactNode;
  if (layout === 'dashboard') {
    body = (
      <>
        <div className="skel-hero">{bar('34%', 18)}{bar('48%', 32, { marginTop: 8 })}{bar('40%', 14, { marginTop: 8 })}</div>
        <div className="kpis skel-kpis">
          {Array.from({ length: 5 }, (_, i) => (
            <div key={i} className="card kpi static">
              <div className="skeleton" style={{ width: 56, height: 56, borderRadius: 12 }} />
              <div style={{ flex: 1 }}>{bar('70%', 12)}{bar('50%', 24, { marginTop: 8 })}{bar('60%', 12, { marginTop: 8 })}</div>
            </div>
          ))}
        </div>
        <div className="row g-aicte-mid">
          <div className="card panel">{bar('40%', 18)}<SkelTable rows={5} /></div>
          <div className="card panel">{bar('50%', 18)}{Array.from({ length: 4 }, (_, i) => <div key={i} className="skeleton" style={{ height: 48, marginTop: 8 }} />)}</div>
        </div>
      </>
    );
  } else if (layout === 'table') {
    body = <SkelTable rows={rows} />;
  } else if (layout === 'detail') {
    body = (
      <>
        <div style={{ padding: '24px 4px 16px' }}>{bar(180, 12)}{bar(260, 32, { marginTop: 8 })}{bar(320, 14, { marginTop: 8 })}</div>
        <div className="card panel">{bar('20%', 18)}<div className="skeleton" style={{ height: 220, marginTop: 12 }} /></div>
        <div className="row g-side" style={{ marginTop: 12 }}>
          <div className="card panel">{bar('40%', 18)}<SkelTable rows={5} /></div>
          <div className="card panel">{Array.from({ length: 8 }, (_, i) => <div key={i} className="skeleton" style={{ width: `${80 - (i % 3) * 15}%`, height: 14, marginTop: 12 }} />)}</div>
        </div>
      </>
    );
  } else if (layout === 'list') {
    body = Array.from({ length: rows }, (_, i) => <div key={i} className="skeleton" style={{ height: 56, marginTop: 8 }} />);
  } else {
    body = Array.from({ length: rows }, (_, i) => <div key={i} className="skeleton" style={{ height: 16, margin: '12px 0', width: `${90 - i * 8}%` }} />);
  }
  return (
    <div className="skel-block" role="status" aria-live="polite" aria-label={t('Loading')}>
      {body}
    </div>
  );
}

function SkelTable({ rows }: { rows: number }) {
  return (
    <div className="skel-table" aria-hidden>
      <div className="skeleton" style={{ height: 36 }} />
      {Array.from({ length: rows }, (_, i) => (
        <div key={i} className="skel-tr">
          {[6, 26, 18, 16, 14, 12].map((w, j) => <div key={j} className="skeleton" style={{ width: `${w}%`, height: 14 }} />)}
        </div>
      ))}
    </div>
  );
}

/** Error banner with a retry. Without an explicit handler, retry re-runs every request on the page. */
export function ErrorBox({ text, onRetry }: { text: string; onRetry?: () => void }) {
  const { refresh } = useStore();
  const t = useT();
  return (
    <div className="error-box" role="alert">
      <AlertTriangle size={18} aria-hidden />
      <span><b>{t('Something went wrong')}.</b> {text}</span>
      <button className="btn btn-ghost btn-sm" onClick={onRetry ?? refresh}>
        <RotateCcw size={14} aria-hidden /> {t('Retry')}
      </button>
    </div>
  );
}

export function Empty({ text, hint, icon }: { text: string; hint?: string; icon?: ReactNode }) {
  const t = useT();
  return (
    <div className="empty">
      <span className="empty-ico" aria-hidden>{icon ?? <Inbox size={22} />}</span>
      <b>{t(text)}</b>
      {hint && <span>{hint}</span>}
    </div>
  );
}

/** Container for list content that may be empty; renders an <li> so lists stay valid. */
export function EmptyLi({ text }: { text: string }) {
  return (
    <li style={{ listStyle: 'none' }}>
      <Empty text={text} />
    </li>
  );
}

export { restItem };
