# Notifications: the Nudge Ladder

How the FDR Trust Ledger tells institutions and AICTE officers what needs them, and how it knows they saw it.
Code: `backend/app/nudge/`. Defaults: `backend/policy.json`. Every number below is quoted from that file. AICTE officials
can publish a new version from **Rules & Policy → Notification policy**. The editor shows each value before and after,
requires a reason, and writes the change to the hash-chained portal audit trail.

> **Delivery providers in this build are SIMULATED.** E-mail goes either to a provider simulator or to a local Mailpit
> inbox, which accepts real SMTP but delivers nothing outside this machine. SMS, WhatsApp and push go to provider
> simulators. Each simulated delivery is labelled SIMULATED in the notification centre (`dchip-sim`), in the health panel
> and in the API (`"simulated": true`). The in-app centre is real. Real gateways are listed under "Planned" in `CHANGELOG.md`.

## 1. Outbox design

| Step | What happens | Why |
|---|---|---|
| Event → outbox row | `notify()` writes a `notifications` row **in the caller's transaction**: a release request and its notice are committed together or not at all. | Transactional outbox: no event is ever left without its notice, and no notice exists for a rolled-back event. |
| Idempotent key | Rows that must happen once carry a unique `key` (e.g. `rem:<fdr>:T-30`, `up:<id>`). A second `notify()` with the same key returns the existing row. | Retries, two schedulers or a re-run can never create a duplicate notice. |
| Bilingual | Each row is rendered in English and Hindi at write time (`text`, `text_hi`); each user's `lang` preference selects which one is sent. | The recipient's language is fixed when the notice is written, not at send time. |
| Planning | The worker creates one `notification_deliveries` row per (notice, channel, recipient), chosen by rung, preferences and digest rules, under a unique constraint. | Planning twice cannot create a second delivery. |
| Sending | Due deliveries are claimed with a lease (`delivery.lease_seconds` = **120**). The provider is called with the delivery's idempotency key; SMTP uses it as the Message-ID. | If the process crashes after the provider call but before the commit, the retry uses the **same** key and the provider returns the original message. |
| Retries | Up to `delivery.max_attempts` = **5**, after **1, 5, 30, 120** minutes (`retry_after_minutes`). | Short gaps first for transient errors, then backing off so a provider outage is not hammered. |
| Status words | `sent` means the provider accepted the message (HTTP 2xx / SMTP 250); it is **not** proof of delivery. `delivered` is set only by a signed provider receipt (`POST /api/providers/receipts/{channel}`, HMAC-SHA256 with `TL_PROVIDER_WEBHOOK_SECRET`), or for the in-app centre. | The health panel never claims more than the evidence shows. Simulated receipts are counted separately ("delivered (simulated receipt)"). |

## 2. Urgency ladder and thresholds

One function (`ladder.rung_for`) decides the rung, so every sender and test agrees. Days count IST calendar days, with the maturity date as day 0.

| Rung | When | Channels (`channels.*`) | Reason |
|---|---|---|---|
| **info** | more than **30** days to maturity, or no deadline | in-app | Nothing to do yet. Batched into the daily digest so it never competes with real work. |
| **action** | within **30** days (`ladder.action_needed_within_days`) | in-app, e-mail | Long enough to arrange a renewal with the bank. E-mail leaves a record the institution can forward internally. |
| **deadline** | within **7** days (`ladder.deadline_within_days`) | in-app, e-mail, SMS | One week is the last useful moment to act. SMS reaches the registered mobile even when nobody reads e-mail. |
| **overdue** | matured with no renewal or release | in-app, e-mail, SMS, WhatsApp, push (all channels; the validator enforces this) | The deposit's cover has lapsed. Every channel is used, and the escalation role is copied at once. |

Validation (`policy.validate`) refuses a policy in which: in-app is missing from any rung; overdue loses a channel;
`1 ≤ deadline < action ≤ 365` does not hold; the hold-review period is not 30 days (fixed by the solution document's
hold rule); quiet hours stop applying to overdue; or action links live for more than 168 hours.

### Maturity reminders

The daily sweep runs at **08:00 IST** (`reminders.run_at`) and sends one notice per FDR per window, at **90, 60, 30
and 7** days before maturity (`reminders.before_maturity_days`). If an FDR has matured without a renewal, an overdue
notice goes out **3** days later (`after_missed_renewal_days`) and is copied up the escalation chain. Renewal gaps found
by the per-FDR timeline (a matured FDR with neither a renewal FDR nor a bank renewal notice, or a renewal the bank has not
confirmed within 7 days) send a notice to AICTE.

The sweep is idempotent twice over: `scheduler_runs` allows one run per IST day, and the unique key per window means a
forced re-run (`POST /api/sim/nudge/run`, dev only) cannot send a window twice. A server that was down at 08:00 catches up
on start-up (`catch_up_reminders`).

**Why 90/60/30/7:** 90 days matches the dashboards' "maturing in 90 days" band and gives time for a board resolution.
60 is the second reminder. 30 is where the rung becomes *action*. 7 is the *deadline* rung.

## 3. Quiet hours

No SMS or WhatsApp between **20:00 and 08:00 IST** (`quiet_hours`). A delivery planned inside that window is
**deferred** to 08:00 and shown as "deferred" with a moon icon. In-app, e-mail and push are not held back. **Overdue items
ignore quiet hours** (`except_rungs: ["overdue"]`), and the validator refuses a policy that removes this.

**Why:** a text message at night is intrusive and is often missed anyway, but a lapsed security deposit is serious enough
to justify it. E-mail and in-app notices do not wake anyone, so they are not held back.

## 4. Digests

Informational notices (`digest.rungs: ["info"]`) are not sent one by one. Once per user per IST day, at **08:00**
(`digest.send_at`), the worker sends one digest notice listing that day's informational items. The individual deliveries
are marked "digested". A user can turn the digest off in **My notification preferences**; informational items then stay
in-app only.

**Why:** dozens of individual "information only" e-mails train people to ignore every e-mail from the portal.

## 5. Acknowledgement loop and escalation

- **Acknowledgement** happens when the recipient opens the notice in the centre (**Open and acknowledge**), or opens it
  through a one-click action link. It stamps `ack_at`, `ack_by` and `ack_via`. Nothing in the same family (the notice and
  the steps that climbed from it) escalates after that.
- **Climbing a rung:** an unacknowledged notice produces a new, linked notice one rung higher (`parent_id`, key `up:<id>`)
  after `acknowledgement.next_rung_after_days`: action after **7** days, deadline after **2**, overdue after **2**.
  Informational notices never climb (`null`).
- **Escalation chain:** an overdue notice is copied to the next role in `escalation.chain` (**institution → AICTE
  officer → competent authority**) as soon as it is created. If still unacknowledged after **3** days
  (`step_after_days`), it is copied one step further. Holds have their own 30-day review to the competent authority
  (`hold_review_days` = **30**, from the solution document).
- Each step fires once (unique keys) and is written to the portal audit trail. The **Escalations** page shows every
  family, step by step, with who acknowledged it and when.

**Why:** a notice nobody reads must not just sit there. It must become more urgent and reach someone who can act.
Stopping the whole family on the first acknowledgement keeps escalation from spamming someone who has already responded.

## 6. Action links

E-mail, SMS and WhatsApp notices carry a one-click link `/l/<token>`. The token is `<id>.<expiry>.<HMAC-SHA256>`, bound to
the user, the record path and the action, and only its SHA-256 is stored. A link lives for **72 hours**
(`action_links.ttl_hours`) and works once. It is refused when malformed, forged, expired, already used, or opened by a
different signed-in user. Opening a link **never performs an action**: it requires sign-in (with 2FA), opens the record
and acknowledges the notice. Approval links ask for a DSC step-up, and the approval endpoint still demands a fresh DSC
signature over the gate decision.

**Why:** a link in an SMS can be forwarded or intercepted, so it may show someone where to look but must never act on its own.

## 7. "What changed since you last looked" and the health panel

- **What changed** (all three dashboards): built from the portal and ledger hash chains, starting at the user's previous
  sign-in (`users.prev_login_at`), or the last 7 days on a first visit. Entries are filtered to what that user may see
  (an institution sees only its own records), grouped into plain sentences with links to pages that exist for that role,
  and followed by the user's open deadline and overdue items.
- **Health panel** (AICTE and auditors): counts from outbox and delivery rows only. It shows sent, delivered (provider
  receipt) and delivered (simulated receipt) separately, plus deferred, digested, failed, acknowledgement rate,
  escalations, and median hours from notice to acknowledgement, overall, by rung and per institution. Every simulated external provider is
  shown with its SIMULATED badge; the real in-app centre is not labelled as simulated.

## 8. Preferences

Each user chooses the language of notices (English or Hindi), opts out of e-mail, SMS, WhatsApp or push, and turns the
digest on or off. The in-app centre cannot be switched off. Overdue items are still sent on every channel, and the
preferences page says so.


## 9. Session 7 verification

Defaults above were reviewed against the printed [current policy.json](verification/session7/56-policy-doc-check.txt).
The centre, escalation family, health totals and email-sent counter, embedded preferences and successful/reused action
links match **7 direct SQL comparisons** ([commands, UI and SQL values](verification/session7/71-nudge-sql-final.txt),
[structured results](verification/session7/live-data.json)). Reusing a consumed action link intentionally returns HTTP 409.
The health counter no longer counts a `sent` delivery twice; the existing regression test checks each channel against
its actual delivery rows ([before](verification/session7/57-health-regression-before.txt), [after](verification/session7/58-health-regression-after.txt)).
Sent continues to mean provider acceptance, not proof of bank credit or external message delivery.
