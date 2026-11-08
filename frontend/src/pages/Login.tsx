import { AnimatePresence, motion, useScroll, useTransform } from 'framer-motion';
import {
  AlertCircle, ArrowLeft, ArrowRight, BarChart3, BellRing, Check, Eye, EyeOff, FileSignature, FileText, KeyRound, Landmark, Loader2, Lock, Mail,
  ScrollText, ShieldCheck, Smartphone, Usb, User, Users,
} from 'lucide-react';
import { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { api, errorText, post } from '../api/client';
import type { Role, User as ApiUser } from '../api/types';
import building from '../assets/login-building.jpg';
import { Brand, PrefControls } from '../components/Header';
import { PARALLAX_MAX, SPRING, STAGGER, T, prefersReducedMotion, revealItem, revealList } from '../lib/motion';
import { usePrefs } from '../lib/prefs';
import { ROLE_BASE, useStore } from '../store/Store';

const DEV = import.meta.env.DEV;

const ROLES: { key: Role; label: string; icon: React.ReactNode; placeholder: string; idLabel: string }[] = [
  { key: 'AICTE_OFFICIAL', label: 'AICTE Official', icon: <User size={24} fill="currentColor" strokeWidth={0} />, placeholder: 'Enter your AICTE official email or user ID', idLabel: 'User ID / Official Email' },
  { key: 'INSTITUTION', label: 'Institution', icon: <Landmark size={24} strokeWidth={1.7} />, placeholder: 'Enter your AICTE Permanent ID', idLabel: 'AICTE Permanent ID' },
  { key: 'AUDITOR', label: 'Auditor', icon: <Users size={24} strokeWidth={1.7} />, placeholder: 'Enter your auditor email or user ID', idLabel: 'User ID / Auditor Email' },
];

type Method = 'otp' | 'totp' | 'dsc';

/** After sign-in: back to an action link (/l/<token>) if that is how the user arrived; never any other target (no open redirect). */
function afterLogin(role: keyof typeof ROLE_BASE): string {
  const next = new URLSearchParams(window.location.search).get('next') ?? '';
  return /^\/l\/[A-Za-z0-9._-]{10,300}$/.test(next) ? next : ROLE_BASE[role];
}

const FEATS = [
  { icon: <FileText size={44} color="var(--blue)" />, bg: 'var(--blue-50)', title: ['Digital', 'Submission'], text: ['Easy and verified', 'FDR submission'] },
  { icon: <ShieldCheck size={44} color="var(--green)" />, bg: 'var(--green-50)', title: ['Rule-based', 'Verification'], text: ['As per AICTE', 'regulations'] },
  { icon: <BellRing size={44} color="var(--orange-600)" />, bg: 'var(--orange-50)', title: ['Lifecycle', 'Tracking'], text: ['Maturity, renewal', 'and alerts'] },
  { icon: <BarChart3 size={44} color="var(--purple)" fill="var(--purple)" />, bg: 'var(--purple-50)', title: ['Audit Trail', '& Compliance'], text: ['Tamper-evident', 'and transparent'] },
];

interface DemoAccount { username: string; password: string; role: Role; kernel_role: string; name: string }

export default function Login() {
  const { user, setUser } = useStore();
  const nav = useNavigate();
  const reduce = prefersReducedMotion();
  const { t } = usePrefs();
  // gentle parallax on the building image: at most 12 px of travel, none under reduced motion
  const { scrollY } = useScroll();
  const buildY = useTransform(scrollY, [0, 800], [0, reduce ? 0 : -PARALLAX_MAX], { clamp: true });
  const [role, setRole] = useState<Role>('AICTE_OFFICIAL');
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [show, setShow] = useState(false);
  const [method, setMethod] = useState<Method>('otp');
  const [methods, setMethods] = useState<Method[]>(['otp', 'totp', 'dsc']);
  const [step, setStep] = useState<'creds' | 'code' | 'dsc'>('creds');
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState('');
  const [sentTo, setSentTo] = useState('');
  const [otp, setOtp] = useState(['', '', '', '', '', '']);
  const [timer, setTimer] = useState(0);
  const [devCode, setDevCode] = useState('');
  const [done, setDone] = useState(false);
  const boxes = useRef<(HTMLInputElement | null)[]>([]);
  const r = ROLES.find((x) => x.key === role)!;

  useEffect(() => {
    if (user && !done) nav(afterLogin(user.role), { replace: true });
  }, [user, nav, done]);

  useEffect(() => {
    if (timer <= 0) return;
    const t = setInterval(() => setTimer((x) => Math.max(0, x - 1)), 1000);
    return () => clearInterval(t);
  }, [timer]);

  const switchRole = (k: Role) => {
    setRole(k);
    setErr('');
    setStep('creds');
    setUsername('');
    setPassword('');
  };

  const fillDemo = async () => {
    const res = await api<{ accounts: DemoAccount[] }>('/sim/demo-accounts').catch(() => ({ accounts: [] as DemoAccount[] }));
    const pick = res.accounts.find((a) => a.role === role && (role !== 'AICTE_OFFICIAL' || a.kernel_role === 'deputy_director')) ?? res.accounts.find((a) => a.role === role);
    if (pick) {
      setUsername(pick.username);
      setPassword(pick.password);
      setErr('');
    } else setErr('No demo account available. Is the backend running in dev mode?');
  };

  const startCode = async (m: Method) => {
    setOtp(['', '', '', '', '', '']);
    setDevCode('');
    if (m === 'otp') {
      const res = await post<{ sent_to: string }>('/auth/otp/send');
      setSentTo(res.sent_to);
      setTimer(59);
      if (DEV) {
        const o = await api<{ code: string | null }>(`/sim/otp-outbox/${encodeURIComponent(username.trim())}`).catch(() => ({ code: null }));
        if (o.code) setDevCode(o.code);
      }
    } else if (DEV) {
      const t = await api<{ code: string }>(`/sim/totp/${encodeURIComponent(username.trim())}`).catch(() => ({ code: '' }));
      setDevCode(t.code);
    }
    setStep('code');
    setTimeout(() => boxes.current[0]?.focus(), 80);
  };

  const submitCreds = async () => {
    setErr('');
    if (!username.trim() || !password) return setErr('Enter your user ID and password to continue.');
    setBusy(true);
    try {
      const res = await post<{ methods: Method[] }>('/auth/login', { username: username.trim(), password, role });
      setMethods(res.methods);
      const m = res.methods.includes(method) ? method : 'otp';
      setMethod(m);
      if (m === 'dsc') setStep('dsc');
      else await startCode(m);
    } catch (e) {
      setErr(errorText(e));
    } finally {
      setBusy(false);
    }
  };

  const finish = (u: ApiUser) => {
    setDone(true);
    setUser(u);
    setTimeout(() => nav(afterLogin(u.role)), reduce ? 0 : 450);
  };

  const verify = async (digits = otp) => {
    const code = digits.join('');
    if (code.length < 6) return setErr('Enter the 6-digit code.');
    setBusy(true);
    setErr('');
    try {
      const res = await post<{ user: ApiUser }>(method === 'otp' ? '/auth/otp/verify' : '/auth/totp/verify', { code });
      finish(res.user);
    } catch (e) {
      setErr(errorText(e));
      setOtp(['', '', '', '', '', '']);
      boxes.current[0]?.focus();
    } finally {
      setBusy(false);
    }
  };

  const onDigit = (i: number, val: string) => {
    const d = val.replace(/\D/g, '');
    if (d.length > 1) {
      const arr = d.slice(0, 6).split('');
      const next = [...arr, ...Array(6 - arr.length).fill('')];
      setOtp(next);
      boxes.current[Math.min(arr.length, 5)]?.focus();
      if (arr.length === 6) verify(next);
      return;
    }
    const next = [...otp];
    next[i] = d;
    setOtp(next);
    setErr('');
    if (d && i < 5) boxes.current[i + 1]?.focus();
    if (d && i === 5 && next.every(Boolean)) verify(next);
  };

  const idx = ROLES.findIndex((x) => x.key === role);

  return (
    <motion.div className="login" initial={{ opacity: 0 }} animate={{ opacity: 1, transition: T.route }} exit={{ opacity: 0, transition: T.fast }}>
      <div className="login-sun" aria-hidden />
      <header className="login-top">
        <Brand />
        <div className="login-top-r">
          <div className="product">
            <b>{t('NIDHIVEDA')}</b>
            <span>{t('Security Deposit & FDR Management Portal')}</span>
          </div>
          <PrefControls />
        </div>
      </header>

      <main className="login-body">
        <div className="login-left">
          <div>
            <div className="eyebrow">{t('TRANSPARENT')} <i /> {t('SECURE')} <i /> {t('ACCOUNTABLE')}</div>
            <h1 className="login-title">NIDHI<span>VEDA</span></h1>
            <div className="login-sub">{t('Security Deposit & FDR Management Portal')}</div>
            <p className="login-desc">A unified and secure platform for the submission, verification, tracking and release of Security Deposits / FDRs for AICTE-approved institutions.</p>
          </div>
          <motion.div className="feats" variants={revealList} initial={reduce ? false : 'hidden'} animate="show" transition={{ staggerChildren: STAGGER }}>
            {FEATS.map((f, i) => (
              <motion.div key={i} className="feat" style={{ ['--fb' as string]: f.bg }} variants={revealItem}>
                <span aria-hidden>{f.icon}</span>
                <b>{f.title[0]}<br />{f.title[1]}</b>
                <span>{f.text[0]}<br />{f.text[1]}</span>
              </motion.div>
            ))}
          </motion.div>
          <div className="login-build">
            <motion.img src={building} alt="AICTE headquarters building" style={{ y: buildY }} />
            <div className="trust-badge">
              <span><ShieldCheck size={26} color="var(--on-solid)" fill="var(--primary-solid)" aria-hidden /> Secure</span><i />
              <span><ScrollText size={24} color="var(--primary)" aria-hidden /> Traceable</span><i />
              <span><FileSignature size={24} color="var(--primary)" aria-hidden /> Compliant</span>
            </div>
          </div>
        </div>

        <motion.section className="login-card" aria-labelledby="signin-h" initial={reduce ? false : { opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0, transition: T.route }}>
          <h2 id="signin-h">{t('Sign In to NIDHIVEDA')}</h2>
          <p className="lc-sub">{t('Access your role-based dashboard')}</p>

          <div className="role-tabs" role="tablist" aria-label={t('Sign in as')}>
            <motion.div className="slider" animate={{ left: `${(idx * 100) / 3}%` }} style={{ width: '33.333%' }} transition={SPRING.nav} />
            {ROLES.map((x) => (
              <button key={x.key} role="tab" aria-selected={role === x.key} className={role === x.key ? 'on' : ''} onClick={() => switchRole(x.key)}>
                <span aria-hidden style={{ display: 'grid' }}>{x.icon}</span> {t(x.label)}
              </button>
            ))}
          </div>

          <AnimatePresence mode="wait" initial={false}>
            {step === 'creds' && (
              <motion.form key={'creds-' + role} initial={{ opacity: 0, x: 10 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: -10 }} transition={T.fast}
                onSubmit={(e) => { e.preventDefault(); submitCreds(); }} noValidate>
                <div className="lfield">
                  <label htmlFor="uid">{t(r.idLabel)}</label>
                  <div className="linput">
                    <Mail size={22} strokeWidth={1.6} aria-hidden />
                    <input id="uid" value={username} onChange={(e) => setUsername(e.target.value)} placeholder={r.placeholder} autoComplete="username" />
                  </div>
                </div>
                <div className="lfield" style={{ marginTop: 22 }}>
                  <label htmlFor="pw">{t('Password')}</label>
                  <div className="linput">
                    <Lock size={22} strokeWidth={1.6} aria-hidden />
                    <input id="pw" type={show ? 'text' : 'password'} value={password} onChange={(e) => setPassword(e.target.value)} placeholder={t('Enter your password')} autoComplete="current-password" />
                    <button type="button" onClick={() => setShow(!show)} aria-label={show ? 'Hide password' : 'Show password'}>{show ? <EyeOff size={21} /> : <Eye size={21} />}</button>
                  </div>
                </div>
                <div className="lrow">
                  {DEV ? (
                    <button type="button" style={{ color: 'var(--muted)', fontSize: 13 }} onClick={fillDemo}>
                      <KeyRound size={13} style={{ verticalAlign: -2, marginRight: 5 }} aria-hidden />Use demo credentials (dev build)
                    </button>
                  ) : <span />}
                  <a href="#help" onClick={(e) => e.preventDefault()} className="link">{t('Forgot Password?')}</a>
                </div>

                <fieldset style={{ border: 0, padding: 0, margin: 0 }}>
                  <legend className="tfa-h">{t('Two-Factor Authentication (Mandatory)')}</legend>
                  <div className="tfa-s">{t('Choose a verification method to continue')}</div>
                  <div className="tfa" role="radiogroup">
                    {([
                      ['otp', <Smartphone size={24} />, 'OTP', 'SMS / Email OTP'],
                      ['totp', <ShieldCheck size={24} />, 'Authenticator App', 'Use Authenticator App'],
                      ['dsc', <Usb size={24} />, 'Digital Signature (DSC)', 'For approvals & release'],
                    ] as const).map(([k, ic, t, s]) => (
                      <button type="button" role="radio" aria-checked={method === k} key={k} className={method === k ? 'on' : ''} onClick={() => setMethod(k)} disabled={!methods.includes(k)}>
                        <span className="ti" aria-hidden>{ic}</span>
                        <b>{t}</b>
                        <small>{s}</small>
                        <span className="radio" aria-hidden />
                      </button>
                    ))}
                  </div>
                </fieldset>

                {err && <div className="attempts" role="alert"><AlertCircle size={15} aria-hidden /> {err}</div>}

                <button className="lbtn" type="submit" disabled={busy}>
                  {busy ? <Loader2 className="spin" size={20} aria-hidden /> : null}
                  {busy ? 'Checking…' : t(method === 'otp' ? 'Send OTP' : method === 'totp' ? 'Continue' : 'Continue with DSC')}
                  {!busy && <ArrowRight className="ar" size={22} aria-hidden />}
                </button>
              </motion.form>
            )}

            {step === 'code' && (
              <motion.div key="code" initial={{ opacity: 0, x: 10 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: -10 }} transition={T.fast} style={{ paddingTop: 18 }}>
                <button className="view-all" onClick={() => { setStep('creds'); setErr(''); }}><ArrowLeft size={16} aria-hidden /> Back</button>
                <div style={{ textAlign: 'center', marginTop: 10 }}>
                  <div style={{ width: 64, height: 64, borderRadius: 16, background: 'var(--primary-50)', color: 'var(--primary)', display: 'grid', placeItems: 'center', margin: '0 auto' }} aria-hidden>
                    {method === 'otp' ? <Smartphone size={30} /> : <ShieldCheck size={30} />}
                  </div>
                  <h3 className="tfa-h" style={{ fontSize: 19, marginTop: 14 }}>{method === 'otp' ? 'Enter the 6-digit OTP' : 'Enter authenticator code'}</h3>
                  <p className="tfa-s">{method === 'otp' ? `Sent to your registered mobile ${sentTo} and e-mail. Valid for 5 minutes, single use.` : 'Open your authenticator app and enter the current code for NIDHIVEDA.'}</p>
                </div>
                <form onSubmit={(e) => { e.preventDefault(); verify(); }}>
                  <div className={`otp${err ? ' bad' : ''}`} role="group" aria-label="Verification code">
                    {otp.map((d, i) => (
                      <input key={i} ref={(el) => { boxes.current[i] = el; }} value={d} inputMode="numeric" autoComplete={i === 0 ? 'one-time-code' : 'off'} maxLength={6} aria-label={`Digit ${i + 1} of 6`}
                        onChange={(e) => onDigit(i, e.target.value)}
                        onKeyDown={(e) => { if (e.key === 'Backspace' && !otp[i] && i > 0) boxes.current[i - 1]?.focus(); }} />
                    ))}
                  </div>
                  {err && <div className="attempts" role="alert" style={{ justifyContent: 'center' }}><AlertCircle size={15} aria-hidden /> {err}</div>}
                  {method === 'otp' && (
                    <div style={{ textAlign: 'center', fontSize: 14, color: 'var(--muted)', marginTop: 12 }} aria-live="polite">
                      {timer > 0 ? <>Resend OTP in <b>0:{String(timer).padStart(2, '0')}</b></> : <button type="button" className="view-all" onClick={() => startCode('otp').catch((e) => setErr(errorText(e)))}>Resend OTP</button>}
                    </div>
                  )}
                  {DEV && devCode && (
                    <div className="login-hint"><KeyRound size={16} aria-hidden /> Dev build: the {method === 'otp' ? 'mock SMS provider sent' : 'simulated authenticator shows'} <code>{devCode}</code></div>
                  )}
                  <button className="lbtn" type="submit" disabled={busy}>
                    {busy ? <Loader2 className="spin" size={20} aria-hidden /> : <ShieldCheck size={20} aria-hidden />} {busy ? 'Verifying…' : t('Verify & Sign In')}
                  </button>
                </form>
              </motion.div>
            )}

            {step === 'dsc' && <DscStep key="dsc" username={username.trim()} onBack={() => setStep('creds')} onDone={finish} />}
          </AnimatePresence>

          <div className="or">{t('OR')}</div>
          <a className="sso" href={`/api/auth/sso/start?role=${role}`}>
            <Landmark className="emb" size={28} strokeWidth={1.5} aria-hidden />
            {t('Sign in with Government SSO (DigiLocker / e-Pramaan)')}
            <ArrowRight className="ar" size={22} aria-hidden />
          </a>
          {DEV && <p className="hint" style={{ textAlign: 'center' }}>Dev build: SSO uses a local mock identity provider, not e-Pramaan.</p>}
          <div className="sec-note">
            <Lock size={24} aria-hidden />
            <span>For security reasons, accounts are locked after <b>5 failed login attempts</b> and sessions expire after <b>15 minutes</b> of inactivity.</span>
          </div>
          <nav className="lfoot" aria-label={t('Help')}>
            <a href="#help" onClick={(e) => e.preventDefault()}>{t('Help & Support')}</a><i />
            <a href="#manual" onClick={(e) => e.preventDefault()}>{t('User Manual')}</a><i />
            <a href="#privacy" onClick={(e) => e.preventDefault()}>{t('Privacy Policy')}</a><i />
            <a href="#terms" onClick={(e) => e.preventDefault()}>{t('Terms of Use')}</a>
          </nav>
        </motion.section>
      </main>

      <AnimatePresence>
        {done && (
          <motion.div className="success-burst" role="status" initial={{ opacity: 0 }} animate={{ opacity: 1, transition: T.fast }}>
            <div style={{ textAlign: 'center' }}>
              <div className="ring"><Check size={48} strokeWidth={3} aria-hidden /></div>
              <div style={{ fontSize: 24, fontWeight: 700 }}>Identity verified</div>
              <div style={{ opacity: 0.85, marginTop: 6 }}>Opening your dashboard…</div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  );
}

function DscStep({ username, onBack, onDone }: { username: string; onBack: () => void; onDone: (u: ApiUser) => void }) {
  const [phase, setPhase] = useState<'ready' | 'signing'>('ready');
  const [err, setErr] = useState('');
  const sign = async () => {
    setPhase('signing');
    setErr('');
    try {
      const { challenge } = await post<{ challenge: string }>('/auth/dsc/challenge');
      if (!DEV) throw new Error('Connect your DSC token and signer utility (integration planned).');
      const sig = await post<{ certificate_pem: string; signature_b64: string }>('/sim/dsc/sign', { username, message: challenge });
      const res = await post<{ user: ApiUser }>('/auth/dsc/verify', sig);
      onDone(res.user);
    } catch (e) {
      setErr(errorText(e));
      setPhase('ready');
    }
  };
  return (
    <motion.div initial={{ opacity: 0, x: 10 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: -10 }} transition={T.fast} style={{ paddingTop: 16 }}>
      <button className="view-all" onClick={onBack}><ArrowLeft size={16} aria-hidden /> Back</button>
      <div style={{ textAlign: 'center', padding: '14px 0 4px' }}>
        <div style={{ width: 64, height: 64, borderRadius: 16, background: 'var(--primary-50)', color: 'var(--primary)', display: 'grid', placeItems: 'center', margin: '0 auto' }} aria-hidden><Usb size={30} /></div>
        <h3 className="tfa-h" style={{ fontSize: 19, marginTop: 14 }}>Sign the login challenge with your DSC</h3>
        <p className="tfa-s">The server checks the certificate chain, its validity period, key usage and the signature.</p>
        {DEV && <div className="login-hint" style={{ justifyContent: 'center' }}><KeyRound size={16} aria-hidden /> Dev build: signed by a SIMULATED DSC issuer (test CA).</div>}
      </div>
      {err && <div className="attempts" role="alert"><AlertCircle size={15} aria-hidden /> {err}</div>}
      <button className="lbtn" disabled={phase === 'signing'} onClick={sign}>
        {phase === 'signing' ? <Loader2 className="spin" size={20} aria-hidden /> : <ShieldCheck size={20} aria-hidden />} {phase === 'signing' ? 'Signing challenge…' : 'Sign & Continue'}
      </button>
    </motion.div>
  );
}
