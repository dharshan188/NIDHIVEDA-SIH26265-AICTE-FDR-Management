# Current-session baseline verification — 2026-10-24

**STOPPED: the backend baseline count did not reproduce.** SQLite returned **130 passed, 7 skipped, 1 warning**, exit 0; the requested baseline says **129 passed expected**. This is a count discrepancy, not a failing assertion. No baseline count was changed or silently accepted. PostgreSQL and real-service integration tests were not configured in this run (four PostgreSQL tests and three integration tests are conditionally skipped by their source). Their live-service results remain unverified.

Kernel pytest reproduced **67 passed**; kernel scenarios reproduced **13 scenarios, 161 checks, 0 failed**. The frontend production build passed with a chunk-size warning. Full output and exact commands follow. Raw logs are also in `docs/verification/final-baseline/`.

No feature implementation, kernel source changes, git commits, container starts or container deletions were performed. The repository root is `/home/dharshan`. The only container listed by `docker ps --format '{{.Names}} {{.Image}} {{.Status}} {{.Ports}}'` was `buildhub-pg postgres:16-alpine Up 19 minutes 0.0.0.0:5432->5432/tcp, [::]:5432->5432/tcp`. No compose command was used.

The first backend attempt stalled after one test under the earlier restricted sandbox. It was terminated (SIGINT followed by SIGTERM) and retried after the user enabled unrestricted execution. The first kernel pytest invocation passed 67 tests but its tee failed because the log directory was created relative to the wrong working directory; the empty misplaced directories were removed, the intended directory was created, and the successful logged retry is recorded below.

## Skipped or incomplete after the stop condition

- Kernel mutation: started on a scratch copy, then its process tree was terminated when the SQLite discrepancy was observed. Partial output is recorded below; no 32/33 claim is made.
- PostgreSQL baseline, backend mutation, S01–S09 report regeneration, real ClamAV/SeaweedFS/Mailpit tests, axe and browser S01: not completed because the stop condition was reached.
- Remaining work A–H, migrations, screenshots, security scans and documentation rewrites: deferred under the same stop condition. Existing files and earlier claims below have not been revalidated by this session.

## Commands and complete captured output

### Repository root

Working directory: `/home/dharshan/sih2`

```bash
git rev-parse --show-toplevel
```

```text
/home/dharshan
```

### Kernel pytest

Working directory: `/home/dharshan/sih2/trust-ledger-kernel`

```bash
set -o pipefail; PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 ../.venv/bin/python -m pytest -q -p hypothesis.extra.pytestplugin tests 2>&1 | tee ../docs/verification/final-baseline/kernel-pytest.txt
```

```text
...................................................................      [100%]
=============================== warnings summary ===============================
trustledger/crypto.py:26
  /home/dharshan/sih2/trust-ledger-kernel/trustledger/crypto.py:26: PytestCollectionWarning: cannot collect test class 'TestBankSigner' because it has a __init__ constructor (from: tests/test_controls_extra.py)
    class TestBankSigner:

trustledger/crypto.py:26
  /home/dharshan/sih2/trust-ledger-kernel/trustledger/crypto.py:26: PytestCollectionWarning: cannot collect test class 'TestBankSigner' because it has a __init__ constructor (from: tests/test_round8_security.py)
    class TestBankSigner:

trustledger/crypto.py:26
  /home/dharshan/sih2/trust-ledger-kernel/trustledger/crypto.py:26: PytestCollectionWarning: cannot collect test class 'TestBankSigner' because it has a __init__ constructor (from: tests/test_v6_findings.py)
    class TestBankSigner:

trustledger/crypto.py:26
  /home/dharshan/sih2/trust-ledger-kernel/trustledger/crypto.py:26: PytestCollectionWarning: cannot collect test class 'TestBankSigner' because it has a __init__ constructor (from: tests/test_v7_findings.py)
    class TestBankSigner:

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
67 passed, 4 warnings in 6.83s
```

### Kernel scenarios

Working directory: `/home/dharshan/sih2/trust-ledger-kernel`

```bash
set -o pipefail; ../.venv/bin/python -m trustledger.scenario 2>&1 | tee ../docs/verification/final-baseline/kernel-scenarios.txt
```

```text

=== S01: Rs 35 lakh RTGS refund debited with UTR, then returned by beneficiary bank
    answers: Round 4: Issue 1, Question 4, Question 9, Section 9 decisive scenario
      # Setup: AICTE's banker (SBI) signing key, Institution A, one Rs 35 lakh online security deposit received in 2016 with the application reference in the remittance.
  2  ..  do bank
  3  ..  do institution
  4  ..  do obligation
  5  ..  do evidence
  6  ..  do allocate -> {'status': 'ALLOCATED'}
  7  ..  do entitlement
  8  ..  do affidavit
  9  ..  do payee
 10  ..  do evidence
 11  ..  do authorise
 12 PASS expect refund_state: refund R1 state=AUTHORISED
 13  ..  do initiate
 14  ..  do evidence
      # Bank debit + UTR exist. A status-field workflow would now say Completed.
 16 PASS expect refund_state: refund R1 state=DEBITED
 17 PASS expect portal_text: Sent from AICTE's bank on 2026-09-10T11:05 via RTGS, UTR SBINR52026091000077. Waiting for your bank's credit confirmation. NOT yet complete.
 18 PASS expect liability: O1: held_for_institution=Rs 35.00 lakh, settled_refunds=Rs 0.00 lakh, in_transit=Rs 35.00 lakh, outstanding_liability=Rs 35.00 lakh, cash_with_aicte_for_this=Rs 0.00 lakh
      # 35 minutes later the beneficiary bank rejects the credit and the money comes back.
 20  ..  do evidence
 21 PASS expect refund_state: refund R1 state=REISSUE_REQUIRED
 22 PASS expect liability: O1: held_for_institution=Rs 35.00 lakh, settled_refunds=Rs 0.00 lakh, in_transit=Rs 0.00 lakh, outstanding_liability=Rs 35.00 lakh, cash_with_aicte_for_this=Rs 35.00 lakh
 23 PASS expect portal_text: Payment UTR SBINR52026091000077 was returned by your bank on 2026-09-10 (BENEFICIARY_BANK_REJECT). NOT complete: AICTE still owes you Rs 35.00 lakh. Owner: AICTE Finance. Target re-issue: 2026-09-17.
 24 PASS expect notification: RTGS UTR SBINR52026091000077 for refund R1 RETURNED (BENEFICIARY_BANK_REJECT). Liability of Rs 35.00 lakh reopened. Re-issue target 2026-09-17.
 25 PASS expect notification: Your bank returned AICTE's payment of Rs 35.00 lakh on 2026-09-10 (reason: BENEFICIARY_BANK_REJECT). The refund is NOT complete and AICTE still owes you this amount. Owner: AICTE Finance. Next step: AICTE Finance re-issues to the same verified account. Target: 2026-09-17.
 26 PASS expect value: refund.attempts.0.status = RETURNED
 27 PASS expect value: refund.attempts.0.debit_evidence = E-DR-1
 28 PASS expect value: book_balance = 350000000
 29 PASS expect error: raised StateError: a returned-payment credit cannot be allocated as a new deposit
      # Re-issue to the same verified account (return reason was not account-related).
 31  ..  do initiate
 32  ..  do evidence
 33  ..  do evidence
 34 PASS expect refund_state: refund R1 state=SETTLED
 35 PASS expect liability: O1: held_for_institution=Rs 35.00 lakh, settled_refunds=Rs 35.00 lakh, in_transit=Rs 0.00 lakh, outstanding_liability=Rs 0.00 lakh, cash_with_aicte_for_this=Rs 0.00 lakh
 36 PASS expect portal_text: Completed: your bank confirmed credit on 2026-09-11T10:20 (UTR SBINR52026091100012).
 37 PASS expect value: refund.attempts len=2
 38 PASS expect value: book_balance = 0
 39 PASS expect chain: chain valid=True first_bad=None events=16
 40 PASS expect replay_matches: replayed 16 events
--> 20 passed, 0 failed

=== S02: Confirmation overdue, then settled, then a late return reverses the settlement
    answers: Round 4: Section 9 follow-up 'reverse the apparent settlement without deleting the original transaction'
      # Setup: AICTE's banker (SBI) signing key, Institution A, one Rs 35 lakh online security deposit received in 2016 with the application reference in the remittance.
  2  ..  do bank
  3  ..  do institution
  4  ..  do obligation
  5  ..  do evidence
  6  ..  do allocate -> {'status': 'ALLOCATED'}
  7  ..  do entitlement
  8  ..  do affidavit
  9  ..  do payee
 10  ..  do evidence
 11  ..  do authorise
 12  ..  do initiate
 13  ..  do evidence
 14  ..  do tick
 15 PASS expect notification: No credit confirmation for UTR SBINR520260910000A1 within 60 min. Status stays 'awaiting confirmation'; chase AICTE's bank.
 16 PASS expect refund_state: refund R2 state=DEBITED
 17  ..  do tick
      # Second tick: the overdue alert is not duplicated.
 19 PASS expect value: outbox len=1
 20  ..  do evidence
 21 PASS expect refund_state: refund R2 state=SETTLED
 22 PASS expect liability: O1: held_for_institution=Rs 35.00 lakh, settled_refunds=Rs 35.00 lakh, in_transit=Rs 0.00 lakh, outstanding_liability=Rs 0.00 lakh, cash_with_aicte_for_this=Rs 0.00 lakh
      # Two days later the beneficiary bank reverses its own credit and returns the money (anomalous but possible).
 24  ..  do evidence
 25 PASS expect refund_state: refund R2 state=REISSUE_REQUIRED
 26 PASS expect liability: O1: held_for_institution=Rs 35.00 lakh, settled_refunds=Rs 0.00 lakh, in_transit=Rs 0.00 lakh, outstanding_liability=Rs 35.00 lakh, cash_with_aicte_for_this=Rs 35.00 lakh
 27 PASS expect notification: RTGS UTR SBINR520260910000A1 for refund R2 RETURNED (CREDIT_REVERSED_BY_BENEFICIARY_BANK) AFTER it was marked settled - investigate. Liability of Rs 35.00 lakh reopened. Re-issue target 2026-09-18.
 28 PASS expect value: refund.attempts.0.confirm_evidence = E-CC-1
 29 PASS expect value: refund.attempts.0.returned_after_settlement = True
 30 PASS expect value: refund.history.4.1 = RETURNED_AFTER_SETTLEMENT
 31 PASS expect chain: chain valid=True first_bad=None events=15
 32 PASS expect replay_matches: replayed 15 events
--> 13 passed, 0 failed

=== S03: One Rs 50 lakh UTR covers Rs 35 + 15 lakh obligations; one obligation paid in two parts
    answers: Round 4: Issue 3, Question 1 (the accounting test)
  1  ..  do bank
  2  ..  do institution
  3  ..  do obligation
  4  ..  do obligation
  5  ..  do obligation
  6  ..  do evidence
  7  ..  do allocate -> {'status': 'ALLOCATED'}
  8  ..  do allocate -> {'status': 'ALLOCATED'}
  9 PASS expect confidence: A-UG confidence=TRACEABLE
 10 PASS expect confidence: A-PG confidence=TRACEABLE
 11 PASS expect no_notification: 0 'attribution_dispute' notifications
 12 PASS expect value: book_balance = 500000000
 13 PASS expect liability: O-UG: held_for_institution=Rs 35.00 lakh, settled_refunds=Rs 0.00 lakh, in_transit=Rs 0.00 lakh, outstanding_liability=Rs 35.00 lakh, cash_with_aicte_for_this=Rs 35.00 lakh
 14 PASS expect liability: O-PG: held_for_institution=Rs 15.00 lakh, settled_refunds=Rs 0.00 lakh, in_transit=Rs 0.00 lakh, outstanding_liability=Rs 15.00 lakh, cash_with_aicte_for_this=Rs 15.00 lakh
      # The credit is now fully used: a further Rs 1 lakh from it is refused (allocated <= received).
 16 PASS expect error: raised OverAllocation: credit CR-UTR-50L has only Rs 0.00 lakh unallocated
      # An obligation cannot be over-funded either (allocated <= required).
 18  ..  do evidence
 19  ..  do evidence
 20  ..  do allocate -> {'status': 'ALLOCATED'}
 21 PASS expect error: raised OverAllocation: obligation O-MCA would exceed its required Rs 15.00 lakh
 22  ..  do allocate -> {'status': 'ALLOCATED'}
 23 PASS expect liability: O-MCA: held_for_institution=Rs 15.00 lakh, settled_refunds=Rs 0.00 lakh, in_transit=Rs 0.00 lakh, outstanding_liability=Rs 15.00 lakh, cash_with_aicte_for_this=Rs 15.00 lakh
 24 PASS expect value: certification_report.unallocated_credits = 30000000
      # Rs 3 lakh excess from UTR-P2 stays visible as unallocated (refundable excess), never silently absorbed.
 26 PASS expect error: raised StateError: machine_reference basis claimed but the credit narrative does not carry the obligation reference
 27 PASS expect chain: chain valid=True first_bad=None events=12
 28 PASS expect replay_matches: replayed 12 events
--> 13 passed, 0 failed

=== S04: Rs 20 lakh legacy credit mis-attributed; both institutions silent; pool still matches
    answers: Round 4: Issue 2, Question 7 (the trust test), Question 8 (annual confirmations)
  1  ..  do bank
  2  ..  do institution
  3  ..  do institution
      # AICTE's own 2012 bank statement line: UTR and amount only, no remitter details (as old statements often are).
  5  ..  do evidence
      # Legacy register (migrated) says this credit belongs to A. It is actually B's.
  7  ..  do legacy_import
         import report: {'records': 1, 'linked_to_bank_credit': 1, 'declared_only': 0, 'disputed': 0, 'flagged_duplicate': 0, 'fdr_registered': 0}
  8 PASS expect confidence: A-LEG-L1 confidence=LEGACY_DECLARED
  9  ..  do evidence
 10 PASS expect value: certification_report.aggregate_matches = True
 11 PASS expect value: certification_report.per_institution.INST-A.certifiable = 0
 12 PASS expect value: certification_report.per_institution.INST-A.declared_not_certifiable = 200000000
      # No annual confirmation is sent: nothing conflicts yet. A year passes with no response from anyone; nothing changes and nobody is penalised.
 14 PASS expect value: confirmation_requests len=0
 15  ..  do tick
 16 PASS expect confidence: A-LEG-L1 confidence=LEGACY_DECLARED
 17 PASS expect value: holds len=0
 18 PASS expect value: outbox len=0
      # A asks for release. The gate does not pretend: Rs 20 lakh is not proven to be A's.
 20  ..  do entitlement
 21 PASS expect release: allowed=False releasable=Rs 0.00 lakh | M_RULES:BLOCK(NOT_SPECIFIED: None ()); M_AFFIDAVIT_6:BLOCK(missing Affidavit-6); M_ATTRIBUTION:BLOCK(requested Rs 20.00 lakh, releasable now Rs 0.00 lakh; breakdown LEGACY_DECLARED=Rs 20.00 lakh); M_PAYEE_VERIFIED:BLOCK(payee not verified (name look-up evidence missing, mismatched or invalidated by a return))
      # Just-in-time check: AICTE asks its own bank for the remitter of UTR OLD-77 (no institution resubmits anything).
 23  ..  do evidence
      # Bank says the money came from Beta's registered account: the item turns UNCERTAIN automatically and only now is anyone asked to confirm.
 25 PASS expect confidence: A-LEG-L1 confidence=UNCERTAIN
 26 PASS expect value: confirmation_requests len=1
 27  ..  do dispute
 28 PASS expect confidence: A-LEG-L1 confidence=UNCERTAIN
 29 PASS expect value: certification_report.per_institution.INST-A.uncertain = 200000000
 30  ..  do resolve_dispute
 31  ..  do obligation
 32  ..  do allocate -> {'status': 'ALLOCATED'}
 33 PASS expect confidence: A-B confidence=CORROBORATED
 34 PASS expect value: certification_report.per_institution.INST-B.certifiable = 200000000
 35 PASS expect value: allocations.A-LEG-L1.active = False
 36 PASS expect chain: chain valid=True first_bad=None events=13
 37 PASS expect replay_matches: replayed 13 events
--> 18 passed, 0 failed

=== S05: A discrepancy at B, or a contested credit, does not freeze A's independently proven money
    answers: Round 4: Issue 8, Question 6 (partial attribution), Question 10 (180-day delay)
  1  ..  do bank
  2  ..  do institution
  3  ..  do institution
  4  ..  do obligation
  5  ..  do obligation
  6  ..  do obligation
  7  ..  do evidence
  8  ..  do evidence
  9  ..  do evidence
 10  ..  do evidence
 11  ..  do allocate -> {'status': 'ALLOCATED'}
 12  ..  do allocate -> {'status': 'ALLOCATED'}
 13  ..  do allocate -> {'status': 'ALLOCATED'}
 14  ..  do allocate -> {'status': 'ALLOCATED'}
      # B has an unrelated discrepancy. Policy only allows holds on specific items, by authorised roles, with a basis.
 16 PASS expect error: raised StateError: policy allows holds on specific allocations, credits or instruments only, not whole institutions
 17 PASS expect error: raised Unauthorised: section_officer:kiran is not one of ['finance_reconciliation_officer', 'internal_audit']
 18 PASS expect error: raised StateError: hold needs a recorded basis
 19  ..  do hold
      # Somebody claims UTR-X (Rs 10 lakh) belonged to B: that credit, and only that credit, is held.
 21  ..  do hold
 22  ..  do entitlement
 23  ..  do entitlement
 24  ..  do affidavit
 25  ..  do affidavit
 26  ..  do payee
 27  ..  do evidence
 28 PASS expect release: allowed=True releasable=Rs 35.00 lakh | all checks pass
 29 PASS expect release: allowed=False releasable=Rs 15.00 lakh | M_ATTRIBUTION:BLOCK(requested Rs 25.00 lakh, releasable now Rs 15.00 lakh; breakdown TRACEABLE=Rs 15.00 lakh, HELD=Rs 10.00 lakh -> a partial release of Rs 15.00 lakh is allowed by policy)
 30  ..  do authorise
 31 PASS expect value: refund.amount = 150000000
      # The held Rs 10 lakh is not forgotten: at 30 days the hold must be re-decided by the competent authority.
 33  ..  do tick
 34 PASS expect notification: Hold H-X (B claims UTR-X was its remittance) placed by finance_reconciliation_officer:anil reached its review date; decide: continue with recorded reason, or release.
 35  ..  do release_hold
 36 PASS expect release: allowed=False releasable=Rs 0.00 lakh | M_CONFLICT_OF_INTEREST:BLOCK(deputy_director:meera handled this case earlier); M_ATTRIBUTION:BLOCK(requested Rs 10.00 lakh, releasable now Rs 0.00 lakh; breakdown DECLARED=Rs 10.00 lakh, TRACEABLE=Rs 15.00 lakh)
 37 PASS expect release: allowed=False releasable=Rs 0.00 lakh | M_ATTRIBUTION:BLOCK(requested Rs 10.00 lakh, releasable now Rs 0.00 lakh; breakdown DECLARED=Rs 10.00 lakh, TRACEABLE=Rs 15.00 lakh)
      # UTR-X was matched only by A's declaration (no remitter on the credit), so it is DECLARED, not proven: it still needs bank remitter details before release. Releasing the hold did not upgrade the evidence.
 39 PASS expect confidence: AA2b confidence=DECLARED
 40 PASS expect chain: chain valid=True first_bad=None events=26
 41 PASS expect replay_matches: replayed 26 events
--> 12 passed, 0 failed

=== S06: FDR matured in 2019, auto-renewed; release prepared in 2026
    answers: Round 4: Issue 5, Issue 7, Question 5 (the old FDR test)
      # Setup: issuing bank (PNB) key; Institution C; Rs 15 lakh FDR obligation; FDR confirmed by the bank in 2014, maturing 2019-02-15.
  2  ..  do bank
  3  ..  do institution
  4  ..  do obligation
  5  ..  do instrument
  6  ..  do evidence
  7  ..  do entitlement
  8  ..  do affidavit
      # Only evidence on file is from 2014, and the FDR has matured since. The gate refuses to name an instrument it cannot vouch for.
 10 PASS expect release: allowed=False releasable=Rs 0.00 lakh | M_CURRENT_INSTRUMENT:BLOCK(latest bank confirmation is 4568 days old (policy max 90); instrument matured after the latest confirmation; bank may have renewed or paid it)
      # Just-in-time bank confirmation: PNB reports the FDR was auto-renewed on maturity to a new number, lien continued.
 12  ..  do evidence
 13 PASS expect value: current_instrument.number = PNB-FD-2207
      # Which rule governs a renewal on 2019-02-15? The resolver uses the date of the renewal, not today. That pack (APH 2018-19) is reviewer-reported and unverified, so it is not applied silently.
 15 PASS expect release: allowed=False releasable=Rs 0.00 lakh | M_RENEWAL_RULES:BLOCK(auto-renewal on 2019-02-15: UNVERIFIED accepted_with_bank_remark (APH-2018-19: Cl. 5.34.2 (reviewer-reported)))
 16 PASS expect error: raised Unauthorised: deputy_director:meera is not one of ['legal_cell']
 17  ..  do confirm_pack
 18 PASS expect release: allowed=True releasable=Rs 0.00 lakh | all checks pass
 19  ..  do authorise
 20 PASS expect value: nocs.NOC-1.instrument_no = PNB-FD-2207
 21 PASS expect value: nocs.NOC-1.state = NOC_ISSUED
 22 PASS expect error: raised InvalidEvidence: lien discharge for an instrument with no NOC
 23  ..  do evidence
 24 PASS expect value: nocs.NOC-1.state = LIEN_DISCHARGED
 25 PASS expect notification: Completed: bank confirmed lien on FDR PNB-FD-2207 discharged.
 26 PASS expect chain: chain valid=True first_bad=None events=12
 27 PASS expect replay_matches: replayed 12 events
--> 12 passed, 0 failed

=== S07: Manual renewal after maturity: prohibited in one edition, unspecified in another
    answers: Round 4: Issue 5 (demo must not perform a prohibited renewal), P1 historical renewal rules
  1  ..  do bank
  2  ..  do institution
  3  ..  do obligation
  4  ..  do instrument
      # Dec 2018: institution asks to renew an FDR that matured on 30 Nov 2018.
  6  ..  do renewal_request -> ESCALATED_TO_LEGAL_CELL
  7 PASS expect result: result=ESCALATED_TO_LEGAL_CELL
  8 PASS expect notification: Which rule governs renewal of ID on 2018-12-20? Resolver status: UNVERIFIED.
  9  ..  do confirm_pack
 10  ..  do renewal_request -> REJECTED
 11 PASS expect result: result=REJECTED
 12 PASS expect notification: Renewal of FDR PNB-FD-3001 after maturity is not permitted (APH-2018-19: Cl. 5.34.2 (reviewer-reported)). Options: release on entitlement, or replacement as the rules allow.
      # A different FDR matures in 2025, under APH 2024-27, which (as far as we found) says nothing about post-maturity renewal.
 14  ..  do obligation
 15  ..  do instrument
 16  ..  do renewal_request -> ESCALATED_TO_LEGAL_CELL
 17 PASS expect result: result=ESCALATED_TO_LEGAL_CELL
 18  ..  do ruling
 19  ..  do renewal_request -> ACCEPTED_PENDING_BANK_CONFIRMATION
 20 PASS expect result: result=ACCEPTED_PENDING_BANK_CONFIRMATION
      # A renewal BEFORE maturity is a replacement and is not blocked by the post-maturity rule.
 22  ..  do obligation
 23  ..  do instrument
 24  ..  do renewal_request -> ACCEPTED_PENDING_BANK_CONFIRMATION
 25 PASS expect result: result=ACCEPTED_PENDING_BANK_CONFIRMATION
 26 PASS expect chain: chain valid=True first_bad=None events=15
 27 PASS expect replay_matches: replayed 15 events
--> 9 passed, 0 failed

=== S08: Ten-year-old FDR evidence at release; bank renumbered one FDR and discharged another without an NOC
    answers: Round 4: Issue 7 (AICTE question: what proves the NOC names the current instrument?)
  1  ..  do bank
  2  ..  do institution
  3  ..  do obligation
  4  ..  do obligation
  5  ..  do instrument
  6  ..  do instrument
  7  ..  do evidence
  8  ..  do evidence
  9  ..  do entitlement
 10  ..  do affidavit
 11 PASS expect release: allowed=False releasable=Rs 0.00 lakh | M_CURRENT_INSTRUMENT:BLOCK(latest bank confirmation is 3837 days old (policy max 90))
 12  ..  do evidence
 13 PASS expect release: allowed=True releasable=Rs 0.00 lakh | all checks pass
      # The bank's reply on the second FDR is worse: discharged, no lien. AICTE issued no NOC for it.
 15  ..  do evidence
 16 PASS expect notification: Bank reports SBI-FD-2 status=DISCHARGED lien=NONE but AICTE issued no NOC. Investigate.
 17  ..  do entitlement
 18  ..  do affidavit
 19 PASS expect release: allowed=False releasable=Rs 0.00 lakh | M_CURRENT_INSTRUMENT:BLOCK(bank reports status=DISCHARGED lien=NONE)
 20 PASS expect chain: chain valid=True first_bad=None events=14
 21 PASS expect replay_matches: replayed 14 events
--> 6 passed, 0 failed

=== S09: Bank signer's authority ends vs. bank signer's key is compromised (with back-dating attempt)
    answers: Rounds 2-4: Bank Authority Registry and revocation cascade (now executable)
  1  ..  do bank
  2  ..  do bank
  3  ..  do institution
  4  ..  do obligation
  5  ..  do obligation
  6  ..  do evidence
  7  ..  do allocate -> {'status': 'ALLOCATED'}
  8  ..  do payee
  9  ..  do evidence
      # Officer behind K1 is transferred on 1 Jan 2026: an ordinary END of authority.
 11  ..  do end_signer
 12 PASS expect confidence: AY confidence=TRACEABLE
 13 PASS expect error: raised InvalidEvidence: signer authority ended 2026-01-01T00:00
 14 PASS expect notification: Rejected credit_advice E-LATE: signer authority ended 2026-01-01T00:00
 15  ..  do evidence
 16  ..  do allocate -> {'status': 'ALLOCATED'}
 17  ..  do entitlement
 18  ..  do affidavit
 19  ..  do authorise
      # On 1 Apr the bank reports K2 was COMPROMISED from 15 Feb. Everything received through K2 on or after that date is now untrusted.
 21  ..  do compromise_signer
 22 PASS expect confidence: AZ confidence=UNVERIFIED_SOURCE
 23 PASS expect confidence: AY confidence=TRACEABLE
 24 PASS expect notification: Evidence E-Z relied on key SBI-K2 after its compromise date 2026-02-15T00:00; dependent decisions re-checked.
 25 PASS expect notification: Refund RZ relied on now-invalid evidence; review required.
 26 PASS expect error: raised GateBlocked: blocked by: M_EVIDENCE_VALID
      # Attacker with K2 back-dates a message to 1 Jan. Validity is judged at receipt time, so it is still rejected.
 28 PASS expect error: raised InvalidEvidence: signer compromised from 2026-02-15T00:00
      # Message changed after signing (amount edited in transit): signature fails.
 30  ..  do bank
 31 PASS expect error: raised InvalidEvidence: signature does not verify
 32 PASS expect chain: chain valid=True first_bad=None events=20
 33 PASS expect replay_matches: replayed 20 events
--> 12 passed, 0 failed

=== S10: Mandatory clearances cannot be overridden; administrative ones can, with a reason; conflict of interest
    answers: Round 3-4: mandatory vs administrative checks, conflict of interest, maker-checker
      # Setup: AICTE's banker (SBI) signing key, Institution A, one Rs 35 lakh online security deposit received in 2016 with the application reference in the remittance.
  2  ..  do bank
  3  ..  do institution
  4  ..  do obligation
  5  ..  do evidence
  6  ..  do allocate -> {'status': 'ALLOCATED'}
  7  ..  do entitlement
  8  ..  do affidavit
  9  ..  do payee
 10  ..  do evidence
 11  ..  do affidavit
 12 PASS expect release: allowed=False releasable=Rs 35.00 lakh | AFFIDAVIT_FORMAT:BLOCK(format deviates from template)
 13 PASS expect error: raised MandatoryOverride: M_PAYEE_VERIFIED is a mandatory clearance and cannot be overridden
 14 PASS expect notification: director:sunil tried to override mandatory M_PAYEE_VERIFIED on O1.
 15 PASS expect error: raised StateError: override needs a reason
 16 PASS expect error: raised Unauthorised: finance_officer:ravi is not one of ['section_officer', 'deputy_director']
 17  ..  do override
 18 PASS expect release: allowed=True releasable=Rs 35.00 lakh | AFFIDAVIT_FORMAT:BLOCK(format deviates from template)
      # Conflict of interest: someone who prepared this case cannot approve it; wrong role cannot approve.
 20 PASS expect release: allowed=False releasable=Rs 35.00 lakh | AFFIDAVIT_FORMAT:BLOCK(format deviates from template); M_APPROVER_ROLE:BLOCK(section_officer:kiran may not approve); M_CONFLICT_OF_INTEREST:BLOCK(section_officer:kiran handled this case earlier)
 21  ..  do entitlement
 22 PASS expect release: allowed=False releasable=Rs 35.00 lakh | AFFIDAVIT_FORMAT:BLOCK(format deviates from template); M_CONFLICT_OF_INTEREST:BLOCK(deputy_director:meera handled this case earlier)
      # Director Sunil tried to bypass a mandatory check on this case earlier, so he is now conflicted on it too.
 24 PASS expect release: allowed=False releasable=Rs 35.00 lakh | AFFIDAVIT_FORMAT:BLOCK(format deviates from template); M_CONFLICT_OF_INTEREST:BLOCK(director:sunil handled this case earlier)
 25  ..  do authorise
 26 PASS expect error: raised Unauthorised: director:rao is not one of ['finance_officer']
 27  ..  do initiate
 28 PASS expect error: raised InvalidEvidence: debit amount differs from authorised refund amount
 29 PASS expect chain: chain valid=True first_bad=None events=16
 30 PASS expect replay_matches: replayed 16 events
--> 13 passed, 0 failed

=== S11: Someone edits the stored Rs 35 lakh credit to Rs 0.01 lakh directly in the database
    answers: Rounds 2-4: hash-chained audit trail (external RFC 3161 anchoring not built in this kernel)
      # Setup: AICTE's banker (SBI) signing key, Institution A, one Rs 35 lakh online security deposit received in 2016 with the application reference in the remittance.
  2  ..  do bank
  3  ..  do institution
  4  ..  do obligation
  5  ..  do evidence
  6  ..  do allocate -> {'status': 'ALLOCATED'}
  7  ..  do entitlement
  8  ..  do affidavit
  9  ..  do payee
 10  ..  do evidence
 11 PASS expect chain: chain valid=True first_bad=None events=9
 12  ..  do tamper
 13 PASS expect chain: chain valid=False first_bad=4 events=9
--> 2 passed, 0 failed

=== S12: Migrating legacy records without marking them verified, blocking refunds, or forcing resubmission
    answers: Round 4: final AICTE question (10,000 historical records)
  1  ..  do bank
  2  ..  do bank
  3  ..  do institution
      # AICTE's own historical bank statement lines (obtainable from AICTE's banker without involving institutions).
  5  ..  do evidence
  6  ..  do evidence
  7  ..  do evidence
  8  ..  do legacy_import
         import report: {'records': 7, 'linked_to_bank_credit': 3, 'declared_only': 1, 'disputed': 1, 'flagged_duplicate': 1, 'fdr_registered': 1}
  9 PASS expect result: result=3
 10 PASS expect result: result=1
 11 PASS expect result: result=1
 12 PASS expect result: result=1
 13 PASS expect result: result=1
      # Nothing became TRACEABLE. L1 is CORROBORATED only because AICTE's bank statement shows A's own account as remitter.
 15 PASS expect confidence: A-LEG-L1 confidence=CORROBORATED
 16 PASS expect confidence: A-LEG-L2 confidence=LEGACY_DECLARED
 17 PASS expect confidence: A-LEG-L5 confidence=UNCERTAIN
 18 PASS expect value: holds len=0
 19 PASS expect no_notification: 0 'refund_returned' notifications
 20 PASS expect notification: LEG-L7: possible duplicate: credit CR-OLD-1 has only Rs 0.00 lakh unallocated
 21 PASS expect notification: Competing claims on credit CR-OLD-5 by INST-E, INST-F. Only allocations on this credit are affected.
      # Release of the legacy FDR: blocked only until a just-in-time bank confirmation arrives. The institution resubmits nothing.
 23  ..  do entitlement
 24  ..  do affidavit
 25 PASS expect release: allowed=False releasable=Rs 0.00 lakh | M_CURRENT_INSTRUMENT:BLOCK(no valid bank confirmation of this instrument)
 26  ..  do evidence
 27 PASS expect release: allowed=True releasable=Rs 0.00 lakh | all checks pass
      # Release of L1 (corroborated by bank evidence) is not blocked on attribution.
 29  ..  do entitlement
 30 PASS expect release: allowed=False releasable=Rs 15.00 lakh | M_AFFIDAVIT_6:BLOCK(missing Affidavit-6); M_PAYEE_VERIFIED:BLOCK(payee not verified (name look-up evidence missing, mismatched or invalidated by a return))
 31 PASS expect value: confirmation_requests len=1
 32 PASS expect chain: chain valid=True first_bad=None events=29
 33 PASS expect replay_matches: replayed 29 events
--> 18 passed, 0 failed

=== S13: Judge's 13th: NEFT refund returned 'account closed'; new account via Affidavit-9; name look-up fails once; then settles
    answers: Round 4: Question 3 (13th scenario without code changes). Written after the code hash was recorded.
      # Setup: AICTE's banker (SBI) signing key, Institution A, one Rs 35 lakh online security deposit received in 2016 with the application reference in the remittance.
  2  ..  do bank
  3  ..  do institution
  4  ..  do obligation
  5  ..  do evidence
  6  ..  do allocate -> {'status': 'ALLOCATED'}
  7  ..  do entitlement
  8  ..  do affidavit
  9  ..  do payee
 10  ..  do evidence
 11  ..  do authorise
 12  ..  do initiate
 13  ..  do evidence
 14  ..  do evidence
 15 PASS expect refund_state: refund R13 state=REISSUE_REQUIRED
 16 PASS expect liability: O1: held_for_institution=Rs 35.00 lakh, settled_refunds=Rs 0.00 lakh, in_transit=Rs 0.00 lakh, outstanding_liability=Rs 35.00 lakh, cash_with_aicte_for_this=Rs 35.00 lakh
 17 PASS expect notification: Your bank returned AICTE's payment of Rs 35.00 lakh on 2026-09-10 (reason: ACCOUNT_CLOSED). The refund is NOT complete and AICTE still owes you this amount. Owner: AICTE Finance. Next step: update and re-verify your bank account (Affidavit-9 process), then AICTE Finance re-issues. Target: 2026-09-17.
 18 PASS expect error: raised GateBlocked: blocked by: M_PAYEE_VERIFIED
 19 PASS expect error: raised StateError: changing a registered payee account needs Affidavit-9 and the TER fee (APH 2024-27)
 20  ..  do payee
 21  ..  do evidence
 22 PASS expect notification: Bank name look-up returned 'Alpha Educational Trust', which does not match 'Alpha Institute of Technology'.
 23 PASS expect error: raised GateBlocked: blocked by: M_PAYEE_VERIFIED
 24  ..  do evidence
 25  ..  do initiate
 26  ..  do evidence
 27  ..  do tick
 28 PASS expect notification: No credit confirmation for UTR N-002 within 120 min. Status stays 'awaiting confirmation'; chase AICTE's bank.
 29  ..  do evidence
 30 PASS expect refund_state: refund R13 state=SETTLED
 31 PASS expect liability: O1: held_for_institution=Rs 35.00 lakh, settled_refunds=Rs 35.00 lakh, in_transit=Rs 0.00 lakh, outstanding_liability=Rs 0.00 lakh, cash_with_aicte_for_this=Rs 0.00 lakh
 32 PASS expect value: refund.attempts len=2
 33 PASS expect chain: chain valid=True first_bad=None events=20
 34 PASS expect replay_matches: replayed 20 events
--> 13 passed, 0 failed

SUMMARY
  S01   OK    20 checks  Rs 35 lakh RTGS refund debited with UTR, then returned by beneficiary bank
  S02   OK    13 checks  Confirmation overdue, then settled, then a late return reverses the settlement
  S03   OK    13 checks  One Rs 50 lakh UTR covers Rs 35 + 15 lakh obligations; one obligation paid in two parts
  S04   OK    18 checks  Rs 20 lakh legacy credit mis-attributed; both institutions silent; pool still matches
  S05   OK    12 checks  A discrepancy at B, or a contested credit, does not freeze A's independently proven money
  S06   OK    12 checks  FDR matured in 2019, auto-renewed; release prepared in 2026
  S07   OK     9 checks  Manual renewal after maturity: prohibited in one edition, unspecified in another
  S08   OK     6 checks  Ten-year-old FDR evidence at release; bank renumbered one FDR and discharged another without an NOC
  S09   OK    12 checks  Bank signer's authority ends vs. bank signer's key is compromised (with back-dating attempt)
  S10   OK    13 checks  Mandatory clearances cannot be overridden; administrative ones can, with a reason; conflict of interest
  S11   OK     2 checks  Someone edits the stored Rs 35 lakh credit to Rs 0.01 lakh directly in the database
  S12   OK    18 checks  Migrating legacy records without marking them verified, blocking refunds, or forcing resubmission
  S13   OK    13 checks  Judge's 13th: NEFT refund returned 'account closed'; new account via Affidavit-9; name look-up fails once; then settles
  scenarios=13 checks_passed=161 checks_failed=0
```

### Backend SQLite, original sandbox attempt

Working directory: `/home/dharshan/sih2/backend`

```bash
set -o pipefail; PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 ../.venv/bin/python -m pytest -q -p hypothesis.extra.pytestplugin tests 2>&1 | tee ../docs/verification/final-baseline/backend-sqlite-pytest.txt
```

```text
.
```

### Backend SQLite, unrestricted retry

Working directory: `/home/dharshan/sih2/backend`

```bash
set -o pipefail; PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 ../.venv/bin/python -m pytest -q -p hypothesis.extra.pytestplugin -o faulthandler_timeout=60 tests 2>&1 | tee ../docs/verification/final-baseline/backend-sqlite-unrestricted-pytest.txt
```

```text
........................................................sss............. [ 52%]
............................................ssss.................        [100%]
=============================== warnings summary ===============================
../.venv/lib/python3.10/site-packages/fastapi/testclient.py:1
  /home/dharshan/sih2/.venv/lib/python3.10/site-packages/fastapi/testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
    from starlette.testclient import TestClient as TestClient  # noqa

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
130 passed, 7 skipped, 1 warning in 101.91s (0:01:41)
```

### Frontend production build

Working directory: `/home/dharshan/sih2/frontend`

```bash
set -o pipefail; npm run build 2>&1 | tee ../docs/verification/final-baseline/frontend-build.txt
```

```text

> frontend@0.0.0 build
> tsc -b && vite build

vite v8.3.5 building client environment for production...
transforming...
✓ 2970 modules transformed.
rendering chunks...
computing gzip size...
dist/index.html                                1.46 kB │ gzip:   0.74 kB
dist/assets/side-dark-BiXSkEdR.jpg            19.89 kB
dist/assets/side-light-Yiz-2WZw.jpg           22.19 kB
dist/assets/hero-institution-BVM4MN7y.jpg     25.73 kB
dist/assets/hero-aicte-DKhwHsP-.jpg           29.83 kB
dist/assets/login-building-ClrGOrZQ.jpg      119.00 kB
dist/assets/aicte-logo-DWG2qWT1.png          243.94 kB
dist/assets/index-DXU_YiJS.css                83.49 kB │ gzip:  18.78 kB
dist/assets/index-DTq33KkI.js              1,050.79 kB │ gzip: 312.76 kB

[plugin builtin:vite-reporter] 
(!) Some chunks are larger than 500 kB after minification. Consider:
- Using dynamic import() to code-split the application
- Use build.rolldownOptions.output.codeSplitting to improve chunking: https://rolldown.rs/reference/OutputOptions.codeSplitting
- Adjust chunk size limit for this warning via build.chunkSizeWarningLimit.
✓ built in 1.39s
```

### Kernel mutation — interrupted, no final result

Working directory: `/home/dharshan/sih2/trust-ledger-kernel`

```bash
set -o pipefail; PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 ../.venv/bin/python -c 'import pathlib, shutil, subprocess, sys, tempfile; root=pathlib.Path.cwd(); tmp=pathlib.Path(tempfile.mkdtemp(prefix="tl-kernel-baseline-")); dst=tmp/"kernel"; shutil.copytree(root,dst,ignore=shutil.ignore_patterns("__pycache__",".pytest_cache",".hypothesis")); print("Scratch kernel:",dst,flush=True); result=subprocess.run([sys.executable,"tools/mutants.py"],cwd=dst); print("Harness exit:",result.returncode,flush=True); sys.exit(result.returncode)' 2>&1 | tee ../docs/verification/final-baseline/kernel-mutation.txt
```

```text
Scratch kernel: /tmp/tl-kernel-baseline-98eplqpq/kernel
killed    Refund marked settled at bank debit (reviewer Issue 1)
killed    Returned payment does not reopen the attempt
killed    Allocation may exceed money received
killed    Obligation may be over-funded
killed    Release counts declared money as proven
killed    Holds ignored
killed    Compromised signer still trusted
killed    Signer validity judged at the (forgeable) signed_at
killed    Stale FDR evidence accepted (age)
killed    Evidence older than last maturity accepted
killed    Unverified rule pack applied silently
killed    Conflict-of-interest check removed
killed    Mandatory clearance can be overridden
killed    Account-related return does not force payee re-verification
killed    Returned money can be re-used as a new deposit
killed    Machine-reference basis not checked
killed    Remitter from another institution not flagged
killed    Hash excludes previous hash
SURVIVED  Payment re-issue skips evidence re-check
killed    Policy hold-scope rule ignored (institution-wide holds allowed)
killed    V6-T01 other bank may settle a payment
killed    V6-T03 dispute award may over-fund
killed    V6-T06 substring reference match
```

---

# Historical report — not current-session evidence

The material below predates this verification attempt. Its claims must not be treated as passing results from this session.

# Test report — FDR Trust Ledger (SIH 2026 · PS 26265)

Every number below was produced by a command run on **2026-10-24** on this machine (Linux, Python 3.10.12, Node 24,
PostgreSQL 16 in Docker). Data is synthetic seed data, not AICTE data.

## Summary

| What | Result |
|---|---|
| Kernel tests (unchanged kernel) | **67 passed** |
| Kernel scenarios (all 13) | **13 scenarios, 161 checks, 0 failed** |
| Reviewer scenarios S01–S09 via `backend/scripts/run_scenarios.py` | **9 scenarios, 115 checks, 0 failed** |
| Backend tests (pytest + Hypothesis), SQLite + PostgreSQL | **76 passed** |
| Backend mutation testing (hand-seeded) | **22 / 22 killed** (control run passed) |
| Kernel mutation testing (`tools/mutants.py`, run on a scratch copy) | **32 / 33 killed** |
| Frontend type-check + production build | **passes** (`tsc -b`, `vite build`) |
| Accessibility: axe-core WCAG 2 A/AA, 17 pages | **0 violations** |
| End-to-end in Chrome (real UI, 4 users, S01 lifecycle) | **completed, 0 console errors** |
| Backend lint (ruff E,F,W,B) | **clean** (E501 and B008 ignored; B008 is FastAPI's `Depends` idiom) |

## Kernel unchanged

A SHA-256 over the kernel's Python, JSON scenario, data and test files is identical before and after this work, and equal
to the same hash taken from `fdr-trust-ledger-final(2).zip`:
`1c7674cce8665ecb7a5f77665879621b0818814d28a3d5f0d5c86d137db3a81b`.

```
cd trust-ledger-kernel
python -m pytest -q tests        -> 67 passed, 4 warnings
python -m trustledger.scenario   -> scenarios=13 checks_passed=161 checks_failed=0
```

## Scenarios S01–S09

```
cd backend && python scripts/run_scenarios.py
S01  OK  20 passed  Rs 35 lakh RTGS refund debited with UTR, then returned by beneficiary bank
S02  OK  13 passed  Confirmation overdue, then settled, then a late return reverses the settlement
S03  OK  13 passed  One Rs 50 lakh UTR covers Rs 35 + 15 lakh obligations; one obligation paid in two parts
S04  OK  18 passed  Rs 20 lakh legacy credit mis-attributed; both institutions silent; pool still matches
S05  OK  12 passed  A discrepancy at B, or a contested credit, does not freeze A's independently proven money
S06  OK  12 passed  FDR matured in 2019, auto-renewed; release prepared in 2026
S07  OK   9 passed  Manual renewal after maturity: prohibited in one edition, unspecified in another
S08  OK   6 passed  Ten-year-old FDR evidence; bank renumbered one FDR and discharged another without an NOC
S09  OK  12 passed  Bank signer's authority ends vs. key compromised (with back-dating attempt)
scenarios=9 checks_passed=115 checks_failed=0
```

The same nine also run inside the API (`POST /api/sim/scenarios/{id}/replay`, in a sandbox kernel). Each passes in
`tests/test_ledger_db.py::test_scenario_replay`.

## Backend tests: 76

| File | Tests | Covers |
|---|---|---|
| `test_auth.py` | 20 | Argon2id; generic errors (unknown user = wrong password = wrong role); lockout after 5 and timed unlock; MFA mandatory; OTP single use, expiry, 5-attempt burn, send rate limit; TOTP; DSC login, wrong certificate, wrong message, single-use challenge; role enforcement; 15-minute idle timeout; cookie flags (HttpOnly, Secure, SameSite=Strict); CSRF; logout; **IDOR** (another institution's FDR, dashboard, institution, messages, payee, release request, lists, payments → 404); SSO login, nonce mismatch, role mismatch |
| `test_bank_and_payments.py` | 23 | SIMULATED flag on every message; confirmation → verify; tampered payload rejected; wrong bank for the instrument; another bank's key; unknown signer; **ended signer** keeps earlier evidence valid; **compromised-from** invalidates evidence received after it; **back-dating** does not escape compromise (receipt time); bank mismatch → discrepancy and verify blocked; re-delivery no-op vs changed content rejected; **S01 end to end through the API**; settlement needs matching amount and account; return after settlement flagged and payee re-verification required; unique UTR; debit and look-up only from Finance's bank; **maker-checker** (scrutiny officer cannot approve; approver cannot initiate); refused mandatory override is logged and conflicts the officer; DSC approval bound to the gate decision; FDR NOC then lien discharge; holds scoped and role-limited, hold blocks release; 30-day hold escalation |
| `test_ledger_db.py` | 29 | DB refuses over-allocation of a credit, beyond requirement, and of a returned payment; unique UTR and FDR-per-bank; event store insert-only; **Hypothesis**: random allocation sequences keep kernel and DB sums within limits and in agreement (40 examples); DB trigger blocks any over-allocation that bypasses the kernel (25 examples); memory rebuilt when storage refuses; rules escalate (no-edition date blocked, unverified edition escalated, legal-cell confirmation); manual renewal after maturity escalated; pre-maturity renewal = replacement; Table 1.4 and penalty proposals; **legacy import** (never TRACEABLE, CORROBORATED only from bank remitter data, duplicate flagged, nothing blocked); **audit chain** clean / edit / last-event deletion via checkpoint / middle deletion / consistent rewrite of the head caught by checkpoint; S01–S09 replay; dashboard figures from the DB and follow changes; maturing counted from server date |
| `test_postgres.py` | 4 | Alembic migration + seed on PostgreSQL 16; trigger blocks over-allocation; event tables insert-only (UPDATE and DELETE); **two concurrent transactions** racing for the same credit: exactly one commits |

Command: `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q -p hypothesis.extra.pytestplugin tests` with
`TL_TEST_PG_URL` set → `76 passed`. Without `TL_TEST_PG_URL`: 72 passed, 4 skipped.

## Mutation testing

**Backend** (`backend/scripts/mutants.py`): each mutant re-breaks one control in a copy of the backend and the full suite
must fail. A control run of the unmutated copy must pass first, or the results are rejected.

- First run: invalid. Every mutant "died" because the copy could not import the kernel (relative path). The harness was
  fixed (absolute kernel path + control run). This is recorded because it would otherwise have overstated the result.
- Second run: 21 / 22 killed. Survivor: *checkpoint hash not compared*. No test rewrote the newest event while keeping the
  chain consistent. Test added (`test_audit_checkpoint_catches_consistent_rewrite_of_head`).
- Final run: **22 / 22 killed** — IDOR scope, CSRF, idle timeout, lockout (2), role tab, OTP used / expiry / rate limit,
  DSC serial binding, SSO nonce, maker-checker, approval DSC, verify vs bank mismatch, verify without confirmation,
  DB credit-cap trigger, projection mismatch rule, checkpoint comparison, chain content hash, memory rebuild on DB
  failure, list scoping, hold scope.

**Kernel** (`trust-ledger-kernel/tools/mutants.py`, run on a scratch copy so the kernel's `results/` file is untouched):
**32 / 33 killed**, the same figure the kernel's documentation reports.

## Frontend

- `npx tsc -b` and `npx vite build`: pass.
- axe-core 4 (WCAG 2 A and AA rules) on 17 pages across the three roles: **0 violations**. The first scan found 4 issues
  (red and green button contrast, one scrollable table not keyboard-focusable); they were fixed and re-scanned.
  Automated checks only. No manual screen-reader or keyboard-only walkthrough has been recorded.
- Browser run (Chrome, 1536×1024, real login): AICTE official via TOTP, institution via OTP, auditor via DSC; S01 by four
  users (institution request → section-officer scrutiny → deputy-director DSC approval → finance initiate → simulated
  debit → return → re-issue → positive confirmation). The institution's screen said "NOT yet complete" after the debit,
  "AICTE still owes you Rs 35.00 lakh" after the return, and "Completed" only after the credit confirmation. No console errors.

## Screenshots (`docs/screenshots/`, 1536×1024)

`01-login.png`, `02-dashboard-aicte.png`, `03-dashboard-institution.png`, `04-dashboard-auditor.png`,
`05-s01-release-gate.png`, `06-s01-sent-not-complete.png`, `07-s01-returned-reissue-required.png`, `08-s01-settled.png`,
`09-audit-trail-verify.png`.

## Not verified here

- The **R10** document (`FDR_Trust_Ledger_R10_Final_Solution.md`) describes a package with round-9 adversarial tests,
  a 70-seed multi-payment test and its own verification runs. That package is **not** in this repository. Its numbers are
  **reported, not verified**.
- No load or concurrency test beyond the two-transaction race; no penetration test; no test against any real bank, SMS
  gateway, DSC issuer or SSO provider (all simulated, see CHANGELOG.md).
