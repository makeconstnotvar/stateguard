# 10. PostgreSQL, SQL и migrations

## 10.1. PostgreSQL как enforcement layer

Бизнес-инвариант должен физически находиться максимально близко к данным. Приоритет механизмов:

1. тип и `NOT NULL`;
2. `CHECK` для одной строки;
3. `UNIQUE`/partial unique;
4. foreign key;
5. exclusion constraint;
6. row-level security;
7. trigger/function для ограничений, которые нельзя выразить declaratively;
8. transaction protocol приложения;
9. периодическая reconciliation.

Чем ниже инвариант расположен в списке, тем больше доказательств требуется.

Приложение не должно рассчитывать на единственную JavaScript/Java/C# проверку, если другой endpoint,
job, migration или ручной SQL может её обойти.

## 10.2. Catalog snapshot

StateGuard применяет migrations к disposable PostgreSQL и экспортирует catalog:

- schemas/tables/columns/types/defaults/nullability;
- primary/foreign/unique/check constraints;
- indexes и predicates;
- triggers/functions;
- RLS policies;
- enum/domain types;
- generated/identity columns;
- constraint validation/deferrability.

Файл `postgres/catalog_snapshot.sql` выдаёт JSONL snapshot. В production adapter нормализует его в
APG и вычисляет catalog hash.

Catalog нужен после фактического применения migrations. Анализ отдельных migration-файлов не
гарантирует итоговую схему: порядок, conditional DDL и ранее изменённая база могут дать другой
результат.

## 10.3. SQL AST

Для literal PostgreSQL SQL используйте bindings к parser PostgreSQL, например libpg_query. Adapter
должен возвращать контракт `postgres/query_ast_contract.json`:

```text
statement type
read relations/columns
write relations/columns
predicates
parameters
joins
locking clause
returning
CTE/subqueries
source location
construction class
```

Не пытайтесь анализировать SQL регулярными выражениями, кроме очень узких migration hot-spots.

## 10.4. Parameterization и dynamic SQL

Параметризация защищает значения, но не доказывает корректность запроса. StateGuard отдельно
проверяет:

- пользовательские values передаются как parameters;
- dynamic identifiers выбираются из closed allowlist;
- tenant/authorization predicate присутствует;
- status/version guards соответствуют command;
- `RETURNING` используется для определения accepted/rejected outcome;
- empty update корректно классифицирован.

Безопасный пример перехода:

```sql
UPDATE orders
SET status = 'submitted', version = version + 1
WHERE id = $1
  AND status = 'draft'
  AND version = $2
RETURNING id, status, version;
```

Один statement даёт ясный linearization point. Если строка не вернулась, handler выполняет
дополнительное read только для классификации отказа, не повторяя update вслепую.

## 10.5. Check-then-write

Подозрительный паттерн:

```text
SELECT current state
→ check in application
→ UPDATE by id
```

Он допустим только при доказанном механизме:

- row lock в общей transaction;
- serializable isolation + full retry;
- version predicate;
- invariant-enforcing constraint;
- операция коммутативна и atomic.

StateGuard graph query должен находить разделённые read/write и искать один из механизмов.

## 10.6. SERIALIZABLE и retry

Если используется `SERIALIZABLE`:

- retry охватывает всю transaction function;
- side effects внутри неё отсутствуют либо идемпотентны и привязаны к durable intent;
- max attempts/backoff заданы;
- serialization failure отличима от business rejection;
- transaction input стабилен между retries;
- generated IDs/clock/randomness передаются как command data либо корректно переиспользуются.

Нельзя повторять только последний SQL statement: read set и решение могли устареть.

## 10.7. Outbox

Рекомендуемая схема:

```sql
CREATE TABLE outbox (
  id uuid PRIMARY KEY,
  aggregate_type text NOT NULL,
  aggregate_id uuid NOT NULL,
  event_type text NOT NULL,
  payload jsonb NOT NULL,
  idempotency_key text NOT NULL UNIQUE,
  occurred_at timestamptz NOT NULL,
  published_at timestamptz,
  attempts integer NOT NULL DEFAULT 0,
  last_error text
);
```

Domain update и outbox insert выполняются в одной transaction. Publisher:

- забирает batch через locking/claim strategy;
- публикует с idempotency key;
- отмечает результат;
- повторяет с bounded backoff;
- сохраняет unknown outcome;
- имеет reconciliation.

Статический анализ проверяет отсутствие direct publish в transaction handler и наличие outbox write
в mapping эффекта. Интеграционные тесты проверяют crash points.

## 10.8. Query correctness

Для каждой критичной observation задаётся reference function. Тестовый oracle сравнивает:

```text
actual SQL result
vs
expected projection из generated model state
```

Обязательные классы fixtures:

- пустая база;
- одна строка;
- несколько tenants/users;
- `NULL` и optional relations;
- duplicate-producing joins;
- boundary timestamps;
- pagination boundary;
- deleted/archived rows;
- permissions combinations;
- concurrent update snapshot.

Проверяйте и строки, и count/metadata. Неверный `COUNT(*)` при правильной странице — реальный дефект.

## 10.9. Migrations: expand/contract

Для rolling deployment:

```text
expand schema
→ deploy code writing both/compatible representations
→ backfill resumably
→ validate constraints
→ switch reads
→ stop old writes
→ contract old schema
```

Каждая стадия — отдельное допустимое состояние системы и отдельный refinement. «Migration пройдёт
быстро» не является моделью совместимости.

## 10.10. Backfill contract

Backfill должен быть:

- idempotent;
- resumable;
- batched;
- observable;
- bounded by timeout/load;
- safe under concurrent writes;
- версионирован;
- проверяем postcondition query.

Храните progress marker или используйте predicate, позволяющий безопасно повторить batch.

## 10.11. Dangerous migration checks

Минимальные правила:

- table/column drop без compatibility window;
- type rewrite большой таблицы;
- blocking index creation;
- non-null без staged backfill;
- volatile default/rewrite;
- long validation lock;
- rename, несовместимый со старой версией;
- trigger/function replacement без contract test;
- enum change, несовместимый с драйвером/ORM;
- RLS policy ослаблена;
- constraint удалён без specification change.

Squawk или аналог используется как baseline, затем добавляются company-specific checks.

## 10.12. Database test layers

```text
schema smoke          — migrations применяются с нуля
upgrade test          — поддерживаемая предыдущая версия → current
catalog assertions    — expected constraints/indexes/RLS
pgTAP                  — SQL-level invariants/functions
query oracle           — SQL vs reference projection
concurrency tests      — parallel commands
failure injection      — rollback/crash/retry/outbox
performance guard      — plan/time budgets отдельно
```

Используется реальная поддерживаемая версия PostgreSQL, а не SQLite-заменитель.

## 10.13. Production data validation

Перед dangerous migration запускайте read-only invariant queries на production replica/approved
snapshot. В StateGuard сохраняются только aggregate result и query hash, если данные чувствительны.

Пример:

```sql
SELECT count(*)
FROM orders o
LEFT JOIN payments p ON p.id = o.payment_id
WHERE o.status = 'paid'
  AND (p.id IS NULL OR p.status <> 'confirmed');
```

Ожидаемый результат — 0. Ненулевой результат блокирует migration и создаёт remediation workflow.

## 10.14. Ownership

Каждый critical table/invariant имеет:

- domain owner;
- schema owner;
- migration approver;
- recovery runbook;
- data classification;
- proof policy.

База — не «деталь repository layer». Для StateGuard она является исполняемой частью спецификации.
