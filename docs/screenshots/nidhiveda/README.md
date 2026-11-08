# NIDHIVEDA screenshots (2026-10-24, session 8)

21 PNGs at 1536×1024, recaptured after two user-requested changes:
1. the solution's display name changed from "FDR Trust Ledger" to **NIDHIVEDA**;
2. the sidebar now keeps the building photo visible (at least 184 px on AICTE/auditor pages, 228 px on institution pages,
   all menu items fit at 1024 px without scrolling).

The Session 7 evidence screenshots in `../final/` are unchanged and remain the historical record.

| Source | Command / log |
|---|---|
| S01 four-user refund images (`s01-*.png`), 12/12 checks | `docs/verification/session8/03-s01-browser.txt` |
| Page screenshots 02–14 | `docs/verification/session8/04-screenshots.txt` |
| `01-login.png` (production build: no dev-only text) | `docs/verification/session8/05-login-production.txt` |
| `15-audit-trail-verify.png` (auditor; both hash chains intact; fresh seed, so the portal chain holds only 3 events) | `docs/verification/session8/08-audit-verify-shot.txt` |
| `16-bank-verification-confirmed.png` (FDR202600124, all six fields bank-confirmed) and `17-bank-verification-mismatch.png` (FDR202600123: declared ₹25,00,000 vs bank-confirmed ₹20,00,000 → Mismatch); fresh seed, so the sidebar shows 27 pending rather than 28 | `docs/verification/session8/09-bank-verification-shots.txt` |

Data: a fresh disposable database seeded by `backend/scripts/seed.py --reset` (synthetic, deterministic for the date),
then changed by the S01 run (one ₹35 lakh online-deposit refund) and the screenshot run (one ₹35 lakh FDR uploaded by
ABC Engineering College, `FDR202600372`, pending). Totals shown: 482 institutions, 822 FDRs, ₹288.85 crore recorded.
All bank data is **SIMULATED** and labelled on screen.

Known limits, as in Session 7:
- `05-upload-checks-and-scan.png` is from the dev build and shows the dev-only "Attach sample documents (dev build)" link.
- `08-fdr-detail-timeline-no-gap.png` shows a timeline without a renewal gap; the seeded data has no live gap.
- `03-dashboard-institution.png` is captured before the upload in the same run, so it shows 2 FDRs while the AICTE and
  auditor dashboards (captured after) include the uploaded third FDR.
