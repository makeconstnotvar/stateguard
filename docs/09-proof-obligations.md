# 09. Каталог proof obligations

## 9.1. Назначение

Proof obligation — атомарное проверяемое утверждение, связанное с конкретными входными хэшами и
допустимым классом evidence. Большое утверждение «сервис корректен» разлагается на десятки
обязательств.

```text
PO ID
property
scope
inputs
assumptions
solver/checker
required evidence
status
counterexample
```

## 9.2. Статусы

```text
pending
running
proved
verified
reviewed-ai
failed
inconclusive
waived
stale
```

`proved` и `verified` не взаимозаменяемы. В production-схеме лучше хранить отдельные поля
`result` и `evidence_class`; MVP упрощает их до status + attempts.

## 9.3. Input totality

```text
PO-INPUT-<ENDPOINT>-TOTAL
```

Для каждого raw input endpoint завершает обработку одним из утверждённых outcomes:

```text
ValidCommand
InvalidSyntax
InvalidStructure
InvalidValue
UnsupportedVersion
Unauthorized/Forbidden
ResourceLimitExceeded
```

Evidence:

- schema/decoder exhaustiveness;
- property-based fuzz test;
- graph query, исключающий raw-input bypass;
- runtime error mapping test.

## 9.4. Outcome coverage и exclusivity

Для command:

```text
Accepted ∨ Rejected_1 ∨ ... ∨ Rejected_n
```

и:

```text
∀i≠j: ¬(Outcome_i ∧ Outcome_j)
```

Простые guards переводятся в SMT. Counterexample — конкретное состояние/команда, для которых нет
outcome или одновременно истинны два outcome.

## 9.5. Authorization dominance

```text
PO-AUTH-<COMMAND>-DOMINANCE
```

Каждый путь до sensitive observation/write проходит через эффективную авторизацию. Отдельно
проверяется actor binding: проверка должна относиться к тому же actor/resource, который используется
в операции.

Evidence:

- APG control/data-flow;
- negative integration test;
- DB RLS/constraint при наличии.

## 9.6. Invariant preservation

```text
PO-INV-<INV>-BY-<COMMAND>
```


a) Event-B/Rodin доказывает абстрактный переход.

b) Implementation conformance проверяет, что реальные writes и outcomes refine событие.

```text
Invariant(s) ∧ Guard(s,c)
⇒ Invariant(step(s,c))
```

Необходимо оба обязательства. Доказанная модель плюс ошибочный SQL не дают корректную систему.

## 9.7. Atomicity

```text
PO-TX-<COMMAND>-ATOMIC
```

Все writes, требуемые postcondition, имеют общий linearization point. Rejection не оставляет
частичного состояния.

Допустимые механизмы:

- один conditional statement;
- одна transaction;
- constraint-enforced write;
- explicit saga с моделированными compensations/unknown states.

## 9.8. Lost update protection

```text
PO-CONC-<ENTITY>-NO-LOST-UPDATE
```

Для конфликтующих updates имеется:

- version predicate;
- row/advisory lock;
- serializable transaction + full retry;
- atomic commutative SQL;
- uniqueness/exclusion conflict.

Evidence включает parallel test на настоящем DB engine.

## 9.9. Retry safety

```text
PO-RETRY-<COMMAND>-SAFE
```

Повтор всей операции после transient failure не нарушает инварианты и delivery semantics.
Проверяются:

- identity операции;
- idempotency/dedup;
- отсутствие эффекта до durable intent;
- bounded retry/backoff;
- terminal unknown/reconciliation.

## 9.10. Effect ordering

```text
PO-EFFECT-<EFFECT>-AFTER-COMMIT
```

Необратимый эффект возникает только из durable state/outbox. При `at-least-once` consumer имеет
идемпотентную обработку.

Counterexample:

```text
DB write → external send → DB rollback
```

или:

```text
commit → process crash before send, no outbox
```

## 9.11. Observation visibility

```text
PO-OBS-<QUERY>-VISIBILITY
```

```text
returnedRows ⊆ visibleRows(state, actor)
```

Проверяется:

- SQL/ORM predicate;
- tenant binding;
- join semantics;
- pagination/count consistency;
- projection fields;
- negative fixtures.

## 9.12. Observation soundness/completeness

В некоторых отчётах важно не только отсутствие лишних данных:

```text
soundness: returned ⊆ expected
completeness: expected ⊆ returned
```

Потерянная строка в финансовом отчёте столь же серьёзна, как лишняя. Эти свойства выполняются на
сгенерированных small models и real PostgreSQL.

## 9.13. Migration preservation

```text
PO-MIG-<VERSION>-PRESERVES-<INV>
```

После migration:

- все существующие данные удовлетворяют новой модели;
- old/new application versions безопасны в declared compatibility window;
- backfill resumable и идемпотентен;
- schema change не оставляет незащищённое окно;
- rollback/forward-fix policy определена.

## 9.14. UI monotonicity

```text
PO-UI-<STORE>-NO-STALE-OVERWRITE
```

Подтверждённая версия не уменьшается. Response старой операции не применяет более старое состояние.

## 9.15. Resource bounds

```text
PO-RESOURCE-<ENDPOINT>-BOUNDED
```

Проверяются:

- body size;
- list/page limits;
- recursion/depth;
- query timeout;
- transaction timeout;
- worker concurrency;
- queue bounds;
- cancellation propagation.

Это часть корректности: неограниченный запрос способен перевести систему в недоступное состояние
без логического нарушения данных.

## 9.16. Proof policy

Пример:

```yaml
proof_policy:
  critical:
    allowed:
      - proved-model+verified-db
      - enforced-db+verified-concurrency-test
      - proved-static+verified-test+reviewed-human
    forbidden_as_only_evidence:
      - reviewed-ai
      - unit-test
      - sonar-clean
  high:
    minimum_independent_evidence: 2
```

Независимость важна: два правила, использующие один неверный parser, не являются двумя независимыми
доказательствами.

## 9.17. Инвалидация

Obligation становится stale, если изменился:

- любой source/spec/mapping input hash;
- framework adapter;
- ruleset;
- solver/analyzer version при policy requiring revalidation;
- DB schema/catalog;
- assumption;
- waiver.

Ledger хранит proof attempt history, но старый success больше не участвует в текущем verdict.

## 9.18. Генерация

Proof generator читает specification + APG и создаёт обязательства по templates. Например, для
critical command автоматически появляются:

```text
input totality
authorization dominance
guard implementation
invariant preservation
atomicity
lost-update protection
outcome coverage/exclusivity
effect ordering
response projection
test trace coverage
```

Отсутствие mapping создаёт `mapping-gap`, а не молчаливое пропускание обязательства.
