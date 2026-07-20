# 21. Контракты и точки расширения

## 21.1. Analyzer adapter

Каждый adapter реализует логический интерфейс:

```text
prepare(context) -> tool invocation
run(context) -> raw artifact
normalize(raw, manifest, policy) -> findings/nodes/edges/proof attempts
health() -> version/capabilities
```

Ошибки:

```text
unsupported
configuration-error
tool-failure
timeout
partial-result
invalid-report
```

Partial result не считается clean.

## 21.2. Finding contract

JSON Schema: `schemas/finding.schema.json`. Обязательное содержание для confirmed high/critical:

- stable key;
- violated property;
- location/current hash;
- reachable counterexample;
- impact;
- root cause;
- systemic remediation;
- verification criterion.

## 21.3. Specification contract

JSON Schema: `schemas/specification.schema.json`. Дополнительная semantic validation должна
проверять references и policy. JSON Schema не умеет доказать сохранение инварианта.

## 21.4. Mapping contract

`mappings.yaml` связывает model IDs с selectors. Adapter возвращает cardinality:

```text
exactly-one
one-or-more
zero-allowed
```

Если expected symbol не найден или найдено слишком много, создаётся mapping gap.

## 21.5. APG import contract

Рекомендуемый JSONL:

```json
{"kind":"node","externalId":"...","type":"Endpoint","properties":{}}
{"kind":"edge","externalId":"...","source":"...","target":"...","type":"CALLS","properties":{}}
```

Требования:

- deterministic external IDs;
- repository-relative paths;
- source tool/version/hash;
- no dangling edges;
- bounded property size;
- schema version.

## 21.6. Proof runner

```text
supports(obligation) -> bool
execute(obligation, inputs, timeout) -> ProofAttempt
```

`ProofAttempt`:

```text
status
solver/tool version
command
input hashes
started/finished
summary
counterexample
evidence artifacts
bounds/assumptions
```

## 21.7. Test evidence adapter

Парсит JUnit/JSON/custom outputs и связывает tests с obligations по metadata/manifest. Test name
matching regex недостаточен для critical evidence; используйте stable test IDs.

## 21.8. Sonar exporter

Экспортирует только current findings. Properties содержат StateGuard IDs и ссылки на invariant/
transition. Severity map versioned.

## 21.9. Central publish API

Рекомендуемые endpoints:

```text
POST /v1/runs                         idempotent create/upsert
PUT  /v1/runs/{id}/findings
PUT  /v1/runs/{id}/proofs
POST /v1/runs/{id}/complete
GET  /v1/repositories/{key}/status
POST /v1/waivers
POST /v1/remediation-batches/claim
POST /v1/remediation-batches/{id}/complete
```

Auth: workload identity/mTLS/token по внутреннему стандарту. Run immutable после complete; новая
публикация создаёт superseding run.

## 21.10. Policy distribution

Central policy artifact:

```text
policy.yaml
severity-map.yaml
proof-policy.yaml
ruleset manifest
framework adapter manifest
checksums/signature
```

Repository может только ужесточать policy без отдельного approval; ослабление требует waiver.

## 21.11. CLI extension

Будущие команды:

```text
stateguard validate
stateguard analyze
stateguard proof generate
stateguard proof run
stateguard apg import
stateguard test import
stateguard publish
stateguard batch claim/fix/verify
stateguard release-bundle
```

MVP намеренно содержит минимальный lifecycle. Не добавляйте интерфейс до стабилизации контракта.

## 21.12. Versioning

Все форматы имеют schema version. Compatibility:

- reader поддерживает current и предыдущую major/minor policy window;
- migrations ledger выполняются транзакционно;
- unknown required field → fail;
- unknown optional extension → preserve/ignore по contract;
- tool adapter output хранит exact schema version.
