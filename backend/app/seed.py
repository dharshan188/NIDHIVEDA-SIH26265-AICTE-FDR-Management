"""Seed data, built THROUGH the kernel (every FDR, confirmation, NOC and payment is a real kernel event).

Target mix (portal FDRs): 612 active/verified (>90 days to maturity), 56 maturing (≤90 days), 27 pending,
18 discrepancy, 64 released, 44 closed = 821. Plus online (RTGS) deposits for the payment views.
Dates are relative to the server's current date. Deterministic for a given date.
"""
from __future__ import annotations

import hashlib
import json
import random
import secrets
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from .crypto import blind_index, encrypt_field, seal_pii
from . import models as m
from . import portal_audit
from .bank.simulator import BANKS, FINANCE_BANK, IFSC_PREFIX, public_key_b64, sign
from .config import BACKEND_DIR, get_settings
from .ledger import LEDGER
from .projections import refresh_fdr
from .security import hash_password, issue_dev_dsc, new_totp_secret

STATES = [("Tamil Nadu", ["Chennai", "Coimbatore", "Madurai", "Salem"]), ("Maharashtra", ["Pune", "Mumbai", "Nagpur", "Nashik"]),
          ("Karnataka", ["Bengaluru", "Mysuru", "Mangaluru"]), ("Uttar Pradesh", ["Lucknow", "Noida", "Kanpur"]),
          ("Andhra Pradesh", ["Visakhapatnam", "Vijayawada", "Guntur"]), ("Telangana", ["Hyderabad", "Warangal"]),
          ("Kerala", ["Kochi", "Thiruvananthapuram"]), ("Gujarat", ["Ahmedabad", "Vadodara", "Surat"]), ("Rajasthan", ["Jaipur", "Jodhpur", "Kota"]),
          ("West Bengal", ["Kolkata", "Durgapur"]), ("Madhya Pradesh", ["Bhopal", "Indore"]), ("Punjab", ["Ludhiana", "Mohali"]),
          ("Haryana", ["Gurugram", "Faridabad"]), ("Odisha", ["Bhubaneswar", "Cuttack"]), ("Delhi", ["New Delhi"]), ("Bihar", ["Patna"])]
PREFIX = ["Sri Krishna", "Rajalakshmi", "Vel Tech", "Shivaji", "Annamalai", "Kongu", "Sardar Patel", "Maharaja", "Bharati", "Saraswati",
          "Swami Vivekananda", "Gokaraju", "Malla Reddy", "Sinhgad", "Bharathiyar", "Mahendra", "Jawaharlal Nehru", "Guru Nanak", "Chaitanya",
          "Sree Narayana", "Vidya Jyothi", "Sri Sairam", "Panimalar", "Vasavi", "Siddhartha", "Lakshmi Narain", "Netaji Subhas", "Kalinga",
          "Shri Ram", "Acharya", "Dayananda Sagar", "Sapthagiri", "Bapuji", "Nitte", "Gayatri", "Aditya", "Krishna", "Rajiv Gandhi"]
SUFFIX = ["College of Engineering", "Institute of Technology", "Engineering College", "Institute of Management Studies", "College of Pharmacy",
          "Polytechnic College", "Institute of Engineering & Technology", "School of Architecture", "College of Technology"]
TYPES = ["Private-Self Financing"] * 4 + ["Private University", "Deemed University"]
NAMED = [("ABC Engineering College", "Tamil Nadu", "Coimbatore"), ("XYZ Institute of Technology", "Maharashtra", "Pune"),
         ("LMN College of Engineering", "Karnataka", "Mysuru"), ("PQR Institute", "Telangana", "Hyderabad"),
         ("DEF College of Engineering", "Uttar Pradesh", "Noida"), ("GHI College", "Kerala", "Kochi"), ("JKL Institute", "Gujarat", "Ahmedabad"),
         ("MNO College", "Rajasthan", "Jaipur"), ("STU Engineering College", "Andhra Pradesh", "Guntur")]
LAKH = 100_000 * 100
SECTION = "section_officer:kiran"
APPROVER = "director:sharma"


@dataclass(order=True)
class Act:
    at: str
    n: int
    fn: Callable = field(compare=False)


class Seeder:
    def __init__(self, db: Session, today: date) -> None:
        self.db, self.today = db, today
        self.r = random.Random(26265)
        self.acts: list[Act] = []
        self.portal_rows: list = []
        self.msgs: list[m.BankMessage] = []
        self.fdr_meta: dict[str, dict] = {}
        self._n = 0

    # -------------------------------------------------------------- helpers
    def at(self, d: date, h: int | None = None, mi: int | None = None) -> str:
        h = self.r.randint(9, 17) if h is None else h
        mi = self.r.randint(0, 59) if mi is None else mi
        return datetime(d.year, d.month, d.day, h, mi).isoformat(timespec="seconds")

    def add(self, at: str, fn: Callable) -> None:
        self._n += 1
        self.acts.append(Act(at, self._n, fn))

    def evidence(self, k, eid: str, bank: str, kind: str, payload: dict, at: str, ref: str | None = None) -> None:
        env = sign(bank, f"{bank}-K1", kind, payload, signed_at=at)
        k.record_bank_evidence(eid, env, at)
        self.msgs.append(m.BankMessage(received_at=at, channel=kind, kind=kind, bank=bank, key_id=env["key_id"], signed_at=at, payload=seal_pii(env["payload"]),
                                       signature=env["signature"], evidence_id=eid, status="ACCEPTED", simulated=True, ref=ref))

    def d(self, days: int) -> date:
        return self.today + timedelta(days=days)

    # -------------------------------------------------------------- build
    def institutions(self) -> list[m.Institution]:
        r, used, out = self.r, set(), []
        for i in range(482):
            if i < len(NAMED):
                name, state, city = NAMED[i]
                typ = "Private-Self Financing"
            else:
                state, cities = r.choice(STATES)
                city, typ = r.choice(cities), r.choice(TYPES)
                while True:
                    name = f"{r.choice(PREFIX)} {r.choice(SUFFIX)}" + (f", {city}" if r.random() < 0.45 else "")
                    if name not in used:
                        break
            used.add(name)
            slug = "".join(c for c in name.lower() if c.isalpha())[:14]
            out.append(m.Institution(id=f"INST{i + 1:04d}", aicte_id="1-12345678" if i == 0 else f"1-{r.randint(10_000_000, 49_999_999)}", name=name,
                                     type=typ, state=state, city=city, email=f"principal@{slug}.edu.in", phone=f"+91 {r.randint(70000, 99999)} {r.randint(10000, 99999)}",
                                     principal=f"Dr. {r.choice('RSKAMVPN')}. {r.choice(['Kumar', 'Sharma', 'Iyer', 'Reddy', 'Nair', 'Patil', 'Gupta', 'Singh'])}",
                                     established=r.randint(1962, 2018), intake=r.randint(4, 24) * 60))
        for inst in out:   # PII from a hash of the id (not `r`), stored encrypted
            h = hashlib.sha256(f"pii:{inst.id}".encode()).digest()
            pan = "AAA" + "TCF"[h[0] % 3] + chr(65 + h[1] % 26) + f"{int.from_bytes(h[2:4], 'big') % 10000:04d}" + chr(65 + h[4] % 26)
            inst.pan = encrypt_field(pan)
            inst.registered_mobile = encrypt_field(f"+91{7 + h[5] % 3}{int.from_bytes(h[6:10], 'big') % 1_000_000_000:09d}")
        return out

    def plan_fdrs(self, insts: list[m.Institution]) -> list[dict]:
        """Decide every FDR's fate first, then turn it into time-ordered kernel actions."""
        r, t = self.r, self.today
        plans: list[dict] = []
        banks = list(BANKS)
        amounts = [20, 25, 30, 35, 35, 40, 40, 45, 50]

        def plan(inst, fate, **kw):
            tenure = kw.pop("tenure", r.choice([3, 3, 3, 5, 5]))
            p = {"inst": inst, "fate": fate, "bank": kw.pop("bank", r.choice(banks)), "amount": kw.pop("amount", r.choice(amounts)) * LAKH,
                 "rate_bp": r.choice([680, 700, 710, 725, 750]), "tenure": tenure, **kw}
            if fate in ("pending", "discrepancy"):
                p.setdefault("submitted", self.d(-p.pop("sub_ago", r.randint(13, 60))))
                p.setdefault("issue", p["submitted"] - timedelta(days=r.randint(1, 6)))
                p.setdefault("maturity", p["issue"] + timedelta(days=365 * tenure))
            elif fate in ("released", "closed"):
                p["maturity"] = self.d(-r.randint(20, 900))
                p["issue"] = p["maturity"] - timedelta(days=365 * tenure)
                p["submitted"] = p["issue"] + timedelta(days=r.randint(2, 15))
                rel = max(p["maturity"] + timedelta(days=r.randint(5, 30)), date(2024, 2, 1) + timedelta(days=r.randint(0, 60)))
                p["release"] = min(rel, self.d(-4))
            else:  # verified
                if "mat_in" in p:
                    p["maturity"] = self.d(p.pop("mat_in"))
                    p["issue"] = p["maturity"] - timedelta(days=365 * tenure)
                elif "issue" not in p:
                    p["issue"] = self.d(-r.randint(20, 365 * tenure - 100))
                    p["maturity"] = p["issue"] + timedelta(days=365 * tenure)
                p.setdefault("submitted", min(p["issue"] + timedelta(days=r.randint(1, 6)), self.d(-14 - r.randint(0, 5))))
            plans.append(p)
            return p

        abc, xyz, lmn, pqr, defc, ghi, jkl, mno, stu = insts[:9]
        plan(abc, "verified", id="FDR202600125", bank="SBI", amount=35, issue=self.d(-13), maturity=self.d(-13 + 1096), submitted=self.d(-13), sub_h=(10, 15))
        plan(abc, "pending", id="FDR202600126", bank="HDFC", amount=35, issue=self.d(-8), maturity=self.d(-8 + 1096), submitted=self.d(-8), sub_h=(11, 42))
        plan(xyz, "verified", id="FDR202600124", bank="HDFC", amount=50, issue=self.d(-15), maturity=self.d(-15 + 1096), submitted=self.d(-9))
        plan(lmn, "discrepancy", id="FDR202600123", bank="ICICI", amount=25, issue=self.d(-18), maturity=self.d(-18 + 1096), submitted=self.d(-10),
             why="principal")
        plan(pqr, "pending", id="FDR202600122", bank="CANARA", amount=40, issue=self.d(-22), maturity=self.d(-22 + 1096), submitted=self.d(-11))
        plan(defc, "verified", id="FDR202600121", bank="PNB", amount=30, issue=self.d(-25), maturity=self.d(-25 + 1096), submitted=self.d(-12))
        for inst, din, amt in ((ghi, 2, 40), (jkl, 10, 30), (mno, 23, 25), (pqr, 36, 50), (stu, 43, 35)):
            plan(inst, "verified", mat_in=din, amount=amt)

        rest = insts[1:]
        no_valid, valid = rest[-14:], rest[:-14]

        def count(f, maturing=None):
            return sum(1 for p in plans if p["fate"] == f and (maturing is None or ((p["maturity"] - t).days <= 90) == maturing))

        for inst in valid:
            if not any(p["inst"] is inst and p["fate"] == "verified" for p in plans):
                plan(inst, "verified")
        pool = valid[:]
        r.shuffle(pool)
        while count("verified", False) < 612:
            plan(pool.pop() if pool else r.choice(valid), "verified")
        pool = valid[:]
        r.shuffle(pool)
        while count("verified", True) < 56:
            plan(pool.pop(), "verified", mat_in=r.randint(3, 89))
        pool = valid[8:]
        r.shuffle(pool)
        while count("pending") < 27:
            plan(pool.pop(), "pending", sub_ago=r.randint(13, 45), bank_differs=count("pending") in (5, 11, 19))
        whys = ["principal", "lien", "maturity", "principal", "lien", "document"]
        while count("discrepancy") < 18:
            plan(pool.pop(), "discrepancy", why=whys[count("discrepancy") % len(whys)])
        for inst in no_valid:
            plan(inst, r.choice(["released", "closed"]))
        while count("released") < 64:
            plan(r.choice(valid), "released")
        while count("closed") < 44:
            plan(r.choice(valid), "closed")
        # FDR numbers and portal ids
        seq: dict[int, int] = {}
        for p in plans:
            p["no"] = f"{IFSC_PREFIX[p['bank']]}FD{r.randint(10**9, 10**10 - 1)}"
            if "id" not in p:
                y = p["issue"].year
                seq[y] = seq.get(y, 200) + 1
                p["id"] = f"FDR{y}{seq[y]:05d}"
        return plans

    def schedule_fdr(self, p: dict) -> None:
        r = self.r
        inst, fid = p["inst"], p["id"]
        oid, iid = f"OBL-{fid}", f"INS-{fid}"
        actor = f"institution:{inst.id}"
        h = p.get("sub_h", (None, None))
        sub_at = self.at(p["submitted"], *h)
        bank_principal, bank_lien, bank_mat, bank_status = p["amount"], "AICTE", p["maturity"].isoformat(), "ACTIVE"
        why = p.get("why")
        if p.get("bank_differs") or why == "principal":
            bank_principal = p["amount"] - 5 * LAKH
        if why == "lien":
            bank_lien = "NONE"
        if why == "maturity":
            bank_mat = (p["maturity"] - timedelta(days=365)).isoformat()
        self.fdr_meta[fid] = {"plan": p, "sub_at": sub_at}

        def submit(k, p=p):
            k.create_obligation(oid, inst.id, "Security deposit", p["amount"], "FDR", sub_at, actor=actor)
            k.register_instrument(iid, oid, p["no"], p["bank"], p["amount"], p["issue"].isoformat(), p["maturity"].isoformat(), sub_at, actor)

        self.add(sub_at, submit)
        sim_status = "ACTIVE"
        if p["fate"] in ("verified", "discrepancy") and why != "document":
            conf_day = min(p["submitted"] + timedelta(days=r.randint(1, 6)), self.d(-1))
            conf_at = self.at(conf_day)

            def confirm(k, p=p, conf_at=conf_at):
                self.evidence(k, f"E-IC-{fid}-1", p["bank"], "instrument_confirmation",
                              {"instrument_no": p["no"], "as_of": conf_at[:10], "status": bank_status, "lien_holder": bank_lien,
                               "amount": bank_principal, "maturity_date": bank_mat}, conf_at, ref=fid)

            self.add(conf_at, confirm)
            p["verified_at"] = conf_at
        if p["fate"] == "discrepancy" and why == "document":
            p["doc_reason"] = "Bank covering letter missing authorised signatory's signature"
        if p["fate"] in ("released", "closed"):
            rel = p["release"]
            ent_at, conf_at, noc_at = self.at(rel - timedelta(days=2)), self.at(rel - timedelta(days=1)), self.at(rel, 11)
            dis_at = self.at(rel + timedelta(days=min(3, (self.today - rel).days - 1)), 15)
            basis = "Superseded by renewed FDR; release of matured instrument" if p["fate"] == "closed" else "Deposit term completed; release on entitlement"

            def ent(k, p=p):
                k.record_entitlement(oid, basis, ent_at, SECTION)
                k.record_affidavit(oid, "AFFIDAVIT-6", True, ent_at, SECTION)

            def conf(k, p=p):
                self.evidence(k, f"E-IC-{fid}-R", p["bank"], "instrument_confirmation",
                              {"instrument_no": p["no"], "as_of": conf_at[:10], "status": "ACTIVE", "lien_holder": "AICTE", "amount": p["amount"],
                               "maturity_date": p["maturity"].isoformat()}, conf_at, ref=fid)

            def noc(k, p=p):
                k.authorise_release(f"NOC-{fid}", oid, noc_at, APPROVER)

            def dis(k, p=p):
                self.evidence(k, f"E-LD-{fid}", p["bank"], "lien_discharge", {"instrument_no": p["no"], "discharged_on": dis_at[:10]}, dis_at, ref=fid)

            for a, f in ((ent_at, ent), (conf_at, conf), (noc_at, noc), (dis_at, dis)):
                self.add(a, f)
            sim_status, bank_lien = "LIEN_DISCHARGED", "NONE"
            p["release_rows"] = (ent_at, noc_at, dis_at)
        self.portal_rows.append(m.SimBankFdr(bank=p["bank"], instrument_no=p["no"], principal_paise=bank_principal, maturity_date=bank_mat,
                                             status=sim_status, lien_holder=bank_lien))

    # -------------------------------------------------------------- online deposits and payments
    def schedule_online(self, insts: list[m.Institution]) -> None:
        abc, xyz, lmn, pqr, defc, ghi = insts[:6]
        t = self.today
        pay_accounts = {}

        def acct(inst, n):
            return f"{inst.id[-4:]}{n:08d}"

        cases = [  # (inst, obligation id, lakh, credit utr, basis, narrative ref?, remitter account known?)
            (xyz, "ONL-XYZ-UG", 35, "UTR-XYZ-2016-0042", "machine_reference", True, True),
            (lmn, "ONL-LMN-UG", 35, "UTR-LMN-2017-0507", "machine_reference", True, True),
            (lmn, "ONL-LMN-PG", 15, "UTR-LMN-2017-0507", "machine_reference", True, True),   # one 50 L credit split 35 + 15
            (pqr, "ONL-PQR-UG", 20, "UTR-PQR-2015-1188", "institution_declaration", False, False),  # declared, not certifiable
            (defc, "ONL-DEF-UG", 35, "UTR-DEF-2016-0311", "institution_declaration", False, True),  # corroborated by remitter account
            (ghi, "ONL-GHI-UG", 35, "UTR-GHI-2016-0909", "machine_reference", True, True),
            (abc, "ONL-ABC-PG", 15, "UTR-ABC-2018-0215", "machine_reference", True, True),
        ]
        credits = {"UTR-LMN-2017-0507": 50}
        for inst in (abc, xyz, lmn, pqr, defc, ghi):
            pay_accounts[inst.id] = (acct(inst, 5010), f"{IFSC_PREFIX[FINANCE_BANK]}000{self.r.randint(1000, 9999)}")

        def reg(k):
            for inst in (abc, xyz, lmn, pqr, defc, ghi):
                k.register_institution(inst.id, inst.name, "2015-01-01T09:00:00", known_accounts=[pay_accounts[inst.id][0]])
        self.add("2015-01-01T09:00:00", reg)
        for inst, oid, lakh, utr, basis, ref, known in cases:
            year = int(utr.split("-")[2])
            at_obl = f"{year}-05-02T09:00:00"
            at_cr = f"{year}-06-01T10:00:00"
            at_al = f"{year}-06-01T12:00:00"
            reference = f"AICTE-APP-{oid[-6:]}"

            def obl(k, inst=inst, oid=oid, lakh=lakh, at_obl=at_obl, reference=reference):
                k.create_obligation(oid, inst.id, oid.split("-")[-1] + " programme", lakh * LAKH, "ONLINE", at_obl, reference=reference)
            self.add(at_obl, obl)
            if utr not in [c for c in getattr(self, "_seen_utr", [])]:
                self._seen_utr = getattr(self, "_seen_utr", []) + [utr]
                amt = credits.get(utr, lakh)
                narrative = " ".join(f"AICTE-APP-{c[1][-6:]}" for c in cases if c[3] == utr) + " security deposit" if ref else "deposit"

                def cr(k, inst=inst, utr=utr, amt=amt, narrative=narrative, at_cr=at_cr, known=known):
                    self.evidence(k, f"E-CR-{utr}", FINANCE_BANK, "credit_advice",
                                  {"utr": utr, "amount": amt * LAKH, "value_date": at_cr[:10], "remitter_name": inst.name if known else "Trust account (unnamed)",
                                   "remitter_account": pay_accounts[inst.id][0] if known else "UNKNOWN-0000", "narrative": narrative,
                                   "beneficiary_account": "AICTE-POOL-0001"}, at_cr, ref=utr)
                self.add(at_cr, cr)

            def al(k, oid=oid, utr=utr, lakh=lakh, basis=basis, at_al=at_al):
                k.allocate(f"AL-{oid}", f"CR-{utr}", oid, lakh * LAKH, basis, at_al, "system:auto_match" if basis == "machine_reference" else "finance_reconciliation_officer:anil")
            self.add(at_al, al)

        # payees + bank name look-ups, recent
        for inst in (abc, xyz, lmn, pqr, defc, ghi):
            a, ifsc = pay_accounts[inst.id]
            self.portal_rows.append(m.SimBankAccount(ifsc=ifsc, account=blind_index(a), account_enc=encrypt_field(a), bank=FINANCE_BANK,
                                                     name_at_bank=inst.name, status="OPEN"))
            pay_at = self.at(t - timedelta(days=40))
            lk_at = self.at(t - timedelta(days=39))

            def payee(k, inst=inst, a=a, ifsc=ifsc, pay_at=pay_at):
                k.register_payee(inst.id, a, ifsc, inst.name, pay_at, f"institution:{inst.id}")
            self.add(pay_at, payee)
            if inst is not pqr:
                def lookup(k, inst=inst, a=a, ifsc=ifsc, lk_at=lk_at):
                    self.evidence(k, f"E-NL-{inst.id}", FINANCE_BANK, "name_lookup", {"account": a, "ifsc": ifsc, "name_at_bank": inst.name}, lk_at, ref=inst.id)
                self.add(lk_at, lookup)

        # entitlement + affidavit for the ones going to release
        for oid, days in (("ONL-XYZ-UG", 6), ("ONL-DEF-UG", 30), ("ONL-GHI-UG", 9), ("ONL-ABC-PG", 12), ("ONL-LMN-UG", 5)):
            e_at = self.at(t - timedelta(days=days), 10, 0)

            def ent(k, oid=oid, e_at=e_at):
                k.record_entitlement(oid, "Programme closure approved; deposit refundable", e_at, SECTION)
                k.record_affidavit(oid, "AFFIDAVIT-6", True, e_at, SECTION)
            self.add(e_at, ent)
        # DEF: refund already settled (history)
        self._payment("ONL-DEF-UG", "RF-SEED-DEF", t - timedelta(days=28), settle=True)
        # GHI: debited yesterday, positive confirmation never arrived -> "Sent, not complete"
        self._payment("ONL-GHI-UG", "RF-SEED-GHI", t - timedelta(days=1), settle=False)
        # ABC: refund returned by the bank -> REISSUE_REQUIRED
        self._payment("ONL-ABC-PG", "RF-SEED-ABC", t - timedelta(days=10), settle=False, ret="BENEFICIARY_BANK_REJECT")
        self.pay_accounts = pay_accounts

    def _payment(self, oid, rid, day: date, settle: bool, ret: str | None = None) -> None:
        a1, a2, a3, a4 = (self.at(day, 10, 0), self.at(day, 11, 0), self.at(day, 11, 5), self.at(day, 11, 40))

        def auth(k):
            k.authorise_release(rid, oid, a1, "deputy_director:meera", rail="RTGS")
        self.add(a1, auth)
        self.add(a2, lambda k: k.initiate_payment(rid, a2, "finance_officer:ravi"))
        utr = f"SBINR5{day:%Y%m%d}{abs(hash(rid)) % 10**6:06d}"

        def debit(k):
            self.evidence(k, f"E-DR-{rid}", FINANCE_BANK, "debit_advice", {"refund_id": rid, "utr": utr, "amount": k.refunds[rid]["amount"],
                                                                           "remitter": "AICTE", "date": a3[:10]}, a3, ref=rid)
        self.add(a3, debit)
        if settle:
            self.add(a4, lambda k: self.evidence(k, f"E-CC-{rid}", FINANCE_BANK, "credit_confirmation",
                                                 {"utr": utr, "amount": k.refunds[rid]["amount"], "beneficiary_account": k.refunds[rid]["paying_to"],
                                                  "credited_at": a4}, a4, ref=rid))
        if ret:
            self.add(a4, lambda k: self.evidence(k, f"E-RT-{rid}", FINANCE_BANK, "return_advice",
                                                 {"original_utr": utr, "return_utr": utr.replace("SBINR5", "SBINRR"), "amount": k.refunds[rid]["amount"],
                                                  "reason_code": ret, "returned_at": a4}, a4, ref=rid))

    # -------------------------------------------------------------- run
    def run(self) -> dict:
        db = self.db
        insts = self.institutions()
        db.add_all(insts)
        db.commit()
        for code in BANKS:
            db.add(m.BankSigner(key_id=f"{code}-K1", bank=code, public_key=public_key_b64(f"{code}-K1"), valid_from="2010-01-01"))
        db.commit()

        def signers(k):
            for code in BANKS:
                k.register_signer(f"{code}-K1", code, public_key_b64(f"{code}-K1"), "2010-01-01", "2010-01-01T00:00:00")
        self.add("2010-01-01T00:00:00", signers)
        online_insts = {i.id for i in insts[:6]}

        def reg_rest(k):
            for inst in insts:
                if inst.id not in online_insts:
                    k.register_institution(inst.id, inst.name, "2015-01-01T09:00:00")
        self.add("2015-01-01T09:00:00", reg_rest)
        self.schedule_online(insts)
        plans = self.plan_fdrs(insts)
        for p in plans:
            self.schedule_fdr(p)
        self.acts.sort()
        batch = 400
        for i in range(0, len(self.acts), batch):
            chunk = self.acts[i:i + batch]
            LEDGER.run(db, lambda k, chunk=chunk: [a.fn(k) for a in chunk])
        db.add_all(self.portal_rows)
        db.add_all(self.msgs)
        db.commit()
        self.portal(plans, insts)
        return {"institutions": len(insts), "fdrs": len(plans), "kernel_events": len(LEDGER.kernel().store)}

    def portal(self, plans: list[dict], insts: list[m.Institution]) -> None:
        db, k, r = self.db, LEDGER.kernel(), self.r
        for p in plans:
            fid = p["id"]
            f = m.Fdr(id=fid, institution_id=p["inst"].id, obligation_id=f"OBL-{fid}", instrument_id=f"INS-{fid}", bank=p["bank"],
                      branch=f"{p['inst'].city} Main Branch", instrument_no=p["no"], amount_paise=p["amount"], rate_bp=p["rate_bp"],
                      issue_date=p["issue"], maturity_date=p["maturity"], submitted_on=datetime.fromisoformat(self.fdr_meta[fid]["sub_at"]),
                      status="pending", scrutinised=p["fate"] in ("verified", "released", "closed"),
                      discrepancy_reason=p.get("doc_reason"),
                      closed_reason="Superseded by renewed FDR" if p["fate"] == "closed" else None)
            db.add(f)
            db.flush()
            sub = datetime.fromisoformat(self.fdr_meta[fid]["sub_at"])
            # A few live FDRs were filed without the lien letter: the missing-documents report must find them. Chosen from a hash
            # of the id, not from `r`, so the other seeded figures stay exactly as before.
            no_lien = p["fate"] in ("pending", "discrepancy", "verified") and hashlib.sha256(fid.encode()).digest()[0] < 10
            for name, size, kind in ((f"{fid}_scan.pdf", r.randint(280, 980), "fdr_scan"), ("Bank_lien_letter.pdf", r.randint(120, 420), "lien_letter")):
                if kind == "lien_letter" and no_lien:
                    continue
                db.add(m.FdrDocument(fdr_id=fid, name=name, size_bytes=size * 1024, sha256=hashlib.sha256(f"{fid}{name}".encode()).hexdigest(),
                                     uploaded_on=sub, stored=False, doc_type=kind))
            refresh_fdr(db, k, f)
            if p.get("release_rows"):
                ent_at, noc_at, dis_at = p["release_rows"]
                db.add(m.ReleaseRequest(id=f"REL-{fid}", obligation_id=f"OBL-{fid}", fdr_id=fid, institution_id=p["inst"].id,
                                        reason="Deposit term completed" if p["fate"] == "released" else "Superseded by renewed FDR", stage="COMPLETED",
                                        raised_by=f"institution:{p['inst'].id}", raised_on=datetime.fromisoformat(ent_at) - timedelta(days=5),
                                        scrutiny_by=SECTION, approved_by=APPROVER, case_id=f"NOC-{fid}", updated_on=datetime.fromisoformat(dis_at)))
        db.commit()
        # renewals already on record: some maturing FDRs have a newer verified FDR from the same institution
        fd = {p["id"]: p for p in plans}
        maturing = sorted((p for p in plans if p["fate"] == "verified" and (p["maturity"] - self.today).days <= 90), key=lambda p: p["maturity"])
        for i, p in enumerate(maturing):
            if i < 5 or i % 3 == 2:
                continue
            repl = next((q for q in plans if q["inst"] is p["inst"] and q is not p and q["fate"] == "verified"
                         and (q["maturity"] - self.today).days > 90 and not q.get("renewal_of")), None)
            if repl:
                repl["renewal_of"] = p["id"]
                db.get(m.Fdr, p["id"]).renewed_by = repl["id"]
                db.get(m.Fdr, repl["id"]).renewal_of = p["id"]
        # open release requests (12): some new, some past scrutiny
        candidates = [p for p in plans if p["fate"] == "verified" and (p["maturity"] - self.today).days > 120 and p["inst"].id not in ("INST0001",)][20:32]
        now = datetime.now()
        for i, p in enumerate(candidates):
            rid = f"REL{now.year}{41 + i:05d}"
            raised = now - timedelta(days=self.r.randint(2, 40))
            db.add(m.ReleaseRequest(id=rid, obligation_id=f"OBL-{p['id']}", fdr_id=p["id"], institution_id=p["inst"].id,
                                    reason=self.r.choice(["Closure of programme approved by AICTE", "Reduction in approved intake", "Replacement with a higher-value FDR"]),
                                    stage="SUBMITTED", raised_by=f"institution:{p['inst'].id}", raised_on=raised, updated_on=raised))
        db.commit()
        _ = fd


def seed_users(db: Session) -> list[dict]:
    """Demo accounts. Passwords come from TL_DEMO_PASSWORD, or are random and written to a gitignored file."""
    cfg = get_settings()
    rows = [
        ("meera@aicte-india.org", "Meera Iyer", "AICTE_OFFICIAL", "deputy_director", "Deputy Director, Regulation Bureau", None, "sso-meera"),
        ("kiran@aicte-india.org", "Kiran Rao", "AICTE_OFFICIAL", "section_officer", "Section Officer (Scrutiny)", None, None),
        ("ravi@aicte-india.org", "Ravi Menon", "AICTE_OFFICIAL", "finance_officer", "Finance Officer", None, None),
        ("anil@aicte-india.org", "Anil Gupta", "AICTE_OFFICIAL", "finance_reconciliation_officer", "Finance Reconciliation Officer", None, None),
        ("legal@aicte-india.org", "Legal Cell", "AICTE_OFFICIAL", "legal_cell", "Legal Cell", None, None),
        ("sharma@aicte-india.org", "Dr. A. Sharma", "AICTE_OFFICIAL", "director", "Director, Regulation Bureau", None, None),
        ("auditor@aicte-india.org", "Internal Audit", "AUDITOR", "internal_audit", "Independent Review", None, "sso-auditor"),
        ("1-12345678", "ABC Engineering College", "INSTITUTION", "institution", "Institution", "INST0001", "sso-abc"),
        ("1-xyz-demo", "XYZ Institute of Technology", "INSTITUTION", "institution", "Institution", "INST0002", None),
    ]
    out = []
    for username, name, role, krole, desig, inst, sso in rows:
        if db.scalars(select(m.User).where(m.User.username == username)).first():
            continue
        pw = cfg.demo_password or secrets.token_urlsafe(10)
        _, totp_enc = new_totp_secret()
        dsc = issue_dev_dsc(username) if cfg.is_dev and krole in ("deputy_director", "director", "section_officer", "internal_audit", "institution") else None
        h = hashlib.sha256(f"mobile:{username}".encode()).digest()
        mobile = f"+91{7 + h[0] % 3}{int.from_bytes(h[1:5], 'big') % 1_000_000_000:09d}"
        db.add(m.User(username=username, full_name=name, password_hash=hash_password(pw), role=role, kernel_role=krole, designation=desig,
                      institution_id=inst, mobile_masked="••••••" + mobile[-4:], mobile=encrypt_field(mobile), totp_secret_enc=totp_enc,
                      dsc_serial=dsc, sso_subject=sso))
        out.append({"username": username, "password": pw, "role": role, "kernel_role": krole, "name": name})
    db.commit()
    if cfg.is_dev and out and not cfg.demo_password:
        path = BACKEND_DIR / ".dev-credentials.json"
        path.write_text(json.dumps(out, indent=1))
        path.chmod(0o600)
    return out


def seed_all(db: Session, today: date | None = None) -> dict:
    if db.scalars(select(m.Institution).limit(1)).first():
        return {"skipped": "database already seeded"}
    from trustledger.kernel import load_policy
    db.add(m.PolicyVersion(created_at=datetime.now(), created_by="system:seed", reason="initial (kernel data/policy.json)", policy=load_policy()))
    db.commit()
    stats = Seeder(db, today or date.today()).run()
    users = seed_users(db)
    # pooled-balance confirmation equal to the ledger's expected pool, so the aggregate can be certified
    from .bank.deliver import deliver
    from .bank.simulator import gateway
    exp = LEDGER.kernel().certification_report()["expected_pool_from_ledger"]
    deliver(db, gateway(db).pooled_balance.balance(FINANCE_BANK, exp, date.today().isoformat()), evidence_id="E-POOL-SEED", ref="pool")
    db.add_all([
        m.Message(institution_id="INST0001", sender="institution", author="1-12345678", at=datetime.now() - timedelta(days=8), text="We have uploaded FDR202600126 issued by HDFC Bank. Kindly verify."),
        m.Message(institution_id="INST0001", sender="aicte", author="kiran@aicte-india.org", at=datetime.now() - timedelta(days=7), text="Received. A confirmation request has been raised with HDFC Bank."),
    ])
    portal_audit.record(db, "seeded", "system:seed", {**stats, "users": len(users)})
    # Seeded notices are history: they are in the notification centre but must not be sent out again by the worker.
    db.execute(update(m.Notification).where(m.Notification.planned_at.is_(None)).values(planned_at=m.Notification.at))
    db.commit()
    return {**stats, "users": [u["username"] for u in users]}
