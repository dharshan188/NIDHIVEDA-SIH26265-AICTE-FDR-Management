// Shared helpers for the browser checks. Talks to the dev servers (vite :5173 -> backend :8000).
import { chromium } from 'playwright-core';
import { createHash } from 'node:crypto';
import { existsSync, mkdirSync, readFileSync, writeFileSync } from 'node:fs';

const FONT_CACHE = new URL('./.font-cache/', import.meta.url).pathname;
mkdirSync(FONT_CACHE, { recursive: true });

export const BASE = process.env.UI_BASE ?? 'http://localhost:5173';
export const PW = process.env.TL_DEMO_PASSWORD ?? 'UiCheck-Demo-2026';
export const CHROME = process.env.CHROME ?? '/usr/bin/google-chrome';

export const USERS = {
  aicte: { username: 'meera@aicte-india.org', role: 'AICTE_OFFICIAL', mfa: 'totp' },
  kiran: { username: 'kiran@aicte-india.org', role: 'AICTE_OFFICIAL', mfa: 'totp' },
  ravi: { username: 'ravi@aicte-india.org', role: 'AICTE_OFFICIAL', mfa: 'totp' },
  institution: { username: '1-12345678', role: 'INSTITUTION', mfa: process.env.TL_UI_INSTITUTION_MFA ?? 'otp' },
  xyz: { username: '1-xyz-demo', role: 'INSTITUTION', mfa: 'otp' },
  auditor: { username: 'auditor@aicte-india.org', role: 'AUDITOR', mfa: 'totp' },
};

export async function launch(opts = {}) {
  return chromium.launch({ executablePath: CHROME, headless: opts.headless ?? true, args: ['--disable-dev-shm-usage', ...(opts.args ?? [])] });
}

/** Per-viewer settings the app reads at start-up (theme, language), plus reduced motion via media emulation. */
export async function newContext(browser, { width = 1536, height = 1024, theme, lang, reducedMotion, video, mobile } = {}) {
  const ctx = await browser.newContext({
    viewport: { width, height },
    deviceScaleFactor: 1,
    colorScheme: theme === 'dark' ? 'dark' : 'light',
    reducedMotion: reducedMotion ? 'reduce' : 'no-preference',
    isMobile: !!mobile,
    hasTouch: !!mobile,
    ...(video ? { recordVideo: { dir: video, size: { width, height } } } : {}),
  });
  // Google Fonts are slow from this network: keep a disk copy so every run uses the same Inter / Noto files.
  await ctx.route(/fonts\.(googleapis|gstatic)\.com/, async (route) => {
    const url = route.request().url();
    const f = FONT_CACHE + createHash('sha1').update(url).digest('hex');
    if (existsSync(f)) {
      const meta = JSON.parse(readFileSync(f + '.json', 'utf8'));
      return route.fulfill({ status: 200, headers: meta, body: readFileSync(f) });
    }
    try {
      const res = await route.fetch({ timeout: 60000 });
      const body = await res.body();
      const headers = { 'content-type': res.headers()['content-type'] ?? 'application/octet-stream', 'access-control-allow-origin': '*' };
      writeFileSync(f, body);
      writeFileSync(f + '.json', JSON.stringify(headers));
      return route.fulfill({ status: res.status(), headers, body });
    } catch {
      return route.abort();
    }
  });
  await ctx.addInitScript(({ theme, lang }) => {
    try {
      if (theme) localStorage.setItem('tl.theme', theme);
      if (lang) localStorage.setItem('tl.lang', lang);
      if (!globalThis.__TL_TOUR__) sessionStorage.setItem('tl.tour.done', '1');
    } catch { /* storage blocked */ }
  }, { theme, lang });
  return ctx;
}

/** Signs in through the same API calls the login page makes, using the dev-only OTP outbox / TOTP helper. */
export async function login(ctx, who) {
  const u = USERS[who];
  const r = ctx.request;
  const h = { 'X-TL-Client': 'web' };
  let res = await r.post(`${BASE}/api/auth/login`, { headers: h, data: { username: u.username, password: PW, role: u.role } });
  if (!res.ok()) throw new Error(`login ${who}: ${res.status()} ${await res.text()}`);
  if (u.mfa === 'totp') {
    const { code } = await (await r.get(`${BASE}/api/sim/totp/${encodeURIComponent(u.username)}`, { headers: h })).json();
    res = await r.post(`${BASE}/api/auth/totp/verify`, { headers: h, data: { code } });
  } else {
    const sent = await r.post(`${BASE}/api/auth/otp/send`, { headers: h });
    if (!sent.ok()) throw new Error(`OTP send ${who}: ${sent.status()} ${await sent.text()}`);
    const { code } = await (await r.get(`${BASE}/api/sim/otp-outbox/${encodeURIComponent(u.username)}`, { headers: h })).json();
    res = await r.post(`${BASE}/api/auth/otp/verify`, { headers: h, data: { code } });
  }
  if (!res.ok()) throw new Error(`mfa ${who}: ${res.status()} ${await res.text()}`);
  const { user } = await res.json();
  return { csrf: user.csrf_token, user };
}

/** API client bound to a signed-in context (for driving a scenario step; the UI is then checked separately). */
export function apiFor(ctx, csrf) {
  const h = { 'X-TL-Client': 'web', 'X-CSRF-Token': csrf };
  const wrap = async (res) => {
    const t = await res.text();
    let j;
    try { j = JSON.parse(t); } catch { j = t; }
    if (!res.ok()) throw new Error(`${res.status()} ${t.slice(0, 300)}`);
    return j;
  };
  return {
    get: async (p) => wrap(await ctx.request.get(`${BASE}/api${p}`, { headers: h })),
    post: async (p, data = {}) => wrap(await ctx.request.post(`${BASE}/api${p}`, { headers: h, data })),
  };
}

/** Collects console errors and page errors for a page. */
export function watchConsole(page, sink, label = '') {
  page.on('console', (m) => {
    if (m.type() === 'error') sink.push(`${label} console: ${m.text()}`);
  });
  page.on('pageerror', (e) => sink.push(`${label} pageerror: ${e.message}`));
}

/** Waits until the page has no loading skeletons and fonts are ready. */
export async function settle(page, extra = 400) {
  await page.waitForLoadState('networkidle', { timeout: 8000 }).catch(() => {});
  await page.waitForFunction(() => !document.querySelector('.skel-block'), null, { timeout: 15000 }).catch(() => {});
  await page.evaluate(() => Promise.race([document.fonts?.ready, new Promise((r) => setTimeout(r, 8000))]));
  await page.waitForTimeout(extra);
}

/** goto without waiting for every font: the app is usable at DOMContentLoaded. */
export const open = (page, url) => page.goto(url, { waitUntil: 'domcontentloaded', timeout: 60000 });

export const PAGES = {
  aicte: ['', 'institutions', 'submissions', 'verification', 'reconciliation', 'renewals', 'releases', 'payments', 'audit-trail', 'reports', 'notifications', 'guidelines', 'rules', 'fdr/:fdr', 'institutions/:inst'],
  institution: ['', 'profile', 'fdrs', 'upload', 'renewals', 'release', 'payments', 'notifications', 'communication', 'guidelines', 'help', 'fdr/:fdr'],
  auditor: ['', 'assignments', 'institutions', 'fdrs', 'compliance', 'discrepancies', 'renewals', 'releases', 'payments', 'audit-trail', 'reports', 'notifications', 'guidelines', 'fdr/:fdr'],
};

const ROLE_TAB = { AICTE_OFFICIAL: 'AICTE Official', INSTITUTION: 'Institution', AUDITOR: 'Auditor' };
const ROLE_BASE = { AICTE_OFFICIAL: '/aicte', INSTITUTION: '/institution', AUDITOR: '/auditor' };

/** Signs in through the login page itself: role tab, user ID, password, 2FA method, then the code typed into the six boxes.
 * The code is read from the dev-only SIMULATED OTP outbox / authenticator helper, standing in for the user's phone. */
export async function uiLogin(page, who) {
  const u = USERS[who];
  const h = { 'X-TL-Client': 'web' };
  await open(page, `${BASE}/login`);
  await page.getByRole('tab', { name: ROLE_TAB[u.role] }).click();
  await page.locator('#uid').fill(u.username);
  await page.locator('#pw').fill(PW);
  await page.getByRole('radio', { name: u.mfa === 'otp' ? /^OTP/ : /Authenticator App/ }).click();
  await page.locator('button.lbtn[type=submit]').click();
  await page.getByRole('group', { name: 'Verification code' }).waitFor({ timeout: 20000 });
  const helper = u.mfa === 'otp' ? `/api/sim/otp-outbox/${encodeURIComponent(u.username)}` : `/api/sim/totp/${encodeURIComponent(u.username)}`;
  const { code } = await (await page.context().request.get(`${BASE}${helper}`, { headers: h })).json();
  for (let i = 0; i < 6; i++) await page.getByLabel(`Digit ${i + 1} of 6`).fill(code[i]);
  await page.locator('form button.lbtn[type=submit]').click().catch(() => {});
  await page.waitForURL((url) => url.pathname.startsWith(ROLE_BASE[u.role]), { timeout: 20000 });
  const me = await (await page.context().request.get(`${BASE}/api/auth/me`, { headers: h })).json();
  return { csrf: me.user.csrf_token, user: me.user };
}
