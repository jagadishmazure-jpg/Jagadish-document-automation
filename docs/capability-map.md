# Document management capability map

The capabilities below are my own grouping of what an enterprise document
management platform has to do, and where each one lives in this repo. They are
written from general practice, not copied from any analyst report.

## Core capabilities

| Capability | What it means | Implemented by |
|---|---|---|
| Repository | Store, organise and retrieve documents under stable IDs | `repository.py`: `DocumentStore` with content checksums |
| Check-out / check-in | Stop two people editing the same document at once | `repository.py`: `checkout()` locks; a second user is blocked; `checkin()` releases |
| Versioning | Keep every revision and allow retrieval of any version | `repository.py`: each `update()` appends an immutable `DocumentVersion`; `get_version(n)` |
| Metadata | System fields that cannot be edited plus custom fields | `metadata.py`: `MetadataIndex`; created_by, created_at, size and checksum are read-only |
| Search | Full-text and metadata search that respects permissions | `search.py`: `SearchEngine` with snippets and security trimming |
| Retention and records | Retention periods, record declaration (legal hold), disposition | `governance.py`: `RetentionEngine`, `declare_record()`, `run_disposition()` with a policy-cited log |
| Security and audit | Role and per-document permissions, tamper-evident audit | `security.py`: `AccessControl` (RBAC plus per-document ACLs) and a hash-chained `AuditLog` |
| Document understanding | Classify a document and extract key fields | `idp.py`: `classify()` (invoice, contract, receipt, policy, memo) and `extract_fields()` with confidence and source snippets |

## Process capabilities

| Capability | What it means | Implemented by |
|---|---|---|
| Review and approval workflow | Route documents to reviewers with a clear state | `workflow.py`: draft, in review, approved, rejected or changes requested; reviewer queue; SLA tracking |
| Electronic signature | Capture each signer's intent against a content hash | `esign.py`: multi-signer envelopes, `seal()` and `verify_seal()` (a functional mock, not a legal signature) |
| Records protection | Declared records cannot be edited or disposed of | `governance.py`: disposition skips declared records and logs the skip |

## Out of scope

- Legally binding e-signature (the module is a mock; production would use a commercial signature service).
- OCR and image processing (classification here works on text).
- Federated search across other repositories.
