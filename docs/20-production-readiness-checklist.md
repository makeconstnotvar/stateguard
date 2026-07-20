# 20. Production readiness checklist

## Governance

- [ ] Назначен executive sponsor и platform owner.
- [ ] Репозитории классифицированы по tier.
- [ ] У critical components есть domain/technical/DB/security owners.
- [ ] Утверждены severity, evidence и waiver policies.
- [ ] Определена формулировка `GREEN BY EVIDENCE`.
- [ ] Процесс не обещает абсолютное отсутствие ошибок.

## Privacy and security

- [ ] Все scanners работают локально/внутри сети.
- [ ] Egress запрещён технически для offline jobs.
- [ ] Образы и packages зеркалируются и pinned digest.
- [ ] Rules/spec artifacts защищены review и hashes.
- [ ] SonarQube не содержит публичных проектов.
- [ ] Tokens project-scoped и хранятся в secret manager.
- [ ] AI runtime не имеет cloud fallback.
- [ ] Prompt/report retention утверждён.
- [ ] Scanner containers не имеют лишних privileges/socket mounts.

## SonarQube

- [ ] Используется внешний PostgreSQL, не встроенная test DB.
- [ ] Выполнены host limits/ulimits.
- [ ] TLS/reverse proxy/access control настроены.
- [ ] Backup создан и restore протестирован.
- [ ] Upgrade rehearsal выполняется на staging DB copy.
- [ ] Project provisioning автоматизирован.
- [ ] Quality profiles/gates versioned.
- [ ] External SARIF path настроен.
- [ ] Lifecycle external issue не считается authoritative.

## Repository contract

- [ ] `.stateguard/stateguard.yaml` валиден.
- [ ] Specification/mappings находятся в VCS.
- [ ] Stable IDs уникальны.
- [ ] Excludes/generated policy рассмотрены.
- [ ] `audit.db`, raw CPG и secrets исключены из VCS.
- [ ] Project-owned build/test scripts существуют.

## Static analysis

- [ ] Native analyzers включены.
- [ ] Semgrep работает с local rules и `--metrics=off` в network-denied container.
- [ ] Rules имеют fixtures/owner/confidence.
- [ ] High/critical rules прошли pilot.
- [ ] Analyzer crash трактуется как failure/unknown, не clean.
- [ ] Joern adapters имеют golden tests.
- [ ] Dynamic/reflection areas отмечены uncertainty.

## Specification and formal model

- [ ] Critical entities/states/invariants/commands описаны.
- [ ] Outcomes total и взаимоисключающие.
- [ ] Assumptions явны.
- [ ] Event-B scope согласован domain owner.
- [ ] Rodin proof status экспортируется с model hash.
- [ ] ProB bounds сохраняются.
- [ ] Model traces связаны с implementation tests.
- [ ] Implementation conformance проверяется отдельно.

## Database

- [ ] Migrations применяются с нуля и с предыдущей поддерживаемой версии.
- [ ] Catalog snapshot сохраняется.
- [ ] Critical invariants enforced constraints/index/RLS/trigger где возможно.
- [ ] Dynamic SQL классифицирован.
- [ ] Lost-update mechanism явен.
- [ ] Serializable retry повторяет всю transaction.
- [ ] External effects не выполняются небезопасно внутри transaction.
- [ ] Outbox/idempotency/reconciliation проверены.
- [ ] Production pre-migration invariant queries определены.

## Testing

- [ ] Decoder property/fuzz tests есть.
- [ ] Critical commands имеют vertical integration tests.
- [ ] Конкурентные histories проверяются на real PostgreSQL.
- [ ] Failure injection покрывает ключевые crash points.
- [ ] UI stale response тестируется.
- [ ] Query visibility/soundness oracles существуют.
- [ ] Flaky tests не закрывают obligations.
- [ ] Test reports связываются с proof IDs.

## Ledger

- [ ] Scan считает current SHA-256.
- [ ] Changed file invalidates units/findings/proofs.
- [ ] Claims имеют lease/fencing strategy.
- [ ] Finding содержит counterexample/remediation/verification.
- [ ] Waivers имеют owner/expiry.
- [ ] `doctor --strict` включён в release.
- [ ] Central publication идемпотентна, если control plane используется.

## AI

- [ ] AI получает bounded graph slices, не весь repository по умолчанию.
- [ ] Output валидируется schema.
- [ ] Source comments считаются untrusted.
- [ ] Review/fix/verify permissions разделены.
- [ ] AI-only evidence не закрывает critical/high policy.
- [ ] Модель проверена на внутреннем benchmark.

## CI/CD

- [ ] PR fast profile укладывается в latency budget.
- [ ] Main analysis публикуется в SonarQube.
- [ ] Nightly/release deep profile существует.
- [ ] Required jobs невозможно молча skip.
- [ ] Tool/ruleset versions и hashes сохраняются.
- [ ] Release evidence bundle immutable.
- [ ] Legacy rollout имеет срок перехода к blocking.

## Operations

- [ ] Определены SLO и capacity metrics.
- [ ] Есть canary process обновления analyzers/rules.
- [ ] Есть incident runbook для false green/compromise.
- [ ] Costs измеряются по layer/repository tier.
- [ ] Raw CPG и sensitive artifacts имеют минимальный retention.
