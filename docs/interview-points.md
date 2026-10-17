# Interview points

Short, honest talking points for Jagadish-document-automation. Every number quoted is from the
real run shown in the README.

- I modelled document management controls as code so they can be tested, not just configured.
- Security trimming happens before results are built: in the demo a viewer's search returns nothing.
- Tamper evidence: the seal check passes on the original and fails when one amount is changed.
- Records management: a declared record is skipped at disposition and the skip is logged.

## Likely follow-up questions

- Why default deny? (Unspecified permissions are the usual leak; require an explicit grant.)
- How would you migrate an existing share? (Bulk ingest with classification, owner assignment and retention labels.)
- What would you change for scale? (Blob plus AI Search, and move audit to Log Analytics.)
