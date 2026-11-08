# FDR Trust Ledger — Frontend (SIH 2026 · PS 26265)

Vite + React + TypeScript. All data and authentication come from the backend API (`../backend`); nothing financial is
computed or stored in the browser.

## Run

```bash
npm install
npm run dev        # http://localhost:5173 — proxies /api to the backend on :8000
npm run build      # production build: no demo-credential button, no dev OTP/DSC helpers
```

Start the backend first (see `../backend/README.md`).

## Dev-build only

These exist only when `import.meta.env.DEV` is true **and** the backend runs with `TL_ENV=dev`:

- **Use demo credentials** on the login card.
- The OTP the mock SMS provider sent, and the current authenticator code, shown under the code boxes.
- DSC signing by a **simulated** DSC issuer (a local test CA).
- Bank simulator buttons on the Payments page (debit, credit confirmation, return).
- Scenario replays S01–S09 on the auditor's Assignments page.

Every place bank data appears carries a **SIMULATED** badge.

## Accessibility

Table text is 13 px minimum, focus is always visible, every control is keyboard-reachable, and animations respect
`prefers-reduced-motion`. An automated axe-core WCAG 2 A/AA scan of all 42 role routes (`tools/ui-checks/axe.mjs`) reports 0 violations in light and dark mode after the session-4 fixes (see `../TEST_REPORT.md`, Session 4). The earlier "0 violations on 17 pages" claim is withdrawn: its page list was never recorded and a 42-route re-run of the unchanged code found 5 violations.
No manual screen-reader test has been done.
