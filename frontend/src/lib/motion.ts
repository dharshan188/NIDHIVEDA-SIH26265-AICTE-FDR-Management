import { MotionGlobalConfig, type Transition, type Variants } from 'framer-motion';

/**
 * The one motion config. Components take durations, easing and stagger from here; there are no ad-hoc timings.
 * UI transitions stay at or under 350 ms. The longer chart timings (bars 600 ms, donut 800 ms, count-up 900 ms) are
 * data reveals that play once, on first view only.
 * Under prefers-reduced-motion every framer animation is skipped (MotionGlobalConfig.skipAnimations), CSS durations
 * drop to 0 (tokens.css), and count-ups render the final value at once.
 */
export const DUR = {
  fast: 0.15,
  base: 0.24, // route transition
  slow: 0.32, // modal / drawer
  bars: 0.6,
  donut: 0.8,
  count: 0.9,
  pulse: 0.6,
} as const;

export const EASE = {
  standard: [0.2, 0, 0, 1] as const,
  out: [0, 0, 0.2, 1] as const,
  inOut: [0.4, 0, 0.2, 1] as const,
};

export const STAGGER = 0.04;
export const SLIDE = 10; // px, route transition travel
export const REVEAL_Y = 16; // px, scroll reveal travel
export const PARALLAX_MAX = 12; // px

export const SPRING = {
  nav: { type: 'spring', stiffness: 420, damping: 38, mass: 0.9 } as Transition,
  layout: { type: 'spring', stiffness: 380, damping: 36 } as Transition,
};

export const T = {
  route: { duration: DUR.base, ease: EASE.standard } as Transition,
  fast: { duration: DUR.fast, ease: EASE.standard } as Transition,
  modal: { duration: DUR.slow, ease: EASE.standard } as Transition,
  item: { duration: DUR.base, ease: EASE.out } as Transition,
};

export const routeVariants: Variants = {
  initial: { opacity: 0, y: SLIDE },
  enter: { opacity: 1, y: 0, transition: T.route },
  exit: { opacity: 0, y: -SLIDE / 2, transition: { duration: DUR.fast, ease: EASE.standard } },
};

/** Container + child for the one-time dashboard reveal (summary cards rise in with a 40 ms stagger). */
export const revealList: Variants = { hidden: {}, show: { transition: { staggerChildren: STAGGER } } };
export const revealItem: Variants = {
  hidden: { opacity: 0, y: 12 },
  show: { opacity: 1, y: 0, transition: T.item },
};
/** Same shape as revealItem but already at rest: used after the first reveal so nothing re-animates on navigation. */
export const restItem: Variants = { hidden: { opacity: 1, y: 0 }, show: { opacity: 1, y: 0 } };

export const modalVariants: Variants = {
  initial: { opacity: 0, scale: 0.96 },
  enter: { opacity: 1, scale: 1, transition: T.modal },
  exit: { opacity: 0, scale: 0.98, transition: { duration: DUR.fast, ease: EASE.standard } },
};

// ---------------------------------------------------------------- reduced motion
const mq = typeof window !== 'undefined' && window.matchMedia ? window.matchMedia('(prefers-reduced-motion: reduce)') : null;

export function prefersReducedMotion() {
  return !!mq?.matches;
}

function apply() {
  MotionGlobalConfig.skipAnimations = prefersReducedMotion();
  document.documentElement.toggleAttribute('data-reduced-motion', prefersReducedMotion());
}

/** Call once at start-up. Keeps framer in step with the OS setting while the app is open. */
export function installMotionPreference() {
  if (!mq) return;
  apply();
  mq.addEventListener('change', apply);
}

// ---------------------------------------------------------------- "first view only" registry
/** Values already shown in this session, keyed by a stable id. Lets count-ups and chart reveals run once, then only
 *  animate the delta when the data changes (for example Pending 27 -> 28 after an upload). */
const seen = new Map<string, number>();
export const lastSeen = (id: string) => seen.get(id);
export const markSeen = (id: string, v: number) => seen.set(id, v);

const once = new Set<string>();
/** True the first time it is called with a key in this session. */
export function firstTime(key: string) {
  if (once.has(key)) return false;
  once.add(key);
  return true;
}
export const hasHappened = (key: string) => once.has(key);
