// Every PDF export that carries bank data must say SIMULATED. Downloads are made by clicking the export buttons in the
// browser (table exports, the missing-documents report, the evidence packet); text is read back with pdftotext.
// A table without bank data (audit events) is exported as a control: it must not be labelled SIMULATED.
// Usage: node pdf_check.mjs   (needs the dev servers from serve.py)
import { execFileSync } from 'node:child_process';
import { mkdirSync } from 'node:fs';
import { BASE, apiFor, launch, newContext, open, settle, uiLogin, watchConsole } from './lib.mjs';

const TMP = new URL('../../.ui-check/pdfs/', import.meta.url).pathname;
mkdirSync(TMP, { recursive: true });
const errors = [];
const results = [];
const browser = await launch();
const ctx = await newContext(browser, { width: 1536, height: 1024 });
const page = await ctx.newPage();
watchConsole(page, errors, 'aicte');
const { csrf } = await uiLogin(page, 'aicte');
const api = apiFor(ctx, csrf);

async function download(name, click) {
  const [dl] = await Promise.all([page.waitForEvent('download', { timeout: 30000 }), click()]);
  const path = `${TMP}${name}.pdf`;
  await dl.saveAs(path);
  const text = execFileSync('pdftotext', ['-layout', path, '-']).toString();
  const pages = Number(/Pages:\s+(\d+)/.exec(execFileSync('pdfinfo', [path]).toString())?.[1] ?? 0);
  return { path, text, pages };
}
function record(name, r, expectSim) {
  const has = /SIMULATED/.test(r.text);
  const line = r.text.split('\n').find((l) => /SIMULATED/.test(l))?.trim() ?? '';
  const ok = has === expectSim && r.pages > 0;
  results.push(ok);
  console.log(`${ok ? 'PASS' : 'FAIL'} ${name}: ${r.pages} page(s); SIMULATED ${has ? 'present' : 'absent'} (expected ${expectSim ? 'present' : 'absent'})${line ? ` :: "${line.slice(0, 140)}"` : ''}`);
}
const tablePdf = (label) => () => page.getByRole('button', { name: `Export PDF: ${label}` }).first().click();

const fdr = (await api.get('/fdrs?size=1&bucket=active')).items[0].id;
await open(page, `${BASE}/aicte/fdr/${fdr}`);
await settle(page, 1200);
record(`table export "Declared vs bank-confirmed, ${fdr}"`, await download('table-comparison', tablePdf(`Declared vs bank-confirmed, ${fdr}`)), true);
record(`evidence packet ${fdr}`, await download('evidence-packet', () => page.getByRole('button', { name: /Download PDF packet/ }).click()), true);

await open(page, `${BASE}/aicte/payments`);
await settle(page, 1200);
record('table export "Payment attempts"', await download('table-payments', tablePdf('Payment attempts')), true);

await open(page, `${BASE}/aicte/reconciliation`);
await settle(page, 1200);
record('table export "Bank messages"', await download('table-bank-messages', tablePdf('Bank messages')), true);
record('table export "Per-institution certification"', await download('table-certification', tablePdf('Per-institution certification')), true);

await open(page, `${BASE}/aicte/missing-documents`);
await settle(page, 1200);
record('missing-documents report (PDF button)', await download('missing-documents', () => page.getByRole('button', { name: 'PDF', exact: true }).click()), true);
record('table export "Missing documents"', await download('table-missing', tablePdf('Missing documents')), true);

await open(page, `${BASE}/aicte/audit-trail`);
await settle(page, 1200);
record('control: table export "Audit events" (no bank data)', await download('table-audit', tablePdf('Audit events')), false);

await ctx.close();
await browser.close();
const failed = results.filter((x) => !x).length;
console.log(`\nPDF exports: ${results.length - failed}/${results.length} as expected; console errors: ${errors.length}`);
for (const e of errors.slice(0, 10)) console.log('  ' + e);
process.exit(failed || errors.length ? 1 : 0);
