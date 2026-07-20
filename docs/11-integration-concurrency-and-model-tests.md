# 11. Интеграционные, конкурентные и model-based тесты

## 11.1. Роль тестов

Тест не доказывает общее свойство, но надёжно проверяет конкретную реализацию и реальную семантику
framework/DB. StateGuard использует тесты как один из независимых классов evidence.

## 11.2. Тестовая пирамида StateGuard

```text
property/unit tests        pure transition/decoder/reference model
contract tests             API, schemas, typed outcomes
database tests             constraints, SQL, migrations
integration tests          vertical command slice
concurrency tests          conflicting histories
failure-injection tests    rollback, timeout, retry, crash points
model-generated tests      traces from Event-B/ProB
UI protocol tests          stale responses, optimistic state
end-to-end tests            несколько критичных business journeys
```

Количество e2e ограничивается. Основное доказательное покрытие получают более управляемые слои.

## 11.3. Pure transition tests

Когда возможно, domain transition выделяется:

```text
transition(state, command) -> accepted(nextState, effects) | rejected(reason)
```

Проверяются:

- totality на generated inputs;
- invariant preservation;
- deterministic result;
- rejection leaves state unchanged;
- effect commands являются данными;
- terminal states.

Это не заменяет transaction test, потому что persistence mapping может быть неверным.

## 11.4. Decoder fuzz/property tests

Генерируются:

- случайные JSON-like values;
- missing/extra fields;
- type confusion;
- numeric/string boundaries;
- unicode/canonicalization;
- oversized/deep structures;
- supported/unsupported versions.

Свойство:

```text
произвольный bounded raw input
→ valid closed command OR typed rejection
→ no uncaught expected exception
```

## 11.5. Vertical integration test

Тест вызывает реальный endpoint/handler с disposable DB и проверяет:

- input decode;
- auth;
- SQL transaction;
- constraints;
- returned outcome;
- durable state;
- outbox;
- logs/metrics при необходимости.

Mock DB для такого evidence неприемлем.

## 11.6. Конкурентные тесты

Шаблон:

1. создать исходное состояние;
2. синхронизировать N workers barrier-ом;
3. одновременно выполнить конфликтующие commands;
4. собрать outcomes;
5. прочитать final state;
6. проверить, что история принадлежит разрешённому множеству;
7. повторить десятки/сотни раз по CI profile.

Примеры:

- два submit с одной version;
- два approve разных actor;
- reserve capacity на последнюю единицу;
- duplicate payment callback;
- cancel против fulfill;
- outbox workers claim один event.

Тест должен проверять не «один запрос упал», а допустимый набор результатов и итоговый инвариант.

## 11.7. Isolation matrix

Запускайте критичные сценарии на фактическом isolation level. При необходимости matrix:

```text
READ COMMITTED
REPEATABLE READ
SERIALIZABLE
```

Цель — подтвердить assumptions и retry behavior, а не объявить SERIALIZABLE универсальным решением.

## 11.8. Failure injection

Точки отказа:

```text
before BEGIN
after first read
after each write
before COMMIT
after COMMIT before response
after outbox claim
before/after external send
after external send before acknowledgement
before applying UI response
```

Проверяется состояние после restart/retry. Для кода можно использовать injectable ports/fault hooks;
для процессов — kill/container restart; для сети — proxy/fault tool внутри изолированного test
network.

## 11.9. Migration tests

Минимум две траектории:

```text
empty database → all migrations
previous supported production schema + fixture snapshot → current
```

Проверки:

- migration завершилась;
- catalog соответствует expected;
- invariant queries = 0 violations;
- old/new app compatibility stage;
- backfill resume;
- lock/time budget на representative volume.

## 11.10. Testcontainers

Testcontainers удобен для disposable services. Требования:

- фиксировать image version/digest;
- использовать ту же major PostgreSQL, что production;
- не запускать privileged containers без необходимости;
- прогревать approved images во внутреннем registry;
- собирать container logs при failure;
- устанавливать startup/statement timeouts;
- очищать resources.

Пример в `examples/order-workflow/tests/order.test.js` показывает PostgreSQL container и
параллельный transition test.

## 11.11. Model-generated traces

ProB экспортирует traces:

```text
initial state
command 1 + outcome
command 2 + outcome
...
expected abstract state
```

Adapter materialизует initial state в DB, вызывает production handlers и сравнивает concrete state
через gluing projection.

Особенно ценны:

- shortest counterexample;
- boundary traces;
- all transitions coverage;
- rejection traces;
- loops/retries;
- competing histories.

## 11.12. Test evidence contract

Каждый evidence test публикует JSON:

```json
{
  "testId": "TEST-CMD-ORDER-SUBMIT-CONCURRENT",
  "proofObligations": ["PO-CONC-ORDER-NO-LOST-UPDATE"],
  "tool": "node:test",
  "environment": {"postgres": "17.x"},
  "inputsHash": "...",
  "result": "passed",
  "iterations": 100,
  "artifact": "..."
}
```

Просто зелёный общий test suite без связи с obligation не считается proof coverage.

## 11.13. Flaky tests

Flaky concurrency test нельзя автоматически rerun-ить до зелёного и забыть. Первый failure
сохраняется как counterexample. Quarantine:

- имеет owner;
- deadline;
- не закрывает obligation;
- не разрешает release для critical property без альтернативного evidence.

## 11.14. Performance и correctness

Performance test отделён от safety, но resource exhaustion может быть correctness failure.
Фиксируйте:

- max query duration;
- max transaction duration;
- max rows/bytes;
- queue depth;
- memory/CPU budget;
- cancellation outcome.

## 11.15. CI profiles

```text
PR:
  selected unit/integration tests
  5–20 concurrency iterations для touched critical slice

main:
  full integration
  migration smoke
  50–100 concurrency iterations

nightly/release:
  model traces
  failure injection
  upgrade migration
  hundreds/thousands selected race iterations
```

Количество зависит от стоимости; важнее deterministic barriers и проверяемые histories, чем
бездумный stress.
