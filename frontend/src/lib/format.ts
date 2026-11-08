const DAY = 86_400_000;

export const startOfToday = () => {
  const d = new Date();
  d.setHours(0, 0, 0, 0);
  return d;
};

export const addDays = (d: Date, n: number) => new Date(d.getTime() + n * DAY);

export const daysBetween = (from: Date, to: Date) => Math.round((to.getTime() - from.getTime()) / DAY);

export const daysLeft = (iso: string) => daysBetween(startOfToday(), new Date(iso));

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

export const fmtDate = (iso: string | Date) => {
  const d = typeof iso === 'string' ? new Date(iso) : iso;
  return `${String(d.getDate()).padStart(2, '0')} ${MONTHS[d.getMonth()]} ${d.getFullYear()}`;
};

export const fmtTime = (iso: string | Date) => {
  const d = typeof iso === 'string' ? new Date(iso) : iso;
  let h = d.getHours();
  const ap = h >= 12 ? 'PM' : 'AM';
  h = h % 12 || 12;
  return `${String(h).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')} ${ap}`;
};

export const fmtDateTime = (iso: string | Date) => `${fmtDate(iso)}, ${fmtTime(iso)}`;

export const inr = (n: number) => `₹ ${Math.round(n).toLocaleString('en-IN')}`;

export const crore = (n: number) => (n / 1e7).toFixed(2);

export const pct = (part: number, total: number) => (total ? ((part / total) * 100).toFixed(1) : '0.0');

export const relTime = (iso: string) => {
  const s = Math.max(0, (Date.now() - new Date(iso).getTime()) / 1000);
  if (s < 60) return 'just now';
  if (s < 3600) return `${Math.floor(s / 60)} min ago`;
  if (s < 86400) return `${Math.floor(s / 3600)} hr ago`;
  const d = Math.floor(s / 86400);
  return d === 1 ? 'yesterday' : `${d} days ago`;
};

/** Money arrives from the API as integer paise. */
export const inrP = (paise: number) => inr(paise / 100);
export const croreP = (paise: number) => (paise / 1e9).toFixed(2);
export const lakhP = (paise: number) => (paise / 1e7).toFixed(2);

/** "Today", "Yesterday" or the date, for grouping lists by day. */
export const dayLabel = (iso: string) => {
  const d = new Date(iso);
  d.setHours(0, 0, 0, 0);
  const diff = daysBetween(d, startOfToday());
  return diff === 0 ? 'Today' : diff === 1 ? 'Yesterday' : fmtDate(d);
};

export function groupByDay<T extends { at: string }>(rows: T[]): { day: string; items: T[] }[] {
  const out: { day: string; items: T[] }[] = [];
  for (const r of rows) {
    const day = dayLabel(r.at);
    const g = out[out.length - 1];
    if (g && g.day === day) g.items.push(r);
    else out.push({ day, items: [r] });
  }
  return out;
}

/** The kernel writes amounts as "Rs 35.00 lakh"; on screen the currency word is shown as the symbol, the figure unchanged. */
export const rupeeText = (s: string) => s.replace(/\bRs (?=\d)/g, '₹');
