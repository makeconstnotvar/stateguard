# 16. Эксплуатация и масштабирование

## 16.1. Единица масштабирования

Нагрузка определяется не числом репозиториев само по себе, а:

- LOC и языками;
- частотой commits;
- количеством critical components;
- глубиной APG;
- числом proof obligations;
- DB test duration;
- AI unresolved rate.

10 огромных monorepo могут быть тяжелее 500 небольших сервисов.

## 16.2. Worker classes

```text
fast workers
  4–8 CPU, moderate RAM
  native analyzers, Semgrep, manifest

db workers
  Docker/Testcontainers, fast local SSD
  migrations, pgTAP, concurrency

deep workers
  high RAM/CPU
  Joern/CPG/APG

formal workers
  Rodin/ProB/Z3

ai workers
  GPU/large RAM, no egress
```

Queues разделяются, чтобы тяжёлый job не блокировал PR feedback.

## 16.3. Scheduling

Priority score:

```text
release-blocking
+ severity
+ changed critical surface
+ evidence staleness
+ repository tier
+ SLA age
- estimated cost
```

Nightly scheduler избегает одновременного полного анализа всех репозиториев.

## 16.4. Repository tiers

```text
Tier 0 — деньги, identity, permissions, irreversible operations
Tier 1 — core business state
Tier 2 — supporting services/backoffice
Tier 3 — low-risk/internal tooling
```

Tier определяет:

- required evidence;
- scan frequency;
- strictness;
- model scope;
- retention;
- recovery SLA.

## 16.5. Central metrics

### Coverage

- % current artifacts reviewed;
- % critical surfaces mapped;
- % critical/high invariants with required evidence;
- % repositories on current policy/toolchain;
- stale evidence age.

### Effectiveness

- escaped defects by class;
- findings confirmed rate;
- false-positive rate;
- recurrence after fix;
- mean time to counterexample;
- mean time to verified fix.

### Cost

- CPU hours per repository;
- CPG storage;
- AI GPU/token-equivalent cost;
- PR latency;
- maintenance hours per ruleset/adapters.

Не оптимизируйте количество findings вверх. Хороший инструмент может выдавать меньше, но точнее.

## 16.6. SLO

Пример:

```text
95% PR fast scans < 12 min
99% main analyses published < 2 h after merge
Tier 0 nightly evidence freshness < 24 h
critical finding triage < 4 business h
expired waiver detection < 1 h
central dashboard availability 99.5%
```

## 16.7. Tool version management

Матрица:

```text
approved
pilot
deprecated
blocked
```

Upgrade waves:

1. synthetic benchmark;
2. canary 5 repositories;
3. 20%;
4. 50%;
5. all;
6. old version removal.

Сравниваются finding delta, crash rate и duration.

## 16.8. Ruleset rollout

Новые правила сначала работают `info/observe`. Central dashboard показывает потенциальный объём.
После tuning:

- new-code warning;
- blocking для selected tiers;
- organization-wide blocking.

## 16.9. Incident response

Инциденты StateGuard:

- false green из-за parser/adapter regression;
- массовый false positive;
- analyzer compromise;
- Sonar data exposure;
- central ledger loss;
- CI gate bypass;
- proof invalidated by tool bug.

Runbook:

1. остановить affected verdict publication;
2. определить versions/ruleset hashes;
3. пометить related proofs stale centrally;
4. re-run affected commits;
5. уведомить owners;
6. зафиксировать root cause и regression fixture.

## 16.10. Support model

Минимальная platform team:

- product/tech lead StateGuard;
- static-analysis engineer;
- DB/concurrency engineer;
- formal-methods champion part-time/full-time по scope;
- DevOps/platform engineer;
- security partner;
- domain champions в продуктовых командах.

Без domain owners формальная спецификация быстро станет документацией, не отражающей продукт.

## 16.11. Cost control

Самые дешёвые действия:

- улучшить архитектурную дисциплину;
- сделать transitions/transactions явными;
- добавить DB constraints;
- убрать dynamic SQL;
- стандартизировать framework adapters;
- запускать deep/AI только на unresolved scope.

Плохая архитектура делает любой анализатор дорогим.

## 16.12. Capacity planning

Соберите baseline на репозитории каждого типа:

```text
manifest time
Semgrep time/RAM
Sonar scan time
Joern parse/query time/RAM/CPG size
DB test time
model-check state count/time
AI context/output size
```

Планируйте p95 × scheduled concurrency × safety factor. Не используйте маркетинговое число
«репозиториев на сервер».
