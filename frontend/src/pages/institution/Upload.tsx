import { ArrowLeft, ArrowRight, Check, CheckCircle2, FileText, Loader2, ShieldCheck, Trash2, UploadCloud } from 'lucide-react';
import { useRef, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { api, errorText, post } from '../../api/client';
import type { ContentCheck, DocInfo, Fdr } from '../../api/types';
import { CheckList, EncChip, ScanChip } from '../../components/FdrPanels';
import { PageHead, Panel, Stagger, PlannedBadge } from '../../components/ui';
import { fmtDate, inr } from '../../lib/format';
import { useApi } from '../../store/Store';

const DEV = import.meta.env.DEV;
const STEPS = ['FDR details', 'Documents', 'Review & declare'];
const DOC_TYPES: [string, string][] = [['fdr_scan', 'Scanned FDR (both sides)'], ['lien_letter', 'Bank letter marking lien in favour of AICTE'],
  ['renewal_advice', 'Bank renewal / replacement advice'], ['other', 'Other supporting document']];
interface Pre { checks: ContentCheck[]; scan: { status: string; engine: string | null; signature: string | null }; sha256: string; accepted: boolean }
interface Picked { file: File; type: string; pre: Pre | null; err: string }
const BANKS: [string, string][] = [['SBI', 'State Bank of India'], ['HDFC', 'HDFC Bank'], ['ICICI', 'ICICI Bank'], ['CANARA', 'Canara Bank'], ['PNB', 'Punjab National Bank'],
  ['BOB', 'Bank of Baroda'], ['AXIS', 'Axis Bank'], ['UNION', 'Union Bank of India'], ['INDIAN', 'Indian Bank'], ['BOI', 'Bank of India'], ['KOTAK', 'Kotak Mahindra Bank'], ['IDBI', 'IDBI Bank']];

function samplePdf(title: string): File {
  // A minimal valid PDF, for dev-build demos only.
  const body = `%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 300 144]/Contents 4 0 R/Resources<</Font<</F1 5 0 R>>>>>>endobj\n4 0 obj<</Length 60>>stream\nBT /F1 12 Tf 20 100 Td (${title} - SAMPLE, not a real FDR) Tj ET\nendstream endobj\n5 0 obj<</Type/Font/Subtype/Type1/BaseFont/Helvetica>>endobj\ntrailer<</Root 1 0 R>>\n%%EOF`;
  return new File([body], `${title.replace(/\W+/g, '_')}.pdf`, { type: 'application/pdf' });
}

export default function Upload() {
  const nav = useNavigate();
  const [params] = useSearchParams();
  const renewalOf = params.get('renewal') || undefined;
  const old = useApi<{ fdr: Fdr }>(renewalOf ? `/fdrs/${renewalOf}` : null);
  const [step, setStep] = useState(0);
  const [form, setForm] = useState({ ref: '', bank: '', branch: '', amount: '', rate: '7.10', issue: '', maturity: '' });
  const [files, setFiles] = useState<Picked[]>([]);
  const [over, setOver] = useState(false);
  const [agree, setAgree] = useState(false);
  const [touched, setTouched] = useState(false);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState('');
  const [rule, setRule] = useState('');
  const [done, setDone] = useState<{ fdr: Fdr; documents: DocInfo[] } | null>(null);
  const input = useRef<HTMLInputElement>(null);

  const set = (k: keyof typeof form) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => setForm({ ...form, [k]: e.target.value });
  const amt = Number(form.amount.replace(/,/g, ''));
  const tenure = form.issue && form.maturity ? (new Date(form.maturity).getTime() - new Date(form.issue).getTime()) / 864e5 : 0;
  const errs: Record<string, string> = {};
  if (!form.ref.trim()) errs.ref = 'FDR number is required';
  if (!form.bank) errs.bank = 'Select the issuing bank';
  if (!form.branch.trim()) errs.branch = 'Branch is required';
  if (!amt || amt < 2000000) errs.amount = 'Minimum prescribed amount is ₹ 20,00,000';
  if (!form.issue) errs.issue = 'Issue date is required';
  else if (new Date(form.issue) > new Date()) errs.issue = 'Issue date cannot be in the future';
  if (!form.maturity) errs.maturity = 'Maturity date is required';
  else if (tenure < 3 * 365 - 5) errs.maturity = 'Tenure must be at least 3 years';

  const go = async (n: number) => {
    setErr('');
    if (n > step && step === 0) {
      if (Object.keys(errs).length) return setTouched(true);
      if (renewalOf && !rule) {
        try {
          const r = await post<{ outcome: string }>(`/fdrs/${renewalOf}/renewal-check`, { new_number: form.ref, new_maturity: form.maturity });
          setRule(r.outcome);
        } catch (e) {
          return setErr(errorText(e));
        }
      }
    }
    setStep(n);
  };

  // Every file goes through the server's own content checks and malware scan as soon as it is chosen; nothing is stored
  // until the FDR is submitted. A file that fails is shown with the reason and cannot be submitted.
  const addFiles = (list: FileList | File[] | null) => {
    if (!list) return;
    setErr('');
    const added: Picked[] = [...list].map((file, i) => ({ file, pre: null, err: '',
      type: (() => { const n = files.length + i; return n === 0 ? 'fdr_scan' : n === 1 ? 'lien_letter' : renewalOf && n === 2 ? 'renewal_advice' : 'other'; })() }));
    setFiles((fs) => [...fs, ...added]);
    added.forEach(async (pk) => {
      const fd = new FormData();
      fd.set('file', pk.file);
      try {
        const pre = await api<Pre>('/documents/precheck', { method: 'POST', body: fd });
        setFiles((fs) => fs.map((x) => (x === pk || x.file === pk.file ? { ...x, pre } : x)));
      } catch (e) {
        setFiles((fs) => fs.map((x) => (x.file === pk.file ? { ...x, err: errorText(e) } : x)));
      }
    });
  };
  const types = files.map((f) => f.type);
  const docsReady = files.length >= 2 && files.every((f) => f.pre?.accepted) && types.includes('fdr_scan') && types.includes('lien_letter');

  const submit = async () => {
    setBusy(true);
    setErr('');
    const fd = new FormData();
    fd.set('bank', form.bank);
    fd.set('branch', form.branch);
    fd.set('instrument_no', form.ref);
    fd.set('amount_rupees', String(amt));
    fd.set('rate_bp', String(Math.round(Number(form.rate) * 100)));
    fd.set('issue_date', form.issue);
    fd.set('maturity_date', form.maturity);
    if (renewalOf) fd.set('renewal_of', renewalOf);
    files.forEach((f) => {
      fd.append('files', f.file);
      fd.append('doc_types', f.type);
    });
    try {
      const r = await api<{ fdr: Fdr; documents: DocInfo[] }>('/fdrs', { method: 'POST', body: fd });
      setDone(r);
    } catch (e) {
      setErr(errorText(e));
    } finally {
      setBusy(false);
    }
  };

  const F = (k: string, label: string, child: React.ReactNode, hint?: string) => (
    <div>
      <label className="lb" htmlFor={`f-${k}`}>{label} <em>*</em></label>
      {child}
      {touched && errs[k] ? <div className="err" id={`e-${k}`} role="alert">{errs[k]}</div> : hint ? <div className="hint">{hint}</div> : null}
    </div>
  );

  if (done) {
    return (
      <div className="card" style={{ maxWidth: 760, margin: '40px auto', padding: '36px 34px', textAlign: 'center' }} role="status">
        <CheckCircle2 size={56} color="var(--green)" aria-hidden />
        <h2 style={{ marginTop: 18, color: 'var(--navy)', fontSize: 24 }}>{renewalOf ? 'Renewal FDR submitted' : 'FDR submitted'}</h2>
        <p className="muted" style={{ marginTop: 8 }}>Reference <b style={{ color: 'var(--navy)' }}>{done.fdr.id}</b> is with the Regulation Bureau. It stays “institution declared” until {done.fdr.bank_name} confirms it.</p>
        <div style={{ textAlign: 'left', marginTop: 18 }}>
          {done.documents.map((x) => (
            <div key={x.id} className="up-file">
              <div className="up-file-head"><FileText size={18} color="var(--red)" aria-hidden /><span className="name">{x.name}</span><span className="muted small">{x.doc_type_label}</span></div>
              <div className="ln-chips"><ScanChip scan={x.scan} /><EncChip enc={x.encryption} /></div>
              <div className="sha"><span className="muted small">SHA-256</span> <code>{x.sha256}</code></div>
            </div>
          ))}
        </div>
        <div style={{ display: 'flex', gap: 10, justifyContent: 'center', marginTop: 22 }}>
          <button className="btn btn-ghost" onClick={() => nav('/institution')}>Back to dashboard</button>
          <button className="btn btn-primary" onClick={() => nav(`/institution/fdr/${done.fdr.id}`)}>Track this FDR <ArrowRight size={17} aria-hidden /></button>
        </div>
      </div>
    );
  }

  return (
    <Stagger>
      <PageHead title={renewalOf ? 'Submit renewal / replacement FDR' : 'Upload new FDR'}
        sub={old.data ? `Replacing ${old.data.fdr.id} (${old.data.fdr.bank_name}, matures ${fmtDate(old.data.fdr.maturity_date)})` : 'A Fixed Deposit Receipt pledged in favour of the Member Secretary, AICTE'}
        crumbs={[{ label: 'Dashboard', to: '/institution' }, { label: renewalOf ? 'Renewal' : 'Upload new FDR' }]} />
      <Panel>
        <ol style={{ display: 'flex', margin: '4px 0 26px', padding: 0, listStyle: 'none' }} aria-label="Steps">
          {STEPS.map((s, i) => (
            <li key={s} style={{ flex: 1, display: 'flex', alignItems: 'center', gap: 12 }} aria-current={i === step ? 'step' : undefined}>
              <span style={{ width: 34, height: 34, borderRadius: '50%', display: 'grid', placeItems: 'center', fontWeight: 700, flex: 'none', fontSize: 14, background: i < step ? 'var(--green)' : i === step ? 'var(--primary)' : 'var(--c-fg-e6ebf2)', color: i <= step ? 'var(--on-solid)' : 'var(--c-fg-4b5874)' }}>
                {i < step ? <Check size={17} strokeWidth={3} aria-label="done" /> : i + 1}
              </span>
              <span style={{ fontSize: 14, fontWeight: i === step ? 700 : 500, color: i <= step ? 'var(--navy)' : 'var(--muted)', whiteSpace: 'nowrap' }}>{s}</span>
              {i < STEPS.length - 1 && <span aria-hidden style={{ flex: 1, height: 3, background: i < step ? 'var(--green)' : 'var(--surface-3)', margin: '0 14px', borderRadius: 2 }} />}
            </li>
          ))}
        </ol>

        {step === 0 && (
          <div className="form-grid">
            <fieldset className="full" style={{ border: 0, padding: 0, margin: 0 }}>
              <legend className="lb">Instrument class</legend>
              <div style={{ display: 'flex', gap: 18, flexWrap: 'wrap', fontSize: 14 }}>
                <label><input type="radio" name="iclass" defaultChecked /> FDR / RPGF under lien to AICTE</label>
                <label className="muted"><input type="radio" name="iclass" disabled /> Online deposit (RTGS): paid through the AICTE payment page, not uploaded</label>
                <label className="muted"><input type="radio" name="iclass" disabled /> Bank guarantee <PlannedBadge what="Bank guarantee instrument" /></label>
              </div>
            </fieldset>
            {F('ref', 'FDR number', <input id="f-ref" className="inp" value={form.ref} onChange={set('ref')} placeholder="As printed on the receipt" aria-invalid={touched && !!errs.ref} />)}
            {F('bank', 'Issuing bank', <select id="f-bank" className="inp" value={form.bank} onChange={set('bank')} aria-invalid={touched && !!errs.bank}><option value="">Select bank</option>{BANKS.map(([c, n]) => <option key={c} value={c}>{n}</option>)}</select>)}
            {F('branch', 'Branch', <input id="f-branch" className="inp" value={form.branch} onChange={set('branch')} placeholder="e.g. Coimbatore Main Branch" />)}
            {F('amount', 'Deposit amount (₹)', <input id="f-amount" className="inp num" inputMode="numeric" value={form.amount} onChange={set('amount')} placeholder="3500000" aria-invalid={touched && !!errs.amount} />, amt ? inr(amt) : 'Minimum ₹ 20,00,000')}
            {F('issue', 'Issue date', <input id="f-issue" className="inp" type="date" value={form.issue} onChange={set('issue')} />)}
            {F('maturity', 'Maturity date', <input id="f-maturity" className="inp" type="date" value={form.maturity} onChange={set('maturity')} />, tenure > 0 ? `Tenure: ${(tenure / 365).toFixed(1)} years` : 'Minimum tenure 3 years')}
            <div><label className="lb" htmlFor="f-rate">Interest rate (% p.a.)</label><input id="f-rate" className="inp" value={form.rate} onChange={set('rate')} /></div>
            <div><label className="lb" htmlFor="f-fav">Pledged in favour of</label><input id="f-fav" className="inp" value="Member Secretary, AICTE, New Delhi" disabled style={{ background: 'var(--c-fg-f5f7fb)' }} /></div>
          </div>
        )}
        {step === 1 && (
          <div>
            <button type="button" className={`drop${over ? ' over' : ''}`} style={{ width: '100%' }} onClick={() => input.current?.click()} onDragOver={(e) => { e.preventDefault(); setOver(true); }} onDragLeave={() => setOver(false)} onDrop={(e) => { e.preventDefault(); setOver(false); addFiles(e.dataTransfer.files); }}>
              <UploadCloud size={44} color="var(--primary)" aria-hidden />
              <span style={{ display: 'block', marginTop: 10 }}><b>Choose files</b> or drag and drop</span>
              <span className="hint" style={{ display: 'block' }}>Scanned FDR (both sides) and the bank lien letter · PDF only · max 10 MB each</span>
            </button>
            <input ref={input} type="file" multiple accept=".pdf,application/pdf" hidden onChange={(e) => addFiles(e.target.files)} aria-label="Choose files" />
            {DEV && <button className="view-all" style={{ marginTop: 10 }} onClick={() => addFiles([samplePdf('FDR scan'), samplePdf('Bank lien letter')])}>Attach sample documents (dev build)</button>}
            {files.map((f, i) => (
              <div key={f.file.name + i} className="up-file">
                <div className="up-file-head">
                  <FileText size={20} color="var(--red)" aria-hidden />
                  <span className="name">{f.file.name}</span>
                  <span className="muted small">{Math.max(1, Math.round(f.file.size / 1024))} KB</span>
                  <label className="sr-only" htmlFor={`dt-${i}`}>Document type for {f.file.name}</label>
                  <select id={`dt-${i}`} className="sel" value={f.type} onChange={(e) => setFiles(files.map((x, j) => (j === i ? { ...x, type: e.target.value } : x)))}>
                    {DOC_TYPES.map(([k, l]) => <option key={k} value={k}>{l}</option>)}
                  </select>
                  <button className="kebab" onClick={() => setFiles(files.filter((_, j) => j !== i))} aria-label={`Remove ${f.file.name}`}><Trash2 size={16} /></button>
                </div>
                {f.err ? <div className="err" role="alert">{f.err}</div> : !f.pre ? (
                  <span className="muted small" role="status"><Loader2 size={14} className="spin" aria-hidden /> Checking the file and scanning it for malware…</span>
                ) : (
                  <>
                    <div className="ln-chips" role="status">
                      <span className={`dchip ${f.pre.accepted ? 'd-delivered' : 'd-failed'}`}>{f.pre.accepted ? 'Ready to submit' : 'Cannot be submitted'}</span>
                      <ScanChip scan={f.pre.scan} />
                      <span className="dchip"><ShieldCheck size={13} aria-hidden /> Encryption: AES-256-GCM on submission (nothing stored yet)</span>
                    </div>
                    <CheckList checks={f.pre.checks} />
                    {f.pre.scan.signature && <div className="err" role="alert">Malware found: {f.pre.scan.signature}. Remove this file.</div>}
                  </>
                )}
              </div>
            ))}
          </div>
        )}
        {step === 2 && (
          <div className="row g-2" style={{ margin: 0 }}>
            <div>
              <h3 style={{ color: 'var(--navy)', marginBottom: 12, fontSize: 16 }}>Instrument</h3>
              <dl className="kv">
                <dt>FDR number</dt><dd>{form.ref}</dd><dt>Bank / branch</dt><dd>{BANKS.find((b) => b[0] === form.bank)?.[1]}, {form.branch}</dd><dt>Amount</dt><dd>{inr(amt)}</dd>
                <dt>Period</dt><dd>{form.issue && fmtDate(form.issue)} → {form.maturity && fmtDate(form.maturity)}</dd><dt>Documents</dt><dd>{files.length}</dd>
                {renewalOf && <><dt>Replaces</dt><dd>{renewalOf}</dd><dt>Rule check</dt><dd>{rule.replace(/_/g, ' ').toLowerCase()}</dd></>}
              </dl>
            </div>
            <div>
              <div className="compliance-box" style={{ background: 'var(--c-fg-f2f6fc)' }}>
                <div className="shield" style={{ background: 'var(--c-fg-e2ecfb)', color: 'var(--primary)' }} aria-hidden><ShieldCheck size={32} /></div>
                <div><b style={{ color: 'var(--navy)' }}>What happens next</b><span>1. Your values are recorded as “institution declared”.<br />2. The Regulation Bureau asks the issuing bank to confirm.<br />3. Scrutiny is completed only if the bank's record matches.</span></div>
              </div>
              <label style={{ display: 'flex', gap: 12, marginTop: 18, fontSize: 14, lineHeight: 1.5, cursor: 'pointer' }}>
                <input type="checkbox" className="chk" style={{ marginTop: 4 }} checked={agree} onChange={(e) => setAgree(e.target.checked)} />
                I declare that the information is true and the original FDR is pledged in favour of the Member Secretary, AICTE, and will not be encashed without prior written approval.
              </label>
            </div>
          </div>
        )}
        {err && <div className="error-box" role="alert" style={{ marginTop: 14 }}><span>{err}</span></div>}
        <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 26, borderTop: '1px solid var(--line)', paddingTop: 16 }}>
          <button className="btn btn-ghost" onClick={() => (step ? go(step - 1) : nav(-1))}><ArrowLeft size={17} aria-hidden /> {step ? 'Back' : 'Cancel'}</button>
          {step < 2 ? (
            <button className="btn btn-primary" onClick={() => go(step + 1)} disabled={step === 1 && !docsReady}>Continue <ArrowRight size={17} aria-hidden /></button>
          ) : (
            <button className="btn btn-green" onClick={submit} disabled={!agree || busy}><ShieldCheck size={17} aria-hidden /> {busy ? 'Submitting…' : 'Submit for verification'}</button>
          )}
        </div>
        {step === 1 && !docsReady && <p className="hint" style={{ textAlign: 'right' }}>Add at least the scanned FDR and the bank lien letter; every file must pass its checks</p>}
      </Panel>
    </Stagger>
  );
}
