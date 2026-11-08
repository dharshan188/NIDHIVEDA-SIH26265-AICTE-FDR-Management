// Compare rendered values with direct SQLite queries, never with another API aggregate.
import { execFileSync } from 'node:child_process';
import { mkdirSync, writeFileSync } from 'node:fs';
import { BASE, launch, newContext, login, apiFor, open, settle, watchConsole } from './lib.mjs';

const DB = process.env.TL_UI_DB;
if (!DB) throw new Error('TL_UI_DB must identify the live UI database');
const OUT = process.env.TL_UI_EVIDENCE ?? new URL('../../docs/verification/session7/', import.meta.url).pathname;
mkdirSync(OUT, { recursive: true });
const results = [], errors = [];
function sql(query, params = []) {
  const code = 'import sqlite3,json,sys; c=sqlite3.connect(sys.argv[1]); c.row_factory=sqlite3.Row; print(json.dumps([dict(r) for r in c.execute(sys.argv[2],json.loads(sys.argv[3]))])); c.close()';
  return JSON.parse(execFileSync('python3', ['-c', code, DB, query, JSON.stringify(params)], { encoding: 'utf8' }));
}
function check(page, field, ui, database, query, params = []) {
  const ok = ui === database;
  const row = { page, field, ui, database, ok, query, params };
  results.push(row);
  console.log(`${ok ? 'PASS' : 'FAIL'} ${page}: ${field}; UI=${JSON.stringify(ui)}; SQL=${JSON.stringify(database)}\n  SQL: ${query}\n  params: ${JSON.stringify(params)}`);
  if (!ok) throw new Error(`Live-data mismatch on ${page}`);
}
const browser = await launch();
const officer = await newContext(browser, { width: 1536, height: 1024 });
const institution = await newContext(browser, { width: 1536, height: 1024 });
try {
  const off = await login(officer, 'aicte');
  const ins = await login(institution, 'institution');
  const api = apiFor(officer, off.csrf);
  const own = apiFor(institution, ins.csrf);
  const fdr = (await own.get('/fdrs?size=1')).items[0];
  const raised = await api.post(`/fdrs/${fdr.id}/observations`, { category: 'query', text: 'Session 7 live-data verification: please review the bank covering letter.' });
  console.log(`Created a real test observation ${raised.observation.id} on ${fdr.id}; the outbox generates a fresh user-bound action link.`);
  await api.post('/sim/nudge/run', { reminders: true, escalate: true, digest: true, deliver: true });
  const page = await institution.newPage(), op = await officer.newPage();
  watchConsole(page, errors, 'institution'); watchConsole(op, errors, 'officer');
  await open(page, `${BASE}/institution/notifications`); await settle(page, 1400);
  const uiOpen = Number(await page.locator('.ladder-step.rung-overdue .ls-count').innerText());
  const countQuery = "SELECT count(*) AS n FROM notifications WHERE rung='overdue' AND ack_at IS NULL AND audience IN ('institution:' || (SELECT institution_id FROM users WHERE username=?), 'user:' || (SELECT id FROM users WHERE username=?))";
  check('notification centre', 'open overdue notices', uiOpen, sql(countQuery, ['1-12345678', '1-12345678'])[0].n, countQuery, ['1-12345678', '1-12345678']);

  const families = await api.get('/nudge/escalations');
  if (!families.items.length) throw new Error('No real escalation family in the live database');
  const root = families.items[0].root_id;
  await open(op, `${BASE}/aicte/escalations`); await settle(op, 1400);
  await op.locator('.esc-card').first().waitFor();
  const steps = await op.locator('.esc-card').first().locator('.esc-step').count();
  const familyQuery = 'WITH RECURSIVE family(id) AS (SELECT id FROM notifications WHERE id=? UNION SELECT n.id FROM notifications n JOIN family f ON n.parent_id=f.id) SELECT count(*) AS n FROM family';
  check('escalation view', `steps in root ${root}`, steps, sql(familyQuery, [root])[0].n, familyQuery, [root]);

  const response = op.waitForResponse(r => r.url().includes('/api/nudge/health?days=30') && r.ok());
  await open(op, `${BASE}/aicte/notification-health`);
  const health = await (await response).json(); await settle(op, 1400);
  const notices = Number((await op.locator('.kpi').filter({ has: op.locator('.lbl', { hasText: /^Notices$/ }) }).locator('.val').innerText()).replaceAll(',', ''));
  const healthQuery = "SELECT count(*) AS n FROM notifications WHERE at>=? AND template IS NOT NULL AND template<>'digest'";
  check('health panel', 'notices in displayed 30-day window', notices, sql(healthQuery, [health.since])[0].n, healthQuery, [health.since]);

  const sentQuery = "SELECT count(*) AS n FROM notification_deliveries d JOIN notifications n ON n.id=d.notification_id WHERE n.at>=? AND n.template IS NOT NULL AND d.channel='email' AND d.status<>'digested' AND (d.sent_at IS NOT NULL OR d.status IN ('sent','delivered'))";
  const email = op.locator('tr').filter({has:op.locator('td',{hasText:'simulator-email'})}).first();
  const sent = Number((await email.locator('td').nth(3).innerText()).replaceAll(',',''));
  check('health panel', 'email sent counted exactly once per delivery', sent, sql(sentQuery,[health.since])[0].n, sentQuery,[health.since]);

  const lang = await page.getByLabel('Language of notices').inputValue();
  const langQuery = 'SELECT lang FROM users WHERE username=?';
  check('notification preferences panel (inside centre)', 'notice language', lang, sql(langQuery, ['1-12345678'])[0].lang, langQuery, ['1-12345678']);

  // Retrieve a real user-bound link already generated by the worker. Do not log the token.
  const uid = ins.user.id;
  const tokens = sql('SELECT id,path,used_at FROM action_tokens WHERE user_id=? AND used_at IS NULL ORDER BY created_at DESC', [uid]);
  const messages = sql("SELECT body FROM provider_sim_messages WHERE to_role='institution:INST0001' ORDER BY id DESC");
  let token, row;
  for (const candidate of tokens) {
    const body = messages.find(m => m.body.includes(candidate.id + '.'))?.body;
    token = body?.match(new RegExp(candidate.id + '\\.[0-9]+\\.[A-Za-z0-9_-]+'))?.[0];
    if (token) { row = candidate; break; }
  }
  if (!row) throw new Error('No unused real action link for this user');
  await open(page, `${BASE}/l/${token}`);
  await page.waitForURL(u => u.pathname === row.path, { timeout: 20000 });
  const pathQuery = 'SELECT path,used_at FROM action_tokens WHERE id=?';
  check('action-link page', 'successful destination path', new URL(page.url()).pathname, sql(pathQuery, [row.id])[0].path, pathQuery, [row.id]);
  if (!sql(pathQuery, [row.id])[0].used_at) throw new Error('Action link was not consumed');
  if (errors.length) throw new Error('Unexpected errors before intentional link reuse: ' + errors.join('\n'));
  await open(page, `${BASE}/l/${token}`);
  await page.getByText('this link has already been used', { exact: false }).waitFor();
  const usedQuery = 'SELECT used_at IS NOT NULL AS used FROM action_tokens WHERE id=?';
  check('action-link page', 'reuse is refused', true, Boolean(sql(usedQuery, [row.id])[0].used), usedQuery, [row.id]);
  // A 409 for the intentional reuse is expected; record it separately from unexpected browser errors.
  const unexpected = errors.filter(e => !e.includes('409'));
  console.log(`Live-data checks: ${results.length}/${results.length} passed; unexpected console errors: ${unexpected.length}; expected action-link reuse HTTP 409: ${errors.length - unexpected.length}`);
  if (unexpected.length) throw new Error(unexpected.join('\n'));
} finally {
  writeFileSync(`${OUT}live-data.json`, JSON.stringify({ database: DB, results, errors }, null, 2));
  await institution.close(); await officer.close(); await browser.close();
}
