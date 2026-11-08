// axe-core WCAG 2 A/AA scan of every route for all three roles plus the login page.
// Usage: node axe.mjs [--theme dark] [--lang hi] [--reduced] [--width 1536]
import { readFileSync, writeFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import { BASE, PAGES, apiFor, launch, login, newContext, open, settle, watchConsole } from './lib.mjs';

const arg = (k, d) => {
  const i = process.argv.indexOf(`--${k}`);
  return i > 0 ? process.argv[i + 1] ?? true : d;
};
const theme = arg('theme', 'light');
const lang = arg('lang', 'en');
const reduced = process.argv.includes('--reduced');
const width = Number(arg('width', 1536));
const only = arg('only', '');
const AXE = readFileSync(createRequire(import.meta.url).resolve('axe-core/axe.min.js'), 'utf8');

const browser = await launch();
const errors = [];
const results = [];

async function scan(page, label) {
  await page.addScriptTag({ content: AXE });
  const r = await page.evaluate(async () => {
    // eslint-disable-next-line no-undef
    const out = await axe.run(document, { runOnly: { type: 'tag', values: ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa'] }, resultTypes: ['violations'] });
    return out.violations.map((v) => ({ id: v.id, impact: v.impact, help: v.help, nodes: v.nodes.slice(0, 4).map((n) => n.target.join(' ') + ' :: ' + (n.failureSummary ?? '').split('\n')[1]) }));
  });
  results.push({ label, violations: r });
  if (process.env.AXE_RESULT) writeFileSync(process.env.AXE_RESULT, JSON.stringify({ results, errors }, null, 2));
  console.log(`${r.length === 0 ? 'OK  ' : 'FAIL'} ${label}${r.length ? '  ' + r.map((v) => `${v.id}(${v.nodes.length})`).join(', ') : ''}`);
  for (const v of r) console.log(JSON.stringify(v));
}

// login page (signed out)
if (!only || only === '/login') {
  const ctx = await newContext(browser, { width, theme, lang, reducedMotion: reduced });
  const page = await ctx.newPage();
  watchConsole(page, errors, 'login');
  await open(page, `${BASE}/login`);
  await settle(page, 900);
  await scan(page, '/login');
  await ctx.close();
}

for (const role of ['aicte', 'institution', 'auditor']) {
  if (only && !only.startsWith(`/${role}`)) continue;
  const ctx = await newContext(browser, { width, theme, lang, reducedMotion: reduced });
  const { csrf } = await login(ctx, role);
  const api = apiFor(ctx, csrf);
  const fdrs = await api.get('/fdrs?size=1&bucket=active');
  const fdr = fdrs.items[0]?.id;
  const inst = role === 'institution' ? '' : (await api.get('/institutions?size=1')).items[0]?.id;
  const page = await ctx.newPage();
  watchConsole(page, errors, role);
  for (const p of PAGES[role]) {
    const path = `/${role}${p ? '/' + p.replace(':fdr', fdr).replace(':inst', inst) : ''}`;
    if (only && only !== path) continue;
    await open(page, `${BASE}${path}`);
    await settle(page, reduced ? 300 : 1200);
    await scan(page, path);
  }
  await ctx.close();
}
await browser.close();

const bad = results.filter((r) => r.violations.length);
console.log(`\naxe: theme=${theme} lang=${lang} reduced=${reduced} width=${width}: ${results.length} pages, ${bad.length} with violations, ${results.reduce((n, r) => n + r.violations.length, 0)} violations`);
for (const b of bad) for (const v of b.violations) console.log(`  ${b.label} ${v.id} [${v.impact}] ${v.help}\n    ${v.nodes.join('\n    ')}`);
console.log(`console errors: ${errors.length}`);
for (const e of errors.slice(0, 20)) console.log('  ' + e);
process.exit(bad.length || errors.length ? 1 : 0);
