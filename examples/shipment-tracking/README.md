# Shipment tracking example

Второй вертикальный срез — намеренно другой по форме от `examples/order-workflow`, чтобы
доказать (или честно опровергнуть) обобщаемость StateGuard за пределы одного примера.
Показывает:

- идемпотентный приём carrier-webhook checkpoint'ов (at-least-once delivery, replay = no-op);
- guard на *внешне заданный* `sequence_no` (не собственный счётчик системы, как `version` в
  order-workflow) — строго возрастающий порядок, а не CAS;
- pessimistic locking (`SELECT ... FOR UPDATE`) вместо optimistic version-guard — конкурентные
  вызовы блокируются, а не откатываются и не повторяются;
- append-only лог checkpoint'ов вместо мутируемой строки;
- deferred constraint trigger, проверяющий что `last_sequence` соответствует наибольшему
  зафиксированному `sequence_no`;
- Z3-доказательства с формами, которых нет в order-workflow: строгое неравенство по внешнему
  входу, `Implies(already_processed, no-op)`, «establishment»-доказательства для команды
  создания, и проверка валидности FSM-перехода (`INV-SHIP-004`);
- собственный (не общий kit-level) Event-B проект — первый пример, использующий
  `specification.event_b_project` как локальный путь.

## Пройден адверсариальный review — что было исправлено

Реализация прошла через Workflow-процесс адверсариального review (5 независимых
направлений + верификация каждой находки). Найдено и исправлено:

- `createShipment` не обрабатывал конкурентную гонку на `order_id` (уходил необработанным
  Postgres-исключением вместо `duplicate_shipment`) — добавлена обработка `23505`.
- Z3-доказательство `INV-SHIP-001` проверяло нестрогое `>=` вместо заявленного строгого
  `>` — не ловило ослабление guard'а. Добавлен инвариант `INV-SHIP-004` (guard
  `allowed_next` не был нагружен НИ ОДНИМ доказательством) и усилена формула
  `INV-SHIP-001`.
- `mappings.yaml`: em-dash вместо двоеточия в одном test-селекторе (молча ронял evidence),
  DB-trigger тест не был привязан как `kind: test` к `INV-SHIP-001`, `kind: query` на
  `.js`-файл нарушал конвенцию адаптера и коллизировал с другими query-узлами.
- Тесты: порядок `t.after`-хуков мог убить контейнер раньше закрытия пула; тест на
  конкурентность не гарантировал настоящую гонку на уровне SQL (добавлен отдельный тест,
  явно держащий `FOR UPDATE`-лок через второй client); добавлено покрытие
  `wrong_state`/`invalid_transition`/`duplicate_shipment`.
- Event-B: `event_shipment`/`event_sequence` были keyed глобально по `EVENT`, а не по паре
  `(SHIPMENT, EVENT)` — второй shipment мог молча «украсть» событие первого, и это не
  ловилось заявленным INVARIANT. Исправлено: `event_sequence` теперь функция от пары,
  зеркалируя `db/schema.sql`'s `UNIQUE(shipment_id, provider_event_id)`.

Полный текст находок и верификации — в истории сессии; здесь фиксируется факт и суть
исправлений, а не сам процесс review.

## Архитектурный пробел, который этот пример вскрыл — и как он исправлен

`server/webhook-parser.js`'s `parseCarrierWebhook` играет ту же роль, что
`decodeSubmitOrder` в order-workflow (входной decoder/validator для команды), но названа
не с префиксом `decode`. Изначально `src/stateguard/joern_adapter.py`'s эвристика
определения handler'а (Pass 2) жёстко проверяла `.lower().startswith("decode")` вместо
чтения роли из `mappings.yaml` — в отличие от `transaction_starts`, который явно
config-driven. `parseCarrierWebhook` при этом ошибочно классифицировался как handler и
получал некорректное `WRITES`-ребро в сгенерированном APG.

Это намеренно не было исправлено переименованием — цель примера в том, чтобы вскрыть
реальный пробел архитектуры, а не спрятать его. Исправление внесено в
`joern_adapter.py`: новая функция `_decoder_selectors()` (зеркалит
`_transaction_wrapper_selectors()`) читает `framework_adapters[].rules.decoders` из
`mappings.yaml`, полностью заменив хардкод naming convention. `parseCarrierWebhook`
теперь явно объявлена в этом списке (см. `mappings.yaml`'s `pg-pessimistic-lock`
адаптер) — без переименования функции, что и доказывает: фикс закрывает пробел, не
навязывая целевому коду соглашение об именовании.

Заодно в том же проходе исправлены два смежных пробела адаптера: `kind: query`-узлы
получали path-only ID, из-за чего один и тот же `.sql`-файл, упомянутый и в invariant, и
в command, коллизировал — исправлено обработкой секции `commands` раньше `invariants`,
так что короткое имя команды детерминированно выигрывает как display name узла; и
`ENFORCES`-ребро от invariant-локации раньше генерировалось только для `kind:
constraint` — теперь для любого kind кроме `test` (у которого уже есть более точное
`TESTED_BY`). Подробности и полная верификация — в `IMPLEMENTATION-MASTER-PLAN.md`.

## Запуск

```bash
npm install
npm test
```

Пример учебный. `SEQ`-диапазон в Event-B модели (`0..5`) специально мал для трассируемости
model checking — production-модель использовала бы Rodin refinement chain с более широким
диапазоном или абстрактным rank вместо конкретных чисел.
