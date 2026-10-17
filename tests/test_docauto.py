"""34 deterministic tests for the document automation platform."""

from datetime import datetime, timedelta, timezone

import pytest

from docauto.repository import DocumentStore, RepositoryError
from docauto.metadata import MetadataIndex, MetadataError
from docauto.search import SearchEngine
from docauto.governance import RetentionEngine, RetentionPolicy, GovernanceError
from docauto.security import AccessControl, AccessDenied
from docauto.idp import classify, extract_fields
from docauto.workflow import WorkflowEngine, WorkflowError
from docauto.esign import SignatureService, SignatureError

INVOICE = """INVOICE NO INV-2041
Bill To: Acme Corp
Invoice Date: 2026-03-15
Line item: Widgets x100 @ $12.50
Subtotal: $1250.00
Tax: $100.00
Amount Due: $1350.00
Payment Terms: Net 30
"""

CONTRACT = """MASTER SERVICES AGREEMENT
This Agreement is entered into by and between Globex Inc ("Party A")
and Initech LLC ("Party B").
WHEREAS the parties hereby agree to the following terms and conditions.
Effective Date: 2026-01-01. Term: 24 months.
Termination: either party may terminate with 90 days notice.
Governing Law: State of Delaware.
Signatures below.
"""

RECEIPT = """RECEIPT
Cashier: Jane
Transaction ID: TXN-9918
Payment Method: Credit Card
Total: $42.50
Change Due: $0.00
Thank you for shopping!
"""

POLICY_DOC = """INFORMATION SECURITY POLICY
Purpose: define how all employees must handle company data.
Scope: all employees and contractors.
All employees must complete security training annually.
Compliance violations may result in disciplinary action.
Procedure: report incidents to security@ within 24 hours.
"""


# ---------- repository ----------

def test_ingest_creates_version_1():
    store = DocumentStore()
    v = store.ingest("D1", "hello", {}, user="u1")
    assert v.version == 1
    assert store.version("D1") == 1


def test_ingest_duplicate_id_rejected():
    store = DocumentStore()
    store.ingest("D1", "hello", {}, user="u1")
    with pytest.raises(RepositoryError):
        store.ingest("D1", "other", {}, user="u1")


def test_update_creates_new_version_and_history_immutable():
    store = DocumentStore()
    store.ingest("D1", "v1 content", {}, user="u1")
    v2 = store.update("D1", "v2 content", user="u1", comment="fix typo")
    assert v2.version == 2
    assert store.get_version("D1", 1).content == "v1 content"
    assert store.get_version("D1", 2).content == "v2 content"
    assert [v.version for v in store.history("D1")] == [1, 2]


def test_checkout_lock_blocks_second_user():
    store = DocumentStore()
    store.ingest("D1", "x", {}, user="u1")
    store.checkout("D1", "u1")
    with pytest.raises(RepositoryError):
        store.checkout("D1", "u2")
    with pytest.raises(RepositoryError):
        store.update("D1", "sneaky", user="u2")
    store.checkin("D1", "u1")
    store.checkout("D1", "u2")  # now allowed


def test_checkin_by_wrong_user_rejected():
    store = DocumentStore()
    store.ingest("D1", "x", {}, user="u1")
    store.checkout("D1", "u1")
    with pytest.raises(RepositoryError):
        store.checkin("D1", "u2")


def test_get_version_out_of_range():
    store = DocumentStore()
    store.ingest("D1", "x", {}, user="u1")
    with pytest.raises(RepositoryError):
        store.get_version("D1", 99)


# ---------- metadata ----------

def test_system_metadata_computed_and_custom_queryable():
    idx = MetadataIndex()
    rec = idx.index("D1", "hello world", user="u1",
                    custom={"department": "finance", "doc_type": "invoice"})
    assert rec.system["created_by"] == "u1"
    assert rec.system["size"] == len("hello world".encode())
    assert len(rec.system["checksum"]) == 64
    assert idx.query(department="finance") == ["D1"]
    assert idx.query(department="hr") == []


def test_system_metadata_write_rejected():
    idx = MetadataIndex()
    idx.index("D1", "x", user="u1")
    for field in ("created_by", "created_at", "size", "checksum", "doc_id"):
        with pytest.raises(MetadataError):
            idx.set_custom("D1", field, "tampered")


def test_custom_metadata_settable():
    idx = MetadataIndex()
    idx.index("D1", "x", user="u1")
    idx.set_custom("D1", "tags", ["a", "b"])
    assert idx.get("D1").custom["tags"] == ["a", "b"]


# ---------- security + search ----------

def _access_with_docs():
    access = AccessControl()
    access.set_acl("PUBLIC-DOC", {"read": "viewer"})
    access.set_acl("SECRET-DOC", {"read": "manager"})
    engine = SearchEngine(access)
    engine.index("PUBLIC-DOC", "quarterly revenue report shows growth",
                 {"title": "Q1 report"})
    engine.index("SECRET-DOC", "quarterly revenue report with layoff plans",
                 {"title": "Q1 confidential"})
    return engine


def test_search_security_trimming_hides_denied_docs():
    engine = _access_with_docs()
    results = engine.search("quarterly revenue", user="analyst", role="viewer")
    ids = [r.doc_id for r in results]
    assert "PUBLIC-DOC" in ids
    assert "SECRET-DOC" not in ids
    # Denied doc must not leak even its title via metadata.
    assert not any("confidential" in (r.snippet + str(r.matched_metadata)).lower()
                   for r in results)


def test_search_manager_sees_both():
    engine = _access_with_docs()
    results = engine.search("quarterly revenue", user="boss", role="manager")
    assert {r.doc_id for r in results} == {"PUBLIC-DOC", "SECRET-DOC"}


def test_search_snippet_and_ranking():
    engine = _access_with_docs()
    results = engine.search("layoff", user="boss", role="manager")
    assert results[0].doc_id == "SECRET-DOC"
    assert "layoff" in results[0].snippet.lower()


def test_rbac_deny_records_audit():
    access = AccessControl()
    access.set_acl("D1", {"read": "manager"})
    with pytest.raises(AccessDenied):
        access.check("mallory", "viewer", "D1", "read")
    entries = access.audit.entries()
    assert len(entries) == 1
    assert entries[0].allowed is False
    assert entries[0].user == "mallory"


def test_audit_chain_verifies_and_detects_tamper():
    access = AccessControl()
    access.set_acl("D1", {"read": "viewer"})
    access.check("u1", "viewer", "D1", "read")
    access.check("u2", "editor", "D1", "read")
    assert access.audit.verify_chain() is True
    access.audit.entries()[0].reason = "tampered"
    assert access.audit.verify_chain() is False


def test_default_deny_for_unlisted_action():
    access = AccessControl()
    access.set_acl("D1", {"read": "viewer"})
    with pytest.raises(AccessDenied):
        access.check("u1", "editor", "D1", "delete")


# ---------- governance ----------

def test_disposition_destroys_expired_temp_doc():
    gov = RetentionEngine()
    gov.add_policy(RetentionPolicy("temp", retention_days=90, disposition="destroy"))
    old = datetime.now(timezone.utc) - timedelta(days=100)
    gov.register("T1", "temp", created_at=old)
    results = gov.run_disposition()
    assert results[0].action == "destroyed"
    assert results[0].policy == "temp"  # policy cited


def test_disposition_skips_declared_record():
    gov = RetentionEngine()
    gov.add_policy(RetentionPolicy("contract", retention_days=3650,
                                   disposition="archive"))
    old = datetime.now(timezone.utc) - timedelta(days=4000)
    gov.register("C1", "contract", created_at=old)
    gov.declare_record("C1")
    results = gov.run_disposition()
    assert results[0].action == "skipped_record"
    # Declared records cannot be edited either.
    with pytest.raises(GovernanceError):
        gov.guard_edit("C1")


def test_disposition_not_yet_due_is_untouched():
    gov = RetentionEngine()
    gov.add_policy(RetentionPolicy("invoice", retention_days=7 * 365,
                                   disposition="archive"))
    gov.register("I1", "invoice")  # created now
    assert gov.run_disposition() == []
    assert gov.disposition_log() == []


# ---------- idp ----------

def test_classify_each_doc_type():
    assert classify(INVOICE).doc_type == "invoice"
    assert classify(CONTRACT).doc_type == "contract"
    assert classify(RECEIPT).doc_type == "receipt"
    assert classify(POLICY_DOC).doc_type == "policy"
    assert classify(INVOICE).confidence > 0.5


def test_extract_invoice_fields():
    fields = {f.name: f for f in extract_fields(INVOICE, "invoice")}
    assert fields["total_amount"].value == "1350.00"
    assert fields["document_date"].value == "2026-03-15"
    assert all(f.confidence > 0 and f.source for f in fields.values())


def test_extract_contract_parties_and_term():
    fields = extract_fields(CONTRACT, "contract")
    parties = [f.value for f in fields if f.name == "party"]
    assert "Globex Inc" in parties
    assert "Initech LLC" in parties
    terms = [f.value for f in fields if f.name == "contract_term"]
    assert terms == ["24 months"]


# ---------- workflow ----------

def test_workflow_happy_path():
    wf = WorkflowEngine()
    wf.submit("D1")
    assert wf.state("D1") == "in_review"
    assert wf.queue() == ["D1"]
    wf.review("D1", "approve", reviewer="mgr", rationale="looks good")
    assert wf.state("D1") == "approved"
    assert wf.queue() == []


def test_reject_requires_rationale():
    wf = WorkflowEngine()
    wf.submit("D1")
    with pytest.raises(WorkflowError):
        wf.review("D1", "reject", reviewer="mgr", rationale="   ")
    wf.review("D1", "reject", reviewer="mgr", rationale="missing signature")
    assert wf.state("D1") == "rejected"


def test_changes_requested_can_resubmit():
    wf = WorkflowEngine()
    wf.submit("D1")
    wf.review("D1", "request_changes", reviewer="mgr", rationale="fix date")
    assert wf.state("D1") == "changes_requested"
    wf.resubmit("D1")
    assert wf.state("D1") == "in_review"


def test_illegal_transition_rejected():
    wf = WorkflowEngine()
    with pytest.raises(WorkflowError):
        wf.review("D1", "approve", reviewer="mgr", rationale="x")
    wf.submit("D1")
    wf.review("D1", "approve", reviewer="mgr", rationale="ok")
    with pytest.raises(WorkflowError):
        wf.review("D1", "approve", reviewer="mgr", rationale="again")


def test_sla_breach_detected():
    wf = WorkflowEngine()
    wf.submit("D1", sla_hours=1.0)
    future = datetime.now(timezone.utc) + timedelta(hours=5)
    status = wf.sla_status("D1", now=future)
    assert status["breached"] is True
    assert status["elapsed_hours"] >= 5.0


# ---------- esign ----------

def test_esign_full_flow_and_seal():
    svc = SignatureService()
    content = "final agreement text"
    svc.request_signature("D1", ["alice", "bob"])
    assert svc.pending("D1") == ["alice", "bob"]
    svc.sign("D1", "alice", "I approve", content)
    with pytest.raises(SignatureError):
        svc.seal("D1", content)  # bob hasn't signed
    svc.sign("D1", "bob", "Reviewed and approved", content)
    svc.seal("D1", content)
    assert svc.verify_seal("D1", content) is True


def test_esign_verify_seal_detects_tampering():
    svc = SignatureService()
    svc.request_signature("D1", ["alice"])
    svc.sign("D1", "alice", "I approve", "original")
    svc.seal("D1", "original")
    assert svc.verify_seal("D1", "modified") is False


def test_esign_rejects_unknown_signer_and_empty_intent():
    svc = SignatureService()
    svc.request_signature("D1", ["alice"])
    with pytest.raises(SignatureError):
        svc.sign("D1", "mallory", "I approve", "x")
    with pytest.raises(SignatureError):
        svc.sign("D1", "alice", "   ", "x")


def test_esign_no_sign_after_seal():
    svc = SignatureService()
    svc.request_signature("D1", ["alice"])
    svc.sign("D1", "alice", "I approve", "x")
    svc.seal("D1", "x")
    with pytest.raises(SignatureError):
        svc.sign("D1", "alice", "again", "x")
