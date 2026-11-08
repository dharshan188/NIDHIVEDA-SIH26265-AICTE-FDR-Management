import {
  AlertTriangle, Bell, BookOpen, CalendarDays, ClipboardCheck, Database, FileCheck2, FileClock, FileText, Headphones,
  Home, Landmark, LineChart, MessageSquareText, Send, ShieldCheck, Upload, User, BarChart3, HandCoins, ScrollText, Banknote, Scale,
  Activity, FileWarning, TrendingUp,
} from 'lucide-react';
import type { ReactNode } from 'react';
import type { Role as ApiRole } from '../api/types';

export type Role = 'aicte' | 'institution' | 'auditor';
export const roleKey = (r: ApiRole): Role => (r === 'AICTE_OFFICIAL' ? 'aicte' : r === 'INSTITUTION' ? 'institution' : 'auditor');

export interface NavItem {
  to: string;
  label: string;
  icon: ReactNode;
  badge?: 'pending' | 'notices' | 'discrepancy';
}

const I = 23;

export const NAV: Record<Role, NavItem[]> = {
  aicte: [
    { to: '', label: 'Dashboard', icon: <Home size={I} /> },
    { to: 'institutions', label: 'Institution Directory', icon: <Landmark size={I} /> },
    { to: 'submissions', label: 'FDR Submissions', icon: <FileText size={I} />, badge: 'pending' },
    { to: 'verification', label: 'Verification & Scrutiny', icon: <ShieldCheck size={I} /> },
    { to: 'reconciliation', label: 'Bank Reconciliation', icon: <Landmark size={I} /> },
    { to: 'renewals', label: 'Renewal & Maturity', icon: <CalendarDays size={I} /> },
    { to: 'releases', label: 'Release / Refund', icon: <HandCoins size={I} /> },
    { to: 'payments', label: 'Payments', icon: <Banknote size={I} /> },
    { to: 'audit-trail', label: 'Audit Trail', icon: <FileClock size={I} /> },
    { to: 'reports', label: 'Reports & Analytics', icon: <BarChart3 size={I} /> },
    { to: 'notifications', label: 'Notifications', icon: <Bell size={I} />, badge: 'notices' },
    { to: 'escalations', label: 'Escalations', icon: <TrendingUp size={I} /> },
    { to: 'notification-health', label: 'Notification Health', icon: <Activity size={I} /> },
    { to: 'missing-documents', label: 'Missing Documents', icon: <FileWarning size={I} /> },
    { to: 'guidelines', label: 'Guidelines & Circulars', icon: <BookOpen size={I} /> },
    { to: 'rules', label: 'Rules & Policy', icon: <Scale size={I} /> },
  ],
  institution: [
    { to: '', label: 'Dashboard', icon: <Home size={I} /> },
    { to: 'profile', label: 'My Profile', icon: <User size={I} /> },
    { to: 'fdrs', label: 'My FDRs / Deposits', icon: <Database size={I} /> },
    { to: 'upload', label: 'Upload New FDR', icon: <Upload size={I} /> },
    { to: 'renewals', label: 'Renewal & Maturity', icon: <CalendarDays size={I} /> },
    { to: 'release', label: 'Release / Refund Request', icon: <Send size={I} /> },
    { to: 'payments', label: 'Refund Payments', icon: <Banknote size={I} /> },
    { to: 'notifications', label: 'Notifications', icon: <Bell size={I} />, badge: 'notices' },
    { to: 'missing-documents', label: 'Missing Documents', icon: <FileWarning size={I} /> },
    { to: 'communication', label: 'Communication', icon: <MessageSquareText size={I} /> },
    { to: 'guidelines', label: 'Guidelines & Documents', icon: <ScrollText size={I} /> },
    { to: 'help', label: 'Help & Support', icon: <Headphones size={I} /> },
  ],
  auditor: [
    { to: '', label: 'Dashboard', icon: <Home size={I} /> },
    { to: 'assignments', label: 'Audit Assignments', icon: <ClipboardCheck size={I} /> },
    { to: 'institutions', label: 'All Institutions', icon: <Landmark size={I} /> },
    { to: 'fdrs', label: 'FDR Records', icon: <Database size={I} /> },
    { to: 'compliance', label: 'Compliance Review', icon: <ShieldCheck size={I} /> },
    { to: 'discrepancies', label: 'Discrepancies', icon: <AlertTriangle size={I} />, badge: 'discrepancy' },
    { to: 'renewals', label: 'Renewal & Maturity', icon: <CalendarDays size={I} /> },
    { to: 'releases', label: 'Release / Refund', icon: <HandCoins size={I} /> },
    { to: 'payments', label: 'Payments', icon: <Banknote size={I} /> },
    { to: 'audit-trail', label: 'Audit Trail', icon: <FileCheck2 size={I} /> },
    { to: 'reports', label: 'Reports', icon: <LineChart size={I} /> },
    { to: 'notifications', label: 'Notifications', icon: <Bell size={I} />, badge: 'notices' },
    { to: 'escalations', label: 'Escalations', icon: <TrendingUp size={I} /> },
    { to: 'notification-health', label: 'Notification Health', icon: <Activity size={I} /> },
    { to: 'missing-documents', label: 'Missing Documents', icon: <FileWarning size={I} /> },
    { to: 'guidelines', label: 'Guidelines & Policies', icon: <BookOpen size={I} /> },
  ],
};

export const ROLE_META: Record<Role, { base: string; title: string; sub: string; tagline: string[] }> = {
  aicte: { base: '/aicte', title: 'AICTE Official', sub: 'Regulation Bureau', tagline: ['Regulating', 'Technical Education', 'for a Stronger India'] },
  institution: { base: '/institution', title: 'ABC Engineering College', sub: 'AICTE ID: 1-12345678', tagline: ['Empowering', 'Quality Education'] },
  auditor: { base: '/auditor', title: 'Auditor', sub: 'Independent Review', tagline: ['Independent Oversight', 'for Transparency', 'and Compliance'] },
};
