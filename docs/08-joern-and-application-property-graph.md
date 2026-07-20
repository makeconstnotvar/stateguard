# 08. Joern и Application Property Graph

## 8.1. Почему CPG недостаточно

Joern Code Property Graph описывает программные конструкции. StateGuard нужен граф продукта:
endpoint, command, invariant, SQL write, UI action, constraint и test. Поэтому строится APG —
Application Property Graph.

```text
Joern CPG + SQL AST + DB catalog + API schemas + StateGuard mappings + test metadata
                                  ↓
                  normalized Application Property Graph
```

## 8.2. Стабильная модель узлов

Минимальные типы:

```text
Repository Component File Symbol Function Method Call
Endpoint Input Decoder Validator AuthorizationCheck
Command Outcome Guard Transaction Query
Table Column Constraint Index Trigger
DomainEntity State Transition Invariant Observation
ExternalEffect OutboxOperation UIAction UIState
Test Migration ProofObligation Finding
```

Каждый узел имеет:

```json
{
  "externalId": "js:function:server/orders.js:submitOrder:<semantic-hash>",
  "type": "CommandHandler",
  "name": "submitOrder",
  "artifactPath": "server/orders.js",
  "range": {"startLine": 17, "endLine": 61},
  "sourceTool": "joern-js",
  "sourceHash": "...",
  "properties": {}
}
```

## 8.3. Типы рёбер

```text
CONTAINS
DECLARES
CALLS
FLOWS_TO
CONTROL_DOMINATES
RETURNS
VALIDATED_BY
AUTHORIZED_BY
IMPLEMENTS
REFINES
READS
WRITES
GUARDED_BY
STARTS_TRANSACTION
PART_OF_TRANSACTION
COMMITS_BEFORE
EMITS_EFFECT
OBSERVED_BY
ENFORCES
TESTED_BY
PROVES
INVALIDATES
DEPENDS_ON
```

Рёбра имеют provenance. Нельзя объединять факт из AST и предположение агента без маркировки:

```json
{
  "sourceTool": "stateguard-mapping",
  "confidence": "asserted",
  "evidenceClass": "declared"
}
```

## 8.4. Pipeline Joern

1. Определить языки/модули.
2. Построить CPG отдельным frontend для каждого поддерживаемого модуля.
3. Запустить data-flow overlays.
4. Экспортировать стабильные факты или выполнить StateGuard queries внутри Joern.
5. Нормализовать paths и symbol IDs.
6. Добавить framework semantics.
7. Слить с SQL/catalog/API графами.
8. Вычислить proof obligations.
9. Сохранить только необходимые APG nodes/edges и slices в ledger.
10. Удалить raw CPG согласно retention.

## 8.5. Framework adapters

Adapter содержит декларации:

```yaml
framework: express
version_range: ">=4 <6"
endpoint_patterns:
  - callee: "express.Router.(get|post|put|patch|delete)"
request_sources:
  - "express.Request.body"
decoders:
  - "zod.*.parse"
transaction_boundaries:
  - "withTransaction"
authorization_calls:
  - "requirePermission"
```

Для Spring, ASP.NET, Django, Rails, NestJS и других framework создаются отдельные adapters.
Автоматическое распознавание дополняется `mappings.yaml`, потому что приложения оборачивают API.

## 8.6. Пример graph query: authorization dominance

Цель:

```text
все пути Endpoint → SensitiveWrite проходят через AuthorizationCheck
```

Алгоритм:

1. найти endpoint node;
2. найти reachable sensitive writes;
3. построить interprocedural control-flow slice;
4. проверить, существует ли путь без auth node;
5. если существует — вернуть минимальный counterexample path;
6. если все пути закрыты, проверить, что auth result реально влияет на branch/termination;
7. сохранить graph/ruleset/source hashes.

Вызов `authorize()` сам по себе не доказательство: результат может игнорироваться.

## 8.7. Пример: transaction containment

Для command mapping задан набор required writes. Query проверяет:

```text
all required writes share the same transaction context
AND commit is reached only after all writes
AND failure path rolls back or produces no visible partial state
```

Wrapper semantics должны знать, как framework передаёт transaction handle. Если код использует
ambient transaction/runtime interception, adapter обязан явно это описать.

## 8.8. Пример: stale UI response

Graph соединяет:

```text
UIAction → async API call → response continuation → observable/domain state write
```

Проверяется наличие control/data dependency от:

- request sequence;
- cancellation token;
- entity/server version;
- takeLatest semantics;

к применению response. Отсутствие создаёт hotspot, а воспроизводимый параллельный сценарий переводит
его в finding.

## 8.9. Graph slices для ИИ

Агенту передаётся не полный CPG, а пакет:

```json
{
  "obligation": "PO-CMD-ORDER-PAY-TX",
  "specification": {...},
  "paths": [...],
  "symbols": [...],
  "sql": [...],
  "constraints": [...],
  "tests": [...],
  "openQuestions": [...]
}
```

Лимиты:

- только связанные файлы;
- минимальные excerpts;
- deterministic ordering;
- SHA-256 каждого excerpt;
- no secrets;
- size budget;
- provenance каждой связи.

## 8.10. Incremental rebuild

Полный CPG на каждом изменении дорог. Первая версия может перестраивать модуль целиком. Позже:

- manifest определяет changed files;
- dependency graph вычисляет affected components;
- CPG кэшируется по repository commit/tool version;
- APG slices инвалидируются по input hashes;
- nightly делает полный reconciliation.

Incremental результат никогда не заменяет периодический full scan: зависимость могла быть извлечена
неполно.

## 8.11. Проверка adapters

Каждый adapter имеет synthetic application:

- безопасный endpoint;
- endpoint без validation;
- auth bypass;
- transaction leak;
- outbox pattern;
- UI stale response;
- ORM wrapper;
- dynamic route.

Golden APG snapshot сравнивается в CI. Обновление Joern/frontend не выпускается, пока snapshot delta
не рассмотрена.

## 8.12. Ограничения

Joern не должен давать ложное чувство полноты для:

- reflection;
- runtime code generation;
- DI/configuration, меняющей call target;
- dynamic SQL;
- metaprogramming;
- native extensions;
- RPC между репозиториями;
- frontend bundle transformations.

Такие места получают explicit uncertainty node и дополнительный test/manual obligation.
