// S01 in the browser with four separate users, each in its own browser context, every action a click in the UI:
//   institution XYZ (OTP) requests release of its Rs 35 lakh online deposit -> section officer Kiran (TOTP) records scrutiny
//   -> deputy director Meera (TOTP) approves with DSC (SIMULATED issuer) -> finance officer Ravi (TOTP) initiates payment
//   -> SIMULATED bank debits (UTR) -> institution sees "NOT yet complete" -> SIMULATED return -> institution sees
//   "AICTE still owes you ₹35.00 lakh" -> Ravi re-issues -> debit -> SIMULATED positive credit confirmation -> "Completed".
// Asserts the institution never sees "Completed" before the credit confirmation. Screenshots to docs/screenshots/final/.
// Usage: node s01.mjs   (needs the dev servers from serve.py on a freshly seeded database)
import { mkdirSync } from 'node:fs';
import { BASE, apiFor, launch, newContext, open, settle, uiLogin, watchConsole } from './lib.mjs';

// SHOTS_DIR (absolute, trailing slash) writes elsewhere and leaves the recorded evidence screenshots untouched
const SHOTS = process.env.SHOTS_DIR ?? new URL('../../docs/screenshots/final/', import.meta.url).pathname;
mkdirSync(SHOTS, { recursive: true });
const OBLIGATION = 'ONL-XYZ-UG';
const errors = [];
const results = [];
const check = (name, ok, detail = '') => {
  results.push({ name, ok });
  console.log(`${ok ? 'PASS' : 'FAIL'} ${name}${detail ? ` :: ${detail}` : ''}`);
};

const browser = await launch();
async function user(who) {
  const ctx = await newContext(browser, { width: 1536, height: 1024 });
  const page = await ctx.newPage();
  watchConsole(page, errors, who);
  const { csrf, user: u } = await uiLogin(page, who);
  console.log(`signed in through the login page: ${u.username} (${u.role}${u.kernel_role ? ` / ${u.kernel_role}` : ''})`);
  return { ctx, page, api: apiFor(ctx, csrf), u };
}
const shot = (page, name) => page.screenshot({ path: `${SHOTS}${name}.png` });

const inst = await user('xyz');
const kiran = await user('kiran');
const meera = await user('aicte');
const ravi = await user('ravi');

// 1. institution raises the request
await open(inst.page, `${BASE}/institution/release`);
await settle(inst.page, 600);
await inst.page.getByRole('tab', { name: 'Online deposit (RTGS)' }).click();
await inst.page.locator('#rf').selectOption({ value: OBLIGATION });
await inst.page.locator('#rr').fill('Programme closed by AICTE order; refund of the security deposit requested (S01 browser run)');
await inst.page.getByRole('button', { name: 'Submit request' }).click();
await inst.page.getByText('Release request submitted').first().waitFor({ timeout: 15000 });
const req = (await inst.api.get('/release-requests?size=100')).items.find((r) => r.obligation_id === OBLIGATION && r.stage === 'SUBMITTED');
check('institution submitted the release request', !!req, req?.id);
const rid = req.id;

// 2. section officer: scrutiny (maker)
async function openCard(page, path) {
  await open(page, `${BASE}${path}`);
  await settle(page, 600);
  const head = page.getByRole('button', { name: new RegExp(rid) }).first();
  await head.click();
  return head;
}
await openCard(kiran.page, '/aicte/releases');
await kiran.page.getByRole('button', { name: 'Record scrutiny' }).click();
await kiran.page.locator('.modal textarea, [role=dialog] textarea').first().fill('Entitlement: programme closure order on file; Affidavit-6 in the prescribed format');
await kiran.page.getByRole('button', { name: 'Record', exact: true }).click();
await kiran.page.getByText('Scrutiny recorded').first().waitFor({ timeout: 15000 });
check('section officer recorded scrutiny', (await kiran.api.get(`/release-requests/${rid}`)).stage === 'SCRUTINY_DONE');

// 3. deputy director: gate preview, then DSC approval (checker; the SIMULATED DSC issuer signs in the dev build)
await openCard(meera.page, '/aicte/releases');
await meera.page.getByText('All checks pass').first().waitFor({ timeout: 15000 });
await shot(meera.page, 's01-1-release-gate');
await meera.page.getByRole('button', { name: 'Approve with DSC' }).click();
await meera.page.getByText(/approved with DSC/).first().waitFor({ timeout: 15000 });
const approved = await meera.api.get(`/release-requests/${rid}`);
check('deputy director approved with DSC', approved.stage === 'APPROVED' && !!approved.dsc_serial, approved.dsc_serial?.slice(0, 12));
const refund = approved.refund?.refund_id;
check('refund authorised for the approved request', !!refund, refund);

// 4. finance officer initiates; the SIMULATED bank debits and issues a UTR
const card = (page) => page.locator('article', { hasText: refund }).first();
async function payments(page, base) {
  await open(page, `${BASE}${base}/payments`);
  await settle(page, 600);
  await page.getByRole('tab', { name: /^All \(/ }).click();   // "Needs attention" hides settled payments
  await card(page).waitFor({ timeout: 15000 });
  await card(page).scrollIntoViewIfNeeded();
}
await payments(ravi.page, '/aicte');
await card(ravi.page).getByRole('button', { name: 'Initiate payment' }).click();
await ravi.page.getByText('Payment initiated').first().waitFor({ timeout: 15000 });
await card(ravi.page).getByRole('button', { name: 'Bank debits (issues UTR)' }).click();
await ravi.page.getByText(/debited the payment/).first().waitFor({ timeout: 15000 });

async function institutionSees() {
  await payments(inst.page, '/institution');
  return (await card(inst.page).locator('.pay-status').innerText()).trim();
}
let txt = await institutionSees();
check('after the bank debit the institution sees "NOT yet complete"', txt.includes('NOT yet complete'), txt);
check('...and not "Completed"', !/Completed/.test(txt));
await shot(inst.page, 's01-2-sent-not-complete');

// 5. the beneficiary bank returns the payment (SIMULATED return advice)
await payments(ravi.page, '/aicte');
await card(ravi.page).getByRole('button', { name: 'Bank returns payment' }).click();
await ravi.page.getByText('Return advice received').first().waitFor({ timeout: 15000 });
txt = await institutionSees();
check('after the return the institution sees "AICTE still owes you ₹35.00 lakh"', txt.includes('AICTE still owes you ₹35.00 lakh'), txt);
check('...and not "Completed"', !/Completed/.test(txt));
await shot(inst.page, 's01-3-returned-still-owed');

// 6. re-issue, debit again, then the positive credit confirmation
await payments(ravi.page, '/aicte');
await card(ravi.page).getByRole('button', { name: 'Re-issue' }).click();
await ravi.page.getByText('Re-issue initiated').first().waitFor({ timeout: 15000 });
await card(ravi.page).getByRole('button', { name: 'Bank debits (issues UTR)' }).click();
await ravi.page.getByText(/debited the payment/).first().waitFor({ timeout: 15000 });
txt = await institutionSees();
check('after the second debit the institution still sees "NOT yet complete"', txt.includes('NOT yet complete') && !/Completed/.test(txt), txt);
await payments(ravi.page, '/aicte');
await card(ravi.page).getByRole('button', { name: /Beneficiary bank confirms credit/ }).click();
await ravi.page.getByText('Positive credit confirmation received').first().waitFor({ timeout: 15000 });
txt = await institutionSees();
check('only after the positive credit confirmation the institution sees "Completed"', txt.startsWith('Completed'), txt);
await shot(inst.page, 's01-4-completed');
const final = await ravi.api.get(`/payments/${refund}`);
check('ledger state SETTLED with two attempts (one returned, one settled)',
  final.state === 'SETTLED' && final.attempts.length === 2 && final.attempts[0].status === 'RETURNED' && final.attempts[1].status === 'SETTLED',
  `${final.state}, attempts ${final.attempts.map((a) => a.status).join(' / ')}`);
const audit = await meera.api.post('/audit-trail/verify');
check('both hash chains verify after the run', audit.kernel_chain.valid && audit.portal_chain.valid);

for (const u of [inst, kiran, meera, ravi]) await u.ctx.close();
await browser.close();
const failed = results.filter((r) => !r.ok).length;
console.log(`\nS01 browser run: ${results.length - failed}/${results.length} checks passed; console errors: ${errors.length}`);
for (const e of errors.slice(0, 20)) console.log('  ' + e);
process.exit(failed || errors.length ? 1 : 0);
