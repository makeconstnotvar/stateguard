# 04. Декларативная спецификация и Event-B

## 4.1. Два уровня спецификации

StateGuard использует два согласованных представления:

1. YAML specification — удобный API для analyzers, CI, mappings и агентов.
2. Event-B — строгая модель critical bounded context с proof obligations и refinement.

YAML не заменяет Event-B. Event-B не обязан содержать HTTP paths и SQL filenames.

## 4.2. Модель M0: домен

Первая машина содержит только:

- абстрактные множества;
- сущности и отношения;
- состояния;
- инварианты;
- атомарные события.

Примерная структура:

```text
CONTEXT OrderCtx
SETS ORDER USER PAYMENT
CONSTANTS draft submitted paid cancelled
AXIOMS partition(ORDER_STATUS, {draft}, {submitted}, {paid}, {cancelled})

MACHINE OrderM0
VARIABLES status owner payment paymentStatus paymentOrder
INVARIANTS
  status ∈ ORDER ⇸ ORDER_STATUS
  owner ∈ dom(status) → USER
  payment ∈ ORDER ⇸ PAYMENT
  ...
  ∀o·o∈dom(status) ∧ status(o)=paid ⇒
      o∈dom(payment) ∧ paymentStatus(payment(o))=confirmed ∧ paymentOrder(payment(o))=o
EVENTS
  CreateOrder
  SubmitOrder
  ConfirmPayment
  MarkOrderPaid
  CancelOrder
END
```

## 4.3. M1: тотальный command protocol

Абстрактное Event-B event выключено, если guard false. Внешний API обязан ответить на каждый
well-formed command. Поэтому M1 вводит outcomes:

```text
SubmitAccepted
SubmitRejectedNotFound
SubmitRejectedForbidden
SubmitRejectedWrongState
SubmitRejectedStaleVersion
```

Rejection events refine `skip`: доменное состояние не меняется, меняется только модель результата.

Проверяются два свойства:

```text
coverage: accepted ∨ rejected_1 ∨ ... ∨ rejected_n
exclusivity: ¬(outcome_i ∧ outcome_j), i ≠ j
```

Coverage/exclusivity можно дополнительно генерировать в Z3.

## 4.4. M2: persistence refinement

Добавляются:

- table-like relations;
- nullable representation;
- version columns;
- outbox;
- gluing invariants между абстрактными функциями и строками.

Пример gluing invariant:

```text
abstract status(o) = concrete orders[o].status
abstract payment(o) defined ⇔ concrete orders[o].payment_id ≠ NULL
```

NULL моделируется явно, например partial function, а не магическим значением.

## 4.5. M3: concurrency refinement

Event-B event атомарен. Реализация должна показать linearization point:

- conditional `UPDATE ... WHERE old_state AND version`;
- unique/exclusion constraint;
- row lock;
- serializable transaction;
- atomic commutative operation.

M3 вводит competing commands и доказывает, что committed outcomes соответствуют допустимой
последовательности.

## 4.6. M4: effects and UI protocol

Для внешних эффектов вводятся состояния:

```text
not_requested
queued
sent
confirmed
rejected
outcome_unknown
reconciling
```

Для UI:

```text
lastConfirmedVersion
requestSequence
pendingCommand
```

Safety UI:

```text
appliedResponse.version >= lastConfirmedVersion
```

## 4.7. Proof obligations

Минимум закрываются:

- well-definedness;
- invariant preservation;
- guard strengthening при refinement;
- simulation/refinement;
- variant decrease для convergent events;
- witness feasibility;
- theorem proofs.

Proof status экспортируется в StateGuard с model hash и version Rodin/ProB.

## 4.8. ProB

ProB используется до и после ручного proof:

- animation с domain experts;
- deadlock search;
- invariant violation search;
- bounded state-space exploration;
- test trace generation;
- enabling/coverage analysis.

Model checking result обязан указывать bounds. Фраза «ProB не нашёл ошибку» без размера domain и
coverage не считается доказательством.

## 4.9. Sync YAML ↔ Event-B

На первом этапе sync ручной и проверяется mapping IDs. Позже генератор может:

- создавать YAML skeleton из Event-B labels;
- проверять наличие всех `INV-*`, `CMD-*`, `OUT-*`;
- экспортировать proof status;
- генерировать model traces.

Автоматически генерировать Event-B predicates из natural language нельзя использовать как
доверенное преобразование без review.
