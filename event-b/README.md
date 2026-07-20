# Event-B / ProB pilot

Этот каталог показывает, как включить formal model в StateGuard. Файл `OrderWorkflow.mch` —
небольшая ProB-compatible Classical B машина для быстрого CLI smoke/model-check. Production Event-B
модель создаётся в Rodin как contexts/machines/refinements; вручную генерировать Rodin XML не следует.

## Рекомендуемая структура production model

```text
models/order-workflow/
├── rodin-project/
│   ├── OrderCtx.buc
│   ├── OrderM0.bum
│   ├── OrderM1Protocol.bum
│   ├── OrderM2Persistence.bum
│   └── OrderM3Concurrency.bum
├── ids.yaml
├── assumptions.md
├── prob.properties
├── traces/
└── proof-export.json
```

## Быстрый ProB CLI smoke

После локальной установки `probcli`:

```bash
./run-prob.sh
```

Скрипт запускает invariant/deadlock model checking с ограничением количества операций. Точные
options зависят от утверждённой версии ProB; зафиксируйте command и version в proof attempt.

## Связь со specification

`proof-obligations.yaml` связывает model labels с StateGuard IDs. Экспорт Rodin/ProB должен содержать:

```text
model hash
machine/context names
proof obligation label
status
solver/version
bounds/preferences
counterexample/trace
```

Model checker success без bounds/preferences не принимается как `checked-model`.
