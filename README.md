# Document Automation

An end-to-end document management platform covering the Gartner Magic
Quadrant for Document Management capability catalog: repository,
metadata, search, information governance, security, intelligent document
processing, workflow automation, and e-signature.

## The problem

70–90% of enterprise data is unstructured and unmanaged — scattered
across shares, inboxes, and local drives with no versioning, no
governance, and no audit trail. This repo implements the full document
lifecycle deterministically: ingest → classify → extract → approve →
sign → retain → dispose, with security and audit at every step.

## Capability map

See [docs/capability-map.md](docs/capability-map.md) for how each
Gartner mandatory/common feature maps to a module.

| Capability | Module |
|---|---|
| Repository (check-in/out, versioning) | `docauto/repository.py` |
| Metadata management | `docauto/metadata.py` |
| Search with security trimming | `docauto/search.py` |
| Information governance & retention | `docauto/governance.py` |
| Security & audit | `docauto/security.py` |
| Intelligent document processing | `docauto/idp.py` |
| Workflow automation | `docauto/workflow.py` |
| E-signature | `docauto/esign.py` |

## Example lifecycle

```python
from docauto.repository import DocumentStore
from docauto.idp import classify, extract_fields
from docauto.workflow import WorkflowEngine
from docauto.esign import SignatureService
from docauto.governance import RetentionEngine, RetentionPolicy
from docauto.security import AccessControl

store = DocumentStore()
v1 = store.ingest("INV-2041", open("invoice.txt").read(),
                  metadata={}, user="ap-clerk")

# Classify + extract
cls = classify(v1.content)                    # -> invoice (0.85)
fields = extract_fields(v1.content, cls.doc_type)

# Approve
wf = WorkflowEngine()
wf.submit("INV-2041")
wf.review("INV-2041", "approve", reviewer="cfo", rationale="within budget")

# Sign
sig = SignatureService()
sig.request_signature("INV-2041", ["cfo", "controller"])
sig.sign("INV-2041", "cfo", "I approve this invoice for payment", v1.content)
sig.sign("INV-2041", "controller", "Verified against PO-9918", v1.content)
sig.seal("INV-2041", v1.content)
assert sig.verify_seal("INV-2041", v1.content)

# Retain 7 years, then dispose
gov = RetentionEngine()
gov.add_policy(RetentionPolicy("invoice", retention_days=7 * 365,
                               disposition="archive"))
gov.register("INV-2041", "invoice")
```

## Production path

- **Store:** replace in-memory structures with S3/Blob + a database; the
  module contracts (ingest/update/version) are unchanged.
- **Identity:** wire `AccessControl.check` to SSO/OIDC groups.
- **IDP:** swap keyword rules for a trained classifier; the
  `Classification`/`Field` shapes stay the same.
- **E-signature:** replace the mock with DocuSign/Adobe Sign; keep the
  seal-then-verify pattern for tamper evidence.

## Tests

```bash
pytest -q
```

34 tests, deterministic, no network access or API keys required.

## Disclaimer

Independent demo project with synthetic data. The e-signature module is
a functional mock, not a legally binding signature provider.
