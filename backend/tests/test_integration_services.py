"""Against real local services (mandatory in the baseline via --require-services):
  TL_TEST_CLAMD=host:port          ClamAV daemon (docker-compose service `clamav`)
  TL_TEST_S3=endpoint,access,secret S3-compatible store (docker-compose service `objectstore`)
"""
from __future__ import annotations

import uuid

from app import crypto
from app.scanner import EICAR, ClamdScanner
from app.storage import S3Store
from test_documents_security import pdf

def test_clamav_passes_clean_pdf_and_flags_eicar(service_config):
    host, port = service_config("clamav").split(":")
    sc = ClamdScanner(host, int(port))
    clean = sc.scan(pdf())
    assert clean.clean and clean.engine.startswith("ClamAV")
    # ClamAV's EICAR signature matches the standard 68-byte test file itself (it is a whole-file signature)
    bad = sc.scan(EICAR)
    assert not bad.clean and "eicar" in (bad.signature or "").lower()


def test_s3_store_holds_only_ciphertext(service_config):
    endpoint, access, secret = service_config("s3").split(",")
    # SeaweedFS allocates volumes per bucket. Reuse a test bucket, isolate each
    # test by object key, and remove only that object rather than allocating GB/run.
    st = S3Store(endpoint, access, secret, "tl-integration-tests", secure=False)
    key = f"docs/aa/{uuid.uuid4().hex}"
    plain = pdf()
    sealed = crypto.seal_document(plain, key)
    try:
        st.put(key, sealed.ciphertext)
        assert st.exists(key) and not st.exists(key + "x")
        blob = st.get(key)
        assert blob == sealed.ciphertext and b"%PDF" not in blob
        assert crypto.open_document(blob, sealed.wrapped_dek, sealed.nonce, key) == plain
    finally:
        st.c.remove_object(st.bucket, key)


def test_smtp_adapter_delivers_to_mailpit_once_per_key(service_config):
    import httpx

    from app.nudge.channels import OutMsg, SmtpEmail
    host, port, http = service_config("mailpit").split(":")
    key = f"n9999-email-u{uuid.uuid4().hex[:6]}"
    prov = SmtpEmail(host, int(port), "", "", "NIDHIVEDA <no-reply@test.local>", False, True)
    msg = OutMsg("email", key, "principal@abc.edu.in", "pr•••@abc.edu.in", "institution:INST0001", "hi", "एफडीआर FDRX की परिपक्वता",
                 "हिंदी संदेश", "short", "https://portal/l/x")
    res = prov.send(None, msg)
    assert res.status == "sent" and res.simulated and res.provider_ref == f"<{key}@fdr-trust-ledger>"
    items = httpx.get(f"http://{host}:{http}/api/v1/search", params={"query": f"message-id:{key}@fdr-trust-ledger"}).json()["messages"]
    assert len(items) == 1 and items[0]["Subject"].startswith("एफडीआर")
