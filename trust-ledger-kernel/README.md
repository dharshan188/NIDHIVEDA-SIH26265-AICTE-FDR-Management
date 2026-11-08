# FDR Trust Ledger: control kernel (SIH 2026, PS 26265)

Event-sourced control kernel for AICTE security deposits and FDRs. See solution_v5.md, section 13.

    pip install pytest hypothesis cryptography
    python -m pytest -q tests          # 43 tests (property-based included)
    python -m trustledger.scenario     # 13 scenarios, 161 checks
    python tools/compare_and_bench.py  # two-design comparison + synthetic load
    python tools/mutants.py            # 20 hand-seeded mutants

- trustledger/kernel.py   controls (allocation, payments, holds, gates, FDR, migration, reports)
- trustledger/rules.py    edition-aware rule resolver; data/rules/*.json are the rule packs
- data/policy.json        proposed policy values (for AICTE approval), changeable without code
- scenarios/*.json        reviewer scenarios as data; S13 was written after the code hash was taken
- results/                saved outputs of the runs

Bank messages are simulated with Ed25519 test keys. There is no UI, DSC parsing, RFC 3161 anchoring or JFDR adapter yet.
