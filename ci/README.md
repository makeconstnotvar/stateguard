# CI integration

Шаблоны предполагают внутренние/self-hosted runners. Они намеренно не скачивают правила во время
анализа и не передают CPG или audit ledger сторонним SaaS.

## Три частоты анализа

### Pull request

- native compiler/linter;
- unit tests;
- Semgrep CE с локальным ruleset;
- инкрементальный `stateguard scan`;
- targeted integration tests;
- blocking только по новым high-confidence findings и критичным obligations.

### Main branch

- полный набор PR-проверок;
- SonarScanner и публикация во внутренний SonarQube;
- полный integration suite;
- обновление центрального StateGuard control plane.

### Nightly/release

- Joern CPG и APG obligations;
- Event-B/ProB;
- Z3;
- миграции от всех поддерживаемых предыдущих версий;
- конкурентные тесты;
- локальный AI-review unresolved obligations;
- `doctor --strict`.

Перед использованием замените версии CI actions/plugins на одобренные компанией и закрепите их
immutable digest/commit, а не плавающим тегом.
