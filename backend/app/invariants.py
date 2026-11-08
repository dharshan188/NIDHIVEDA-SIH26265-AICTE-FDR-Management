"""Database-enforced money invariants (second line of defence behind the kernel).

- Σ active allocations on a credit   ≤ the credit amount
- Σ active allocations to an obligation ≤ the required amount
- returned-payment credits cannot be allocated
(Unique UTR per debit and unique FDR instrument per bank are UNIQUE constraints in models.py.)

PostgreSQL locks the credit and obligation rows inside the trigger (SELECT ... FOR UPDATE), so two
concurrent transactions cannot both pass the check against the same stale sum.
"""
from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.engine import Connection

SQLITE = [
    """CREATE TRIGGER IF NOT EXISTS trg_alloc_ins BEFORE INSERT ON allocations WHEN NEW.active
    BEGIN
      SELECT RAISE(ABORT, 'INVARIANT: returned-payment credit cannot be allocated')
        WHERE (SELECT kind FROM bank_credits WHERE credit_id = NEW.credit_id) <> 'deposit';
      SELECT RAISE(ABORT, 'INVARIANT: allocations exceed credit amount')
        WHERE (SELECT COALESCE(SUM(amount_paise),0) FROM allocations WHERE credit_id = NEW.credit_id AND active) + NEW.amount_paise
            > (SELECT amount_paise FROM bank_credits WHERE credit_id = NEW.credit_id);
      SELECT RAISE(ABORT, 'INVARIANT: allocations exceed required amount')
        WHERE (SELECT COALESCE(SUM(amount_paise),0) FROM allocations WHERE obligation_id = NEW.obligation_id AND active) + NEW.amount_paise
            > (SELECT amount_paise FROM obligations WHERE obligation_id = NEW.obligation_id);
    END""",
    """CREATE TRIGGER IF NOT EXISTS trg_alloc_upd BEFORE UPDATE ON allocations WHEN NEW.active
    BEGIN
      SELECT RAISE(ABORT, 'INVARIANT: allocations exceed credit amount')
        WHERE (SELECT COALESCE(SUM(amount_paise),0) FROM allocations WHERE credit_id = NEW.credit_id AND active AND alloc_id <> NEW.alloc_id) + NEW.amount_paise
            > (SELECT amount_paise FROM bank_credits WHERE credit_id = NEW.credit_id);
      SELECT RAISE(ABORT, 'INVARIANT: allocations exceed required amount')
        WHERE (SELECT COALESCE(SUM(amount_paise),0) FROM allocations WHERE obligation_id = NEW.obligation_id AND active AND alloc_id <> NEW.alloc_id) + NEW.amount_paise
            > (SELECT amount_paise FROM obligations WHERE obligation_id = NEW.obligation_id);
    END""",
    # event stores are insert-only
    """CREATE TRIGGER IF NOT EXISTS trg_kernel_events_no_delete BEFORE DELETE ON kernel_events
    BEGIN SELECT RAISE(ABORT, 'INVARIANT: kernel_events is insert-only'); END""",
    """CREATE TRIGGER IF NOT EXISTS trg_portal_events_no_delete BEFORE DELETE ON portal_events
    BEGIN SELECT RAISE(ABORT, 'INVARIANT: portal_events is insert-only'); END""",
]

POSTGRES = [
    """CREATE OR REPLACE FUNCTION tl_check_allocation() RETURNS trigger AS $$
    DECLARE credit_amt bigint; credit_kind text; req bigint; used_c bigint; used_o bigint;
    BEGIN
      IF NOT NEW.active THEN RETURN NEW; END IF;
      SELECT amount_paise, kind INTO credit_amt, credit_kind FROM bank_credits WHERE credit_id = NEW.credit_id FOR UPDATE;
      SELECT amount_paise INTO req FROM obligations WHERE obligation_id = NEW.obligation_id FOR UPDATE;
      IF credit_kind <> 'deposit' THEN RAISE EXCEPTION 'INVARIANT: returned-payment credit cannot be allocated'; END IF;
      SELECT COALESCE(SUM(amount_paise),0) INTO used_c FROM allocations WHERE credit_id = NEW.credit_id AND active AND alloc_id <> NEW.alloc_id;
      SELECT COALESCE(SUM(amount_paise),0) INTO used_o FROM allocations WHERE obligation_id = NEW.obligation_id AND active AND alloc_id <> NEW.alloc_id;
      IF used_c + NEW.amount_paise > credit_amt THEN RAISE EXCEPTION 'INVARIANT: allocations exceed credit amount'; END IF;
      IF used_o + NEW.amount_paise > req THEN RAISE EXCEPTION 'INVARIANT: allocations exceed required amount'; END IF;
      RETURN NEW;
    END $$ LANGUAGE plpgsql""",
    "DROP TRIGGER IF EXISTS trg_alloc ON allocations",
    "CREATE TRIGGER trg_alloc BEFORE INSERT OR UPDATE ON allocations FOR EACH ROW EXECUTE FUNCTION tl_check_allocation()",
    """CREATE OR REPLACE FUNCTION tl_insert_only() RETURNS trigger AS $$
    BEGIN RAISE EXCEPTION 'INVARIANT: % is insert-only', TG_TABLE_NAME; END $$ LANGUAGE plpgsql""",
    "DROP TRIGGER IF EXISTS trg_kernel_events_io ON kernel_events",
    "CREATE TRIGGER trg_kernel_events_io BEFORE UPDATE OR DELETE ON kernel_events FOR EACH ROW EXECUTE FUNCTION tl_insert_only()",
    "DROP TRIGGER IF EXISTS trg_portal_events_io ON portal_events",
    "CREATE TRIGGER trg_portal_events_io BEFORE UPDATE OR DELETE ON portal_events FOR EACH ROW EXECUTE FUNCTION tl_insert_only()",
]


def install(conn: Connection) -> None:
    stmts = POSTGRES if conn.dialect.name == "postgresql" else SQLITE
    for s in stmts:
        conn.execute(text(s))
