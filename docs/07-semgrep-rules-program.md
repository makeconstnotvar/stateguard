# 07. Программа разработки Semgrep-правил

## 7.1. Semgrep как policy engine

Semgrep CE ценен не готовым публичным ruleset, а возможностью выразить архитектурные правила
конкретной компании понятным кодоподобным шаблоном. Его следует развивать как внутренний продукт.

## 7.2. Категории правил StateGuard

### Input boundary

- endpoint без decoder;
- использование raw request после successful parse;
- неизвестные поля проходят в domain command;
- default подставляет бизнес-значение без утверждённой политики;
- строка/число не канонизированы до сравнения/записи.

### Authorization and visibility

- sensitive repository call без authorization wrapper;
- query строится без tenant/owner scope;
- UI visibility трактуется как authorization;
- IDOR-подобный путь от request identifier до read/write.

### State transitions

- прямой write поля state/status вне transition API;
- generic patch критичной сущности;
- transition не проверяет old state;
- transition не использует version/lock;
- terminal state снова становится mutable.

### Transactions

- связанные writes вне общей transaction;
- transaction object потерян между слоями;
- repository использует global connection вместо tx handle;
- catch продолжает выполнение после rollback-worthy error;
- external effect внутри retryable transaction.

### Effects

- publish/send до commit;
- message без operation/idempotency key;
- retry non-idempotent call;
- timeout трактуется как success/failure вместо unknown outcome.

### UI consistency

- async response применяется без sequence/version guard;
- server-confirmed state смешан с form draft;
- optimistic transition без rollback/reconciliation;
- набор независимых booleans кодирует взаимоисключающие состояния.

### Migrations

- `NOT NULL` добавлен без безопасной staged migration;
- column rename/drop несовместим с rolling deployment;
- индекс создаётся блокирующим способом на большой таблице;
- constraint отсутствует или остаётся `NOT VALID` без validate step;
- backfill не имеет batching/restart semantics.

## 7.3. Жизненный цикл правила

```text
hypothesis
→ examples from real incidents/code review
→ fixture suite
→ experimental/info mode
→ telemetry on findings (внутренняя)
→ tune suppressions/framework semantics
→ warning
→ blocking for new code
→ periodic effectiveness review
```

Правило сразу в blocking без pilot создаёт массовое недоверие к инструменту.

## 7.4. Fixture contract

Для каждого правила:

```text
rules/<language>/<rule>.yml
tests/<language>/<rule>/positive.*
tests/<language>/<rule>/negative.*
tests/<language>/<rule>/edge-cases.*
tests/<language>/<rule>/README.md
```

Fixtures должны покрывать:

- очевидный дефект;
- безопасную альтернативу;
- алиасы/imports;
- async/callback syntax;
- wrapper methods;
- framework-specific variants;
- intentional waiver.

## 7.5. Framework semantics

Общие имена `validate`, `query`, `transaction` недостаточны. Для каждого framework создаётся
semantic pack:

```yaml
sources:
  - express.req.body
sanitizers:
  - zod.Schema.parse
  - decodeOrderCommand
transaction_boundaries:
  - pg.PoolClient
  - knex.transaction
external_effects:
  - fetch
  - axios
  - KafkaProducer.send
```

Пакет versioned и выбирается в `stateguard.yaml`.

## 7.6. Rule confidence

- `high`: AST pattern почти однозначно представляет дефект;
- `medium`: требует контекста, но даёт хороший сигнал;
- `low`: hotspot/evidence gap для graph/AI review.

Low-confidence rules не должны блокировать PR напрямую. Они создают review unit или proof
obligation.

## 7.7. Suppression

Допустимые suppressions:

```text
inline waiver ID
central waiver with owner, reason and expiry
path policy for generated/vendor code
rule refinement
```

Недопустим безымянный `nosemgrep` без причины. Пример:

```js
// nosemgrep: stateguard.javascript.external-effect-inside-transaction-callback
// stateguard-waiver: WVR-2026-0042 — provider call is idempotent; expires 2026-12-31
```

CI проверяет существование waiver и срок.

## 7.8. Packaging и offline use

Rules repository собирается в immutable artifact:

```text
stateguard-semgrep-rules-2026.07.3.tar.zst
SHA256SUMS
manifest.json
```

CI image содержит:

- pinned Semgrep version/digest;
- pinned rules artifact/hash;
- no platform token;
- no network;
- writable output only.

В proof attempt сохраняются scanner version, image digest и ruleset hash.

## 7.9. Performance

Rules делятся на profiles:

```text
fast     — high signal, каждый PR
standard — main branch
full     — nightly/release
forensic — ручное расследование
```

Ограничивайте expensive taint rules по paths/languages. Измеряйте p95 rule time. Один чрезмерно
широкий regex способен сделать бесплатный анализатор очень дорогим по CPU.

## 7.10. Импорт в StateGuard

Semgrep выдаёт SARIF. Importer:

- нормализует URI;
- вычисляет stable fingerprint;
- прикрепляет current artifact SHA;
- применяет severity policy;
- связывает metadata `invariantId`, `transitionId`, `surface`;
- помечает исчезнувшие findings как `not-observed`, но не закрывает автоматически без policy;
- инвалидирует finding при изменении evidence file.

## 7.11. Первые 20 правил

Рекомендуемый backlog:

1. SQL interpolation.
2. Raw request → DB sink.
3. Raw request used after parse.
4. Empty/swallowed catch.
5. Generic update critical entity.
6. Status write outside transition layer.
7. Update state without old-state predicate.
8. Check-then-write without concurrency mechanism.
9. Multiple writes without transaction wrapper.
10. Global DB handle inside transaction callback.
11. External HTTP/message effect inside transaction.
12. Retry around non-idempotent effect.
13. Timeout mapped to success.
14. Query without tenant predicate.
15. Authorization only in UI.
16. Async UI response without sequence guard.
17. Optimistic state without rollback.
18. Blocking PostgreSQL migration pattern.
19. `NOT NULL`/drop without staged deployment markers.
20. TODO in critical invariant mapping.

Каждое правило должно быть связано с реальным failure mode. Правило без объяснимого counterexample
обычно является стилевым предпочтением, а не частью StateGuard.
