export type Role = 'AICTE_OFFICIAL' | 'INSTITUTION' | 'AUDITOR';
export type Bucket = 'active' | 'maturing' | 'pending' | 'discrepancy' | 'released' | 'closed';
export type FdrStatus = 'pending' | 'verified' | 'discrepancy' | 'released' | 'closed';

export interface User {
  id: number;
  username: string;
  full_name: string;
  role: Role;
  kernel_role: string;
  designation: string;
  institution_id: string | null;
  csrf_token?: string;
}

export interface Fdr {
  id: string;
  institution_id: string;
  institution_name: string | null;
  bank: string;
  bank_name: string;
  branch: string;
  instrument_no: string;
  amount_paise: number;
  rate_bp: number;
  issue_date: string;
  maturity_date: string;
  submitted_on: string;
  status: FdrStatus;
  bucket: Bucket;
  days_left: number;
  discrepancy_reason: string | null;
  scrutinised: boolean;
  renewal_of: string | null;
  renewed_by: string | null;
  closed_reason: string | null;
  bank_confirmed?: boolean;
}

export interface Money {
  count: number;
  amount_paise: number;
}

export interface Stats {
  as_of: string;
  by_bucket: Record<Bucket, Money>;
  total: Money;
  open_release_requests: Money;
  fdrs_with_discrepancy: number;
  institutions_with_discrepancy: number;
  institutions: number;
  institutions_submitting_this_week: number;
}

export interface Compliance {
  compliant: number;
  pending: number;
  discrepancy: number;
  no_valid_fdr: number;
}

export interface Institution {
  id: string;
  aicte_id: string;
  name: string;
  type: string;
  state: string;
  city: string;
  email: string;
  phone: string;
  principal: string;
  established: number;
  intake: number;
  compliance?: string;
  live_fdrs?: number;
  amount_paise?: number;
}

export interface Release {
  id: string;
  obligation_id: string;
  fdr_id: string | null;
  institution_id: string;
  institution_name: string | null;
  reason: string;
  stage: 'SUBMITTED' | 'SCRUTINY_DONE' | 'APPROVED' | 'COMPLETED' | 'REJECTED';
  raised_by: string;
  raised_on: string;
  scrutiny_by: string | null;
  approved_by: string | null;
  case_id: string | null;
  dsc_serial: string | null;
  remarks: string | null;
  updated_on: string;
  amount_paise: number | null;
  gate?: Gate | null;
  refund?: Payment;
  noc?: { noc_id: string; instrument_no: string; state: string };
}

export interface GateCheck {
  code: string;
  mandatory: boolean;
  ok: boolean;
  detail: string;
  overridden_by?: string | null;
}

export interface Gate {
  allowed: boolean;
  blocked_by: string[];
  checks: GateCheck[];
  approval_message: string;
  releasable?: number;
  requested?: number;
  instrument_no?: string | null;
}

export interface Attempt {
  utr: string;
  rail: string;
  amount: number;
  debited_at: string;
  status: string;
  settled_at?: string;
  returned_at?: string;
  return_reason?: string;
  returned_after_settlement?: boolean;
}

export interface Payment {
  refund_id: string;
  obligation_id: string;
  institution_id: string;
  institution_name?: string | null;
  amount_paise: number;
  rail: string;
  state: 'AUTHORISED' | 'INITIATED' | 'DEBITED' | 'SETTLED' | 'REISSUE_REQUIRED' | string;
  approver: string;
  status_text: string;
  reissue_target: string | null;
  history: { at: string; state: string; utr: string | null }[];
  attempts: Attempt[];
  liability: { held_for_institution: number; settled_refunds: number; in_transit: number; outstanding_liability: number; cash_with_aicte_for_this: number };
  payee_verified: boolean;
  simulated_bank: boolean;
}

export interface BankMessage {
  id: number;
  received_at: string;
  channel: string;
  kind: string;
  bank: string;
  bank_name: string;
  key_id: string;
  signed_at: string;
  payload: Record<string, unknown>;
  evidence_id: string;
  status: 'ACCEPTED' | 'REJECTED' | 'DUPLICATE';
  reason: string | null;
  simulated: boolean;
  scenario_id: string | null;
  ref: string | null;
}

export interface Notice {
  id: number;
  at: string;
  kind: string;
  text: string;
  ref: string | null;
  read: boolean;
  rung?: Rung;
  title?: string;
  ack_at?: string | null;
}

export type Rung = 'info' | 'action' | 'deadline' | 'overdue';

export interface Delivery {
  channel: 'in_app' | 'email' | 'sms' | 'whatsapp' | 'push';
  status: string;
  simulated: boolean;
  provider: string | null;
  reason: string | null;
  sent_at: string | null;
  delivered_at: string | null;
  receipt_simulated: boolean | null;
}

export interface LadderNotice {
  id: number;
  at: string;
  kind: string;
  template: string | null;
  rung: Rung;
  rung_label: string;
  title: string;
  text: string;
  text_en: string;
  text_hi: string | null;
  ref: string | null;
  window: string | null;
  read: boolean;
  ack_at: string | null;
  ack_via: string | null;
  escalated_at: string | null;
  escalation_step: number;
  parent_id: number | null;
  audience: string;
  deliveries: Delivery[];
}

export interface DocInfo {
  id: number;
  name: string;
  size_bytes: number;
  sha256: string;
  uploaded_on: string;
  stored: boolean;
  doc_type: string;
  doc_type_label: string;
  encryption: { alg: string; kek_id: string; store: string } | null;
  scan: { status: string; engine: string | null; at: string | null };
  content_checks: ContentCheck[];
  integrity: { status: string | null; at: string | null };
}

export interface ContentCheck { code: string; label: string; ok: boolean | null; detail: string }

export interface TimelineEvent {
  date: string;
  at: string;
  kind: string;
  label: string;
  source: string;
  editions_in_force: string[];
  rule: { key: string; status: string; value: unknown; cites: string[] } | null;
  future?: boolean;
  related?: string;
}

export interface Timeline {
  fdr_id: string;
  events: TimelineEvent[];
  gaps: { kind: string; since: string; days: number; label: string }[];
  reminders: { id: number; at: string; window: string; rung: Rung; ack_at: string | null; key: string }[];
}

export interface Paged<T> {
  total: number;
  items: T[];
}
