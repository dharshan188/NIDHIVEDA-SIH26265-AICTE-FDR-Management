import { AnimatePresence } from 'framer-motion';
import { useEffect } from 'react';
import { Navigate, Route, Routes, useLocation, useNavigate } from 'react-router-dom';
import { api } from './api/client';
import type { User } from './api/types';
import { ROLE_BASE, useStore } from './store/Store';
import AppShell from './components/AppShell';
import { Toasts } from './components/ui';
import AicteDashboard from './pages/aicte/Dashboard';
import AuditorDashboard from './pages/auditor/Dashboard';
import InstitutionDashboard from './pages/institution/Dashboard';
import Upload from './pages/institution/Upload';
import Login from './pages/Login';
import AuditTrail from './pages/shared/AuditTrail';
import FdrDetail from './pages/shared/FdrDetail';
import FdrList from './pages/shared/FdrList';
import Institutions, { InstitutionDetail } from './pages/shared/Institutions';
import { Assignments, Communication, Guidelines, Help, Profile, RulesPolicy } from './pages/shared/Misc';
import Payments from './pages/shared/Payments';
import Reconciliation from './pages/shared/Reconciliation';
import Releases from './pages/shared/Releases';
import Renewals from './pages/shared/Renewals';
import Reports from './pages/shared/Reports';
import Verification from './pages/shared/Verification';
import { Escalations, LinkLanding, MissingDocuments, NotificationCentre, NotificationHealth } from './pages/shared/Nudge';

export default function App() {
  const loc = useLocation();
  // top-level key: login <-> each role shell animate as whole screens
  const top = loc.pathname.split('/')[1] || 'login';
  return (
    <>
      <AnimatePresence mode="wait">
        <Routes location={loc} key={top}>
          <Route path="/login" element={<Login />} />
          <Route path="/l/:token" element={<LinkLanding />} />
          <Route path="/aicte" element={<AppShell role="aicte" />}>
            <Route index element={<AicteDashboard />} />
            <Route path="institutions" element={<Institutions />} />
            <Route path="institutions/:id" element={<InstitutionDetail />} />
            <Route path="submissions" element={<FdrList />} />
            <Route path="verification" element={<Verification />} />
            <Route path="reconciliation" element={<Reconciliation />} />
            <Route path="renewals" element={<Renewals />} />
            <Route path="releases" element={<Releases />} />
            <Route path="audit-trail" element={<AuditTrail />} />
            <Route path="reports" element={<Reports />} />
            <Route path="escalations" element={<Escalations />} />
            <Route path="notification-health" element={<NotificationHealth />} />
            <Route path="missing-documents" element={<MissingDocuments />} />
            <Route path="notifications" element={<NotificationCentre />} />
            <Route path="guidelines" element={<Guidelines />} />
            <Route path="payments" element={<Payments />} />
            <Route path="rules" element={<RulesPolicy />} />
            <Route path="fdr/:id" element={<FdrDetail />} />
          </Route>
          <Route path="/institution" element={<AppShell role="institution" />}>
            <Route index element={<InstitutionDashboard />} />
            <Route path="profile" element={<Profile />} />
            <Route path="fdrs" element={<FdrList />} />
            <Route path="upload" element={<Upload />} />
            <Route path="renewals" element={<Renewals />} />
            <Route path="release" element={<Releases />} />
            <Route path="payments" element={<Payments />} />
            <Route path="notifications" element={<NotificationCentre />} />
            <Route path="communication" element={<Communication />} />
            <Route path="guidelines" element={<Guidelines />} />
            <Route path="help" element={<Help />} />
            <Route path="missing-documents" element={<MissingDocuments />} />
            <Route path="fdr/:id" element={<FdrDetail />} />
          </Route>
          <Route path="/auditor" element={<AppShell role="auditor" />}>
            <Route index element={<AuditorDashboard />} />
            <Route path="assignments" element={<Assignments />} />
            <Route path="institutions" element={<Institutions />} />
            <Route path="institutions/:id" element={<InstitutionDetail />} />
            <Route path="fdrs" element={<FdrList />} />
            <Route path="compliance" element={<Institutions complianceView />} />
            <Route path="discrepancies" element={<Verification readOnly />} />
            <Route path="renewals" element={<Renewals />} />
            <Route path="releases" element={<Releases />} />
            <Route path="payments" element={<Payments />} />
            <Route path="audit-trail" element={<AuditTrail />} />
            <Route path="reports" element={<Reports />} />
            <Route path="escalations" element={<Escalations />} />
            <Route path="notification-health" element={<NotificationHealth />} />
            <Route path="missing-documents" element={<MissingDocuments />} />
            <Route path="notifications" element={<NotificationCentre />} />
            <Route path="guidelines" element={<Guidelines />} />
            <Route path="fdr/:id" element={<FdrDetail />} />
          </Route>
          <Route path="/sso-complete" element={<SsoComplete />} />
          <Route path="*" element={<Navigate to="/login" replace />} />
        </Routes>
      </AnimatePresence>
      <Toasts />
    </>
  );
}

/** Landing page after the OIDC callback has set the session cookie. */
function SsoComplete() {
  const { setUser } = useStore();
  const nav = useNavigate();
  useEffect(() => {
    api<{ user: User }>('/auth/me')
      .then((r) => {
        setUser(r.user);
        nav(ROLE_BASE[r.user.role], { replace: true });
      })
      .catch(() => nav('/login', { replace: true }));
  }, [setUser, nav]);
  return <div className="empty" role="status" style={{ paddingTop: 160 }}>Completing Government SSO sign-in…</div>;
}
