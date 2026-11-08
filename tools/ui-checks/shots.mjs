// Screenshots at 1536x1024 into docs/screenshots/final/: login, the three dashboards, upload (checks, then encryption),
// FDR detail (documents with SHA-256 re-check; timeline with rule in force and renewal gap), notification centre,
// escalations, health, missing documents, the Rules page policy editor, and page 1 of a PDF export.
// Every figure on screen comes from the API; the upload goes through the real ClamAV and the encrypted object store.
// Usage: node shots.mjs   (needs the dev servers from serve.py)
import { execFileSync } from 'node:child_process';
import { mkdirSync, writeFileSync } from 'node:fs';
import { BASE, apiFor, launch, newContext, open, settle, uiLogin, watchConsole } from './lib.mjs';

// SHOTS_DIR (absolute, trailing slash) writes elsewhere and leaves the recorded evidence screenshots untouched
const OUT = process.env.SHOTS_DIR ?? new URL('../../docs/screenshots/final/', import.meta.url).pathname;
const TMP = new URL('../../.ui-check/shots/', import.meta.url).pathname;
mkdirSync(OUT, { recursive: true });
mkdirSync(TMP, { recursive: true });
const errors = [];
const taken = [];
const browser = await launch();

async function session(who) {
  const ctx = await newContext(browser, { width: 1536, height: 1024 });
  const page = await ctx.newPage();
  watchConsole(page, errors, who);
  const { csrf } = await uiLogin(page, who);
  return { ctx, page, api: apiFor(ctx, csrf) };
}
async function shot(page, name, path, { scrollTo, before } = {}) {
  if (path) {
    await open(page, `${BASE}${path}`);
    await settle(page, 1200);
  }
  if (before) await before(page);
  if (scrollTo) {
    await page.locator(scrollTo).first().evaluate((el) => el.scrollIntoView({ block: 'start' }));
    await page.evaluate(() => window.scrollBy(0, -90));   // keep the sticky header from covering the panel title
    await page.waitForTimeout(500);
  }
  await page.screenshot({ path: `${OUT}${name}.png` });
  taken.push(name);
  console.log(`saved ${name}.png`);
}
const panel = (title) => `section.panel:has(h2:text-is("${title}")), .panel:has(:is(h2,h3):text-is("${title}"))`;

/** A small, valid, unencrypted PDF (no scripts, forms or attachments). */
function makePdf(title) {
  const text = `${title} - test document for the NIDHIVEDA prototype (not a real FDR)`;
  const objs = ['<</Type/Catalog/Pages 2 0 R>>', '<</Type/Pages/Kids[3 0 R]/Count 1>>',
    '<</Type/Page/Parent 2 0 R/MediaBox[0 0 595 842]/Contents 4 0 R/Resources<</Font<</F1 5 0 R>>>>>>',
    null, '<</Type/Font/Subtype/Type1/BaseFont/Helvetica>>'];
  const stream = `BT /F1 14 Tf 60 760 Td (${text}) Tj ET`;
  objs[3] = `<</Length ${stream.length}>>\nstream\n${stream}\nendstream`;
  let body = '%PDF-1.4\n';
  const offs = [];
  objs.forEach((o, i) => { offs.push(body.length); body += `${i + 1} 0 obj\n${o}\nendobj\n`; });
  const xref = body.length;
  body += `xref\n0 ${objs.length + 1}\n0000000000 65535 f \n${offs.map((o) => `${String(o).padStart(10, '0')} 00000 n \n`).join('')}`;
  body += `trailer\n<</Size ${objs.length + 1}/Root 1 0 R>>\nstartxref\n${xref}\n%%EOF\n`;
  return Buffer.from(body, 'latin1');
}

// ---------------------------------------------------------------- signed out
{
  const ctx = await newContext(browser, { width: 1536, height: 1024 });
  const page = await ctx.newPage();
  watchConsole(page, errors, 'login');
  await open(page, `${process.env.UI_LOGIN_BASE ?? BASE}/login`);
  await settle(page, 900);
  await shot(page, '01-login');
  await ctx.close();
}

// ---------------------------------------------------------------- institution: dashboard, upload, notifications
const abc = await session('institution');
await shot(abc.page, '03-dashboard-institution', '/institution');
await open(abc.page, `${BASE}/institution/upload`);
await settle(abc.page, 800);
const no = `SBI-SHOT-${Date.now() % 1e6}`;
const today = new Date();
const iso = (d) => d.toISOString().slice(0, 10);
await abc.page.locator('#f-ref').fill(no);
await abc.page.locator('#f-bank').selectOption('SBI');
await abc.page.locator('#f-branch').fill('Coimbatore Main Branch');
await abc.page.locator('#f-amount').fill('3500000');
await abc.page.locator('#f-issue').fill(iso(new Date(today.getTime() - 5 * 864e5)));
await abc.page.locator('#f-maturity').fill(iso(new Date(today.getTime() + (3 * 365 + 5) * 864e5)));
await abc.page.getByRole('button', { name: 'Continue' }).click();
writeFileSync(`${TMP}FDR_scan_${no}.pdf`, makePdf(`Scanned FDR ${no}`));
writeFileSync(`${TMP}Lien_letter_${no}.pdf`, makePdf(`Bank lien letter for ${no}`));
await abc.page.locator('input[type=file]').setInputFiles([`${TMP}FDR_scan_${no}.pdf`, `${TMP}Lien_letter_${no}.pdf`]);
await abc.page.getByText('Ready to submit').nth(1).waitFor({ timeout: 30000 });
await shot(abc.page, '05-upload-checks-and-scan', null, { scrollTo: '.up-file' });
await abc.page.getByRole('button', { name: 'Continue' }).click();
await abc.page.locator('input.chk[type=checkbox]').check();
await abc.page.getByRole('button', { name: 'Submit for verification' }).click();
await abc.page.getByText('FDR submitted').waitFor({ timeout: 30000 });
await abc.page.waitForTimeout(600);
await shot(abc.page, '06-upload-encryption-status');
const fid = (await abc.api.get(`/fdrs?size=5&sort=submitted`)).items.find((f) => f.instrument_no === no)?.id;
console.log('uploaded', fid);
await shot(abc.page, '09-notification-centre', '/institution/notifications');

// ---------------------------------------------------------------- AICTE official
const aicte = await session('aicte');
// let the scheduled jobs run now (dev control) so the centre, health and escalations reflect current outbox rows
console.log('nudge run:', JSON.stringify(await aicte.api.post('/sim/nudge/run', { reminders: true, escalate: true, digest: true, deliver: true })).slice(0, 300));
await shot(aicte.page, '02-dashboard-aicte', '/aicte');
await shot(aicte.page, '07-fdr-detail-documents', `/aicte/fdr/${fid}`, {
  scrollTo: '.doc-list',
  before: async (p) => {
    await p.getByRole('button', { name: 'Check SHA-256 now' }).first().click();
    await p.getByText(/SHA-256 matches/).first().waitFor({ timeout: 15000 });
  },
});
// timeline: an FDR with a renewal gap, so the flag and the rule in force on each date are visible
const gaps = await aicte.api.get('/renewals/gaps');
const gapFdr = gaps.items.find((g) => g.kind === 'renewal_notice_missing')?.fdr_id ?? gaps.items[0]?.fdr_id ?? fid;
console.log(`renewal gaps: ${gaps.total}; timeline shot uses ${gapFdr}`);
const history = await aicte.api.get(`/fdrs/${gapFdr}/timeline`);
if (!gaps.total) console.log('NO RENEWAL GAP EXISTS in the live API result; no gap was created. Timeline screenshot is not gap proof.');
else if (!history.gaps?.length) throw new Error('selected FDR timeline has no actual renewal gap');
console.log('Timeline gap evidence:', JSON.stringify(history.gaps));
await shot(aicte.page, history.gaps?.length ? '08-fdr-detail-timeline' : '08-fdr-detail-timeline-no-gap', `/aicte/fdr/${gapFdr}`, {
  scrollTo: '.panel:has(.timeline)',
  before: async p => { if (history.gaps?.length) await p.getByText('Renewal gap', { exact: true }).first().waitFor(); },
});
await shot(aicte.page, '10-escalations', '/aicte/escalations');
await shot(aicte.page, '11-notification-health', '/aicte/notification-health');
await shot(aicte.page, '12-missing-documents', '/aicte/missing-documents');
await shot(aicte.page, '13-rules-policy-editor', '/aicte/rules', { scrollTo: '.pol-form' });

// PDF export: the missing-documents report, page 1 rendered to PNG at 1536x1024
const res = await aicte.ctx.request.get(`${BASE}/api/reports/missing-documents.pdf`, { headers: { 'X-TL-Client': 'web' } });
writeFileSync(`${TMP}missing-documents.pdf`, await res.body());
execFileSync('pdftoppm', ['-png', '-r', '110', '-f', '1', '-l', '1', '-singlefile', `${TMP}missing-documents.pdf`, `${TMP}missing-p1`]);
execFileSync('convert', [`${TMP}missing-p1.png`, '-resize', '1536x1024', '-background', '#e5e7eb', '-gravity', 'north', '-extent', '1536x1024', `${OUT}14-pdf-export-missing-documents.png`]);
taken.push('14-pdf-export-missing-documents');
console.log('saved 14-pdf-export-missing-documents.png');

// ---------------------------------------------------------------- auditor
const aud = await session('auditor');
await shot(aud.page, '04-dashboard-auditor', '/auditor');

for (const s of [abc, aicte, aud]) await s.ctx.close();
await browser.close();
const sizes = execFileSync('identify', ['-format', '%f %wx%h\n', ...taken.map((n) => `${OUT}${n}.png`)]).toString();
console.log(`\n${taken.length} screenshots:\n${sizes}console errors: ${errors.length}`);
for (const e of errors.slice(0, 20)) console.log('  ' + e);
process.exit(errors.length ? 1 : 0);
