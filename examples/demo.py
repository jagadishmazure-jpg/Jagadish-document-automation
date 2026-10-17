"""One invoice through the document lifecycle: ingest, classify, version, search, approve, sign, retain (offline)."""
from datetime import datetime, timezone

from docauto.esign import SignatureService
from docauto.governance import RetentionEngine, RetentionPolicy
from docauto.idp import classify, extract_fields
from docauto.repository import DocumentStore, RepositoryError
from docauto.search import SearchEngine
from docauto.security import AccessControl
from docauto.workflow import WorkflowEngine

INVOICE = """INVOICE NO INV-2041
Bill To: Acme Corp
Invoice Date: 2026-03-15
Subtotal: $1250.00
Tax: $100.00
Amount Due: $1350.00
Payment Terms: Net 30
"""

store = DocumentStore()
v1 = store.ingest("INV-2041", INVOICE, metadata={"department": "finance"}, user="ap-clerk")
cls = classify(v1.content)
print(f"Classified as {cls.doc_type} (confidence {cls.confidence:.2f})")
for f in extract_fields(v1.content, cls.doc_type):
    print(f"  {f.name:14} = {f.value!s:12} confidence {f.confidence:.2f}")

store.checkout("INV-2041", "ap-clerk")
try:
    store.checkout("INV-2041", "other-user")
except RepositoryError as e:
    print(f"Second checkout blocked: {e}")
store.update("INV-2041", INVOICE + "PO Ref: PO-9918\n", user="ap-clerk")
store.checkin("INV-2041", "ap-clerk")
print(f"Versions kept: {store.version('INV-2041')}")

access = AccessControl()
access.set_acl("INV-2041", {"read": "editor"})
search = SearchEngine(access)
search.index("INV-2041", store.get_version("INV-2041", 2).content, {"department": "finance"})
print(f"Search 'Net 30' as editor: {[r.doc_id for r in search.search('Net 30', 'ap-clerk', 'editor')]}")
print(f"Search 'Net 30' as viewer: {[r.doc_id for r in search.search('Net 30', 'guest', 'viewer')]}  (security-trimmed)")
print(f"Audit log entries: {len(access.audit.entries())}, chain verifies: {access.audit.verify_chain()}")

wf = WorkflowEngine()
wf.submit("INV-2041")
state = wf.review("INV-2041", "approve", reviewer="controller", rationale="matches PO-9918")
print(f"Workflow state: {state.state}")

content = store.get_version("INV-2041", 2).content
sig = SignatureService()
sig.request_signature("INV-2041", ["cfo", "controller"])
sig.sign("INV-2041", "cfo", "I approve this invoice for payment", content)
sig.sign("INV-2041", "controller", "Verified against PO-9918", content)
sig.seal("INV-2041", content)
print(f"Seal verifies on original: {sig.verify_seal('INV-2041', content)}; "
      f"on tampered copy: {sig.verify_seal('INV-2041', content.replace('1350', '9350'))}")

gov = RetentionEngine()
gov.add_policy(RetentionPolicy("invoice", retention_days=7 * 365, disposition="archive"))
gov.register("INV-2041", "invoice", created_at=datetime(2018, 1, 1, tzinfo=timezone.utc))
gov.register("INV-1007", "invoice", created_at=datetime(2018, 1, 1, tzinfo=timezone.utc))
gov.declare_record("INV-1007")
for r in gov.run_disposition(as_of=datetime(2026, 10, 1, tzinfo=timezone.utc)):
    print(f"Disposition {r.doc_id}: {r.action} (policy {r.policy})")
