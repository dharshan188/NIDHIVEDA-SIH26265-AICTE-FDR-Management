# Required scenarios — report

Generated 2026-10-24T16:58:06 by `backend/scripts/run_required_scenarios.py` against a fresh seeded database. Bank, OTP/DSC, SMS/e-mail/WhatsApp/push providers, the malware-scanner stub and the clock are SIMULATED; document storage uses a local filesystem. Real-service tests run separately.

**6 scenarios, 52 checks passed, 0 failed.**

## R1 — New submission: upload, encrypt, scan, bank confirmation, verification, notices both ways

| Check | Result |
|---|---|
| institution uploads the FDR with two PDFs | pass |
| both documents encrypted at rest (AES-256-GCM envelope) | pass |
| both documents malware-scanned clean | pass |
| status pending until the bank confirms | pass |
| AICTE notified through the outbox (fdr_submitted) | pass |
| download decrypts and the SHA-256 matches | pass |
| verification refused before any bank confirmation | pass |
| issuing bank (SIMULATED) confirms every field | pass |
| officer verifies | pass |
| institution notified in English and Hindi | pass |

## R2 — Validity tracking: daily sweep, ladder rungs, buckets from queries, rules in force per date

| Check | Result |
|---|---|
| 08:00 IST sweep runs | pass |
| a second run the same IST day sends nothing new | pass |
| dashboard 'maturing' count equals the list query | pass |
| a maturing FDR has a scheduled reminder | pass |
| reminder window is the tightest one reached | pass |
| ladder rung follows days to maturity | pass |
| timeline shows the rule editions in force on the issue date | pass |

## R3 — Approaching maturity: T-7 deadline rung, quiet hours, acknowledgement stops the ladder

| Check | Result |
|---|---|
| T-7 reminder created on the deadline rung | pass |
| channels: in-app, e-mail and SMS | pass |
| in-app and e-mail go out at 21:00 | pass |
| SMS held for quiet hours (20:00–08:00 IST) | pass |
| e-mail marked SIMULATED (provider simulator) | pass |
| SMS sent at 08:00 next morning | pass |
| institution opens it: acknowledged | pass |
| no rung-up after acknowledgement | pass |

## R4 — Renewal: missed renewal goes overdue and escalates; a renewal FDR closes the gap and stops reminders

| Check | Result |
|---|---|
| 3 days after maturity: overdue notice | pass |
| overdue uses every channel | pass |
| copied to the AICTE officer (escalation role) | pass |
| renewal gap check runs (maturity is in the future on the real clock) | pass |
| institution submits the renewal FDR | pass |
| old FDR's timeline shows the renewal | pass |
| old FDR has no renewal gap any more | pass |
| no further reminders for the renewed FDR | pass |

## R5 — Discrepancy: bank says a different amount; verification blocked; flagged; observation answered and closed

| Check | Result |
|---|---|
| institution declares Rs 25 lakh (bank book says Rs 20 lakh) | pass |
| comparison shows the amount MISMATCH | pass |
| verification refused on mismatch | pass |
| officer flags the discrepancy | pass |
| institution receives 'clarification needed' (action rung) | pass |
| scrutiny observation recorded (mismatch) | pass |
| institution replies: observation answered | pass |
| officer closes the observation | pass |
| missing-documents report lists it as unverified | pass |

## R6 — Authorised release: scrutiny, DSC approval, NOC, completion only on bank lien discharge

| Check | Result |
|---|---|
| institution raises the release request | pass |
| AICTE notified (release_requested) | pass |
| section officer completes scrutiny | pass |
| approval without a valid DSC signature is refused | pass |
| release gate allows (all mandatory checks pass) | pass |
| deputy director approves with DSC: NOC issued | pass |
| NOC alone is not completion (FDR still verified) | pass |
| institution told: not complete until lien discharge | pass |
| bank (SIMULATED) confirms lien discharge | pass |
| only now: released | pass |
