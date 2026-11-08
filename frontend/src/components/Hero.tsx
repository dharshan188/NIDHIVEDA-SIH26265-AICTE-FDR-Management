import { motion } from 'framer-motion';
import { CalendarDays, RefreshCw } from 'lucide-react';
import type { Institution } from '../api/types';
import heroAicte from '../assets/hero-aicte.jpg';
import heroInst from '../assets/hero-institution.jpg';
import { fmtDate, fmtDateTime } from '../lib/format';
import { T } from '../lib/motion';
import { useT } from '../lib/prefs';
import { useStore } from '../store/Store';
import type { Role } from './nav';
import { SimBadge } from './ui';

export default function Hero({ role, lastSync, institution }: { role: Role; lastSync: string | null | undefined; institution?: Institution }) {
  const { user, refresh } = useStore();
  const t = useT();
  const when = lastSync ? fmtDateTime(lastSync) : 'no bank messages yet';
  const syncItems = (
    <>
      <span className="live-dot" aria-hidden />
      <span>{t('Last bank message')}: <b>{when}</b></span>
      <SimBadge />
      <button className="refresh" onClick={refresh} aria-label={t('Reload figures')} title={t('Reload figures')}>
        <RefreshCw size={16} />
      </button>
    </>
  );
  const sync = <div className="hero-sync">{syncItems}</div>;

  if (role === 'institution' && institution) {
    return (
      <div className="hero tall">
        <motion.img className="hero-img" src={heroInst} alt="" initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={T.route} />
        <div className="hero-text">
          <div className="wb">{t('Welcome back,')}</div>
          <h1 title={institution.name}>{institution.name}</h1>
          <div className="meta">
            AICTE ID: {institution.aicte_id} <i /> Type: {institution.type} <i /> State: {institution.state}
          </div>
          {sync}
        </div>
        <div className="quote-card">
          Compliance Today
          <br />
          for a Stronger Tomorrow”
          <i />
        </div>
      </div>
    );
  }

  const isAud = role === 'auditor';
  return (
    <div className="hero">
      <motion.img className="hero-img" src={heroAicte} alt="" initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={T.route} />
      <div className="hero-text">
        <div className="wb">{t('Welcome back,')}</div>
        <h1>{user?.full_name}</h1>
        <div className="meta">
          {user?.designation} <i /> Role: {isAud ? 'Audit & Compliance Oversight' : 'FDR & Security Deposit Management'}
        </div>
        {isAud ? (
          <div className="hero-sync">
            {syncItems}
            <span className="sep" aria-hidden />
            <CalendarDays size={15} aria-hidden /> <span>{t('Data as of')} <b>{fmtDate(new Date())}</b></span>
          </div>
        ) : sync}
      </div>
    </div>
  );
}
