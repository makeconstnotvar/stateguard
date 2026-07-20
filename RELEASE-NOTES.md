# StateGuard implementation kit 0.1.0

Дата сборки: 20 июля 2026 года.

Включено:

- 23 тематических документа и production-readiness checklist;
- working local CLI/SQLite ledger;
- hash-based stale invalidation;
- review claims/leases;
- SARIF import/export;
- normalized APG import;
- proof attempt recording;
- fix prompt generation;
- SonarQube Community Build starter deployment;
- Semgrep CE starter rules/offline runner;
- Joern, Event-B/ProB, Z3 and PostgreSQL examples;
- central control-plane PostgreSQL/OpenAPI contract;
- self-hosted CI templates;
- tested order-workflow vertical slice source;
- prebuilt source-only Python wheel (third-party dependencies are not bundled).

Known implementation gaps are intentional and documented: production framework adapters, complete
Joern/APG normalization, Rodin project files, central service implementation and company-specific
rules/models must be developed for the target organization.
