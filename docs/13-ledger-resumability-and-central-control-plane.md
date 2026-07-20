# 13. Ledger, возобновляемость и центральный control plane

## 13.1. Зачем ledger

Большой репозиторий не помещается в один контекст и не анализируется за одну сессию. Ledger
превращает аудит в транзакционный процесс:

- каждый файл имеет current hash;
- review unit имеет aggregate hash;
- finding связан с evidence hash;
- proof obligation имеет input hash;
- worker получает lease;
- изменение input делает результат stale;
- история сохраняется.

## 13.2. Локальный SQLite

MVP использует:

```text
<repo>/.stateguard/audit.db
```

Настройки:

- WAL;
- foreign keys;
- busy timeout;
- `BEGIN IMMEDIATE` для claims/critical updates;
- repository-relative paths;
- source code не копируется целиком.

SQLite подходит для одного checkout и нескольких локальных workers. Не помещайте один WAL-файл на
ненадёжный shared network filesystem.

## 13.3. Основные таблицы

- `artifacts`: manifest и review hashes;
- `review_units`: chunks/components и leases;
- `findings`: нормализованные дефекты;
- `evidence`: excerpts/payload references;
- `proof_obligations`/`proof_attempts`/`proof_inputs`;
- `tool_runs`;
- `apg_nodes`/`apg_edges`;
- `waivers`;
- `remediation_batches`;
- `audit_runs`/`metadata`.

Полная схема находится в `sql/ledger.sql`.

## 13.4. Scan semantics

`stateguard scan`:

1. создаёт audit run;
2. обходит утверждённые roots;
3. применяет excludes/generated classification;
4. считает SHA-256;
5. отмечает added/changed/deleted;
6. invalidates связанные units;
7. переводит current findings в `stale-evidence`;
8. переводит proof obligations в `stale`;
9. завершает run с summary.

Старые результаты не удаляются. Они больше не участвуют в verdict, но полезны для истории.

## 13.5. Review units

`autoplan` группирует файлы по компонентам и ограничивает размер unit. Производственная версия
использует APG/dependency graph и explicit mappings:

```text
vertical command slice
read-model slice
migration slice
shared library slice
UI flow slice
```

Unit хранит current/reviewed aggregate hashes. `complete` допустим только при совпадении состава и
хэшей с выданным claim.

## 13.6. Claims и leases

```text
claim(worker, lease)
```

атомарно выбирает highest-priority доступный unit. Lease предотвращает вечную блокировку после
падения агента. Worker периодически heartbeat-ит long task; MVP использует fixed lease и reclaim.

В production добавьте:

- heartbeat;
- max extensions;
- worker capabilities;
- claim audit log;
- cancellation;
- optimistic fencing token, чтобы просроченный worker не записал результат после reclaim.

## 13.7. Finding lifecycle

Рекомендуемые статусы:

```text
open
triaged
fixed-pending-verification
closed
false-positive
accepted-risk
stale-evidence
not-observed
reopened
```

Finding закрывается, если:

- counterexample больше не воспроизводится;
- required tests/checks прошли;
- source evidence относится к current hash;
- related obligations обновлены;
- verifier независим от fix attempt по policy.

## 13.8. Waivers

Waiver содержит:

- точный finding/obligation;
- reason;
- risk/impact;
- compensating controls;
- owner/approver;
- expiry;
- ticket/decision reference;
- affected versions.

Истёкший waiver переводит обязательство в failing state. Бессрочные waivers для critical свойств
запрещаются либо требуют executive approval.

## 13.9. Central PostgreSQL

При множестве репозиториев local ledgers публикуют summaries в central control plane. Рекомендуемая
модель multi-tenant by organization/repository/commit.

Central service хранит:

- repositories/components/owners;
- scan runs/tool versions;
- findings/proof statuses;
- policy/ruleset versions;
- artifact identities/hashes;
- waivers/SLA;
- remediation batches;
- aggregate metrics.

Он не обязан хранить source contents и raw CPG.

## 13.10. Publication contract

Pipeline подписывает manifest:

```json
{
  "repository": "acme/order-service",
  "commit": "...",
  "runId": "...",
  "policyHash": "...",
  "toolchain": {...},
  "artifacts": [{"pathHash": "...", "sha256": "..."}],
  "findings": [...],
  "proofs": [...]
}
```

Для особо чувствительных репозиториев можно хэшировать paths и хранить детали только локально;
центральный dashboard показывает aggregate risk и deep-link во внутренний job artifact.

## 13.11. Idempotency

Publish API использует idempotency key:

```text
repository + commit + policy hash + run type
```

Повтор публикации заменяет/подтверждает тот же run, не создаёт дубликат.

## 13.12. Retention

- current main evidence: долгосрочно;
- superseded proof attempts: согласно audit policy;
- raw logs: 30–180 дней;
- raw CPG: минимально;
- AI excerpts: минимально и шифрованно;
- artifact hashes: достаточно долго для release traceability.

## 13.13. Disaster recovery

Локальный ledger воспроизводим из repository + tools, но центральные waivers/decisions и history
требуют backup. Проверяется restore central DB и возможность связать restored evidence с commit.

## 13.14. MVP ограничения

В данном комплекте central service не реализован как готовый SaaS. Есть local CLI и подробный
контракт. До разработки control plane сначала подтвердите процесс на 5–10 репозиториях: иначе будет
создана дорогая панель для данных, которым команда ещё не доверяет.
