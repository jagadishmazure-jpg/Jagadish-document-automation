# Gartner capability map

How this repo's modules map to the Gartner Magic Quadrant for Document
Management (April 2026) mandatory and common features.

## Mandatory features

| Gartner feature | Implemented by |
|---|---|
| **Document repository** — store, organize, retrieve documents | `repository.py` — `DocumentStore` with stable IDs, content addressing |
| **Check-in / check-out** — prevent conflicting edits | `repository.py` — `checkout()` locks; second user blocked; `checkin()` releases |
| **Version control** — track document history | `repository.py` — every `update()` appends an immutable `DocumentVersion`; `get_version(n)` |
| **Metadata management** — system + custom metadata | `metadata.py` — `MetadataIndex`; system fields (created_by, created_at, size, checksum) are read-only and enforced |
| **Search** — full-text and metadata search | `search.py` — `SearchEngine` over content + metadata, with snippets |
| **Information governance** — retention, legal hold, disposition | `governance.py` — `RetentionEngine`: per-type retention policies, `declare_record()` legal holds, `run_disposition()` with policy-cited log |
| **Security** — access control, audit | `security.py` — `AccessControl` (RBAC × per-document ACLs) + hash-chained `AuditLog` |
| **Intelligent document processing** — classify, extract | `idp.py` — `classify()` (invoice/contract/receipt/policy/memo) + `extract_fields()` with confidence + source snippets |

## Common features

| Gartner feature | Implemented by |
|---|---|
| **Workflow automation** — route documents for review/approval | `workflow.py` — `WorkflowEngine`: draft → in_review → approved/rejected/changes_requested state machine, reviewer queue, SLA tracking |
| **E-signature** — capture legally-recognized intent | `esign.py` — `SignatureService`: intent capture with content hash, multi-signer envelopes, `seal()` + `verify_seal()` tamper check (functional mock) |
| **Records management** — declare, protect, dispose of records | `governance.py` — `declare_record()` blocks edit/dispose; disposition skips declared records and logs the skip |
| **Audit trail** — who did what, when | `security.py` — every access decision recorded in the hash-chained audit log; `verify_chain()` detects tampering |

## Deliberately out of scope

- Real e-signature legality (mock only; production uses DocuSign/Adobe Sign).
- OCR / image processing (IDP here works on text; production adds an OCR stage).
- Federated search across external repositories (single-store scope).
