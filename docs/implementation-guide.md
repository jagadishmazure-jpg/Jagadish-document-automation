# Implementation guide: from offline build to Azure

> Status: **planned**. Nothing here has been deployed. The offline build in this
> repository is what exists today; this guide is how it would be taken to a
> real Azure environment.

## Azure service mapping

| Offline component | Azure service (planned) | Notes |
|---|---|---|
| `DocumentStore` and versions | Azure Blob Storage with versioning and soft delete | Private endpoint |
| Metadata | Azure Cosmos DB or Azure SQL |  |
| Search | Azure AI Search with security trimming on Entra group IDs |  |
| Classification and extraction | Azure AI Document Intelligence | Keep confidence and snippets |
| Retention and records | Microsoft Purview retention labels and immutable blob policies |  |
| Workflow | Azure Logic Apps approvals |  |
| Access control | Entra ID groups mapped to roles | Audit to Log Analytics |

## Steps

1. Back `DocumentStore` with Blob Storage versioning; keep the same ingest, update and version contract.
2. Index content and metadata in AI Search with a group-ID field for security trimming.
3. Replace keyword classification with Document Intelligence behind the same `classify` and `extract_fields` shapes.
4. Map retention policies to Purview retention labels; use immutable storage for declared records.
5. Run approvals through Logic Apps and send audit events to Log Analytics.

## Guardrails to keep when going live

- Default deny: an action with no ACL entry requires the admin role.
- Search checks read permission before a document can appear in results.
- Declared records cannot be edited or disposed of; disposition logs the skip with the policy.
- A seal binds signer intent to a content hash, so any later change fails verification.
- System metadata (creator, created time, size, checksum) cannot be overwritten.
- Every access decision goes to a hash-chained audit log.

## What to measure before calling it production-ready

- Classification accuracy on a labelled sample of real document types.
- Search results never include documents the user cannot read (red-team check).
- Disposition runs that skip every declared record.
