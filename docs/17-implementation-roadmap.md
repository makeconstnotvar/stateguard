# 17. Пошаговый план реализации

## 17.1. Принцип

Каждая фаза заканчивается работающим полезным продуктом. Формальная часть добавляется поверх
дисциплинированного baseline, а не вместо него.

## Phase 0. Решение и scope — 1–2 недели

Результаты:

- executive sponsor;
- 3–5 pilot repositories;
- repository tiers;
- privacy/network policy;
- initial correctness taxonomy;
- одна critical business flow для formal pilot;
- success metrics;
- владельцы.

Не начинать разработку control plane до согласования того, что считается finding/proof/green.

## Phase 1. Локальный baseline — 2–4 недели

Внедрить:

- StateGuard CLI из архива;
- repository manifest/hash;
- SQLite ledger;
- native analyzers;
- Semgrep CE offline;
- SARIF import/export;
- fix prompt;
- CI non-blocking.

Definition of done:

- pilot repos сканируются воспроизводимо;
- изменение файла invalidates review;
- findings имеют stable IDs;
- отчёты не покидают сеть;
- команда умеет воспроизводить запуск.

## Phase 2. SonarQube organizational layer — 2–4 недели

Внедрить:

- internal SonarQube + PostgreSQL;
- backups/restore test;
- project provisioning;
- quality profiles/gates;
- main branch scans;
- StateGuard SARIF import;
- ownership/dashboard.

Definition of done:

- все pilot repos видны;
- gate и StateGuard status разделены;
- tokens least-privilege;
- staging upgrade procedure документирована.

## Phase 3. Corporate Semgrep rules — 4–8 недель параллельно

Создать первые 10–20 high-signal rules и fixtures. Начать с incidents/code review patterns.

Definition of done:

- precision согласована;
- rule changes versioned;
- fast profile укладывается в CI budget;
- suppression требует waiver/reason;
- ruleset hash сохраняется.

## Phase 4. Specification and mappings — 3–6 недель

Для одного bounded context:

- entities/states;
- invariants;
- commands/outcomes;
- observations/effects;
- assumptions;
- implementation mappings;
- proof policy.

Definition of done:

- domain owner подтвердил модель;
- IDs связаны с handlers/SQL/tests;
- gaps видимы;
- model review проходит вместе с code review.

## Phase 5. PostgreSQL enforcement/test contour — 4–8 недель

Внедрить:

- disposable migrated DB;
- catalog snapshot;
- migration analyzer;
- constraint assertions;
- query oracles;
- concurrency tests;
- outbox/retry patterns.

Definition of done:

- critical invariants имеют DB/test evidence;
- два реальных race scenario воспроизводятся и закрыты;
- migration upgrade path тестируется.

## Phase 6. Joern/APG pilot — 6–12 недель

Не пытайтесь сразу поддержать все языки. Один основной стек:

- Joern frontend;
- framework adapter;
- stable APG schema;
- authorization dominance;
- transaction containment;
- input-to-sink flow;
- effect ordering;
- graph slices.

Definition of done:

- benchmark показывает полезный cross-file signal;
- adapters имеют golden tests;
- incremental/full reconciliation понятны;
- APG outputs привязаны к hashes.

## Phase 7. Event-B/ProB — 6–12 недель параллельно

Для выбранного workflow:

- M0 domain;
- M1 total outcomes;
- M2 persistence mapping;
- M3 concurrency/effects по необходимости;
- Rodin proofs;
- ProB model checking;
- generated traces → integration tests.

Definition of done:

- найден хотя бы один meaningful counterexample либо модель существенно упростила reasoning;
- proof status импортирован;
- concrete implementation mapping проверяется;
- domain team поддерживает модель.

## Phase 8. Z3 obligations — 3–6 недель

Автоматизировать только:

- outcome totality/exclusivity;
- guard overlap;
- arithmetic limits;
- small bounded predicates.

Definition of done:

- translation имеет tests;
- counterexamples читаемы;
- unsupported constructs дают `inconclusive`, не false proof.

## Phase 9. Local AI — 3–8 недель

Подключить после накопления structured unresolved cases:

- approved local runtime;
- context packager;
- JSON output schema;
- benchmark;
- review/fix/verify roles;
- strict permissions.

Definition of done:

- agent экономит время на benchmark;
- evidence citations проверяются;
- no egress подтверждён инфраструктурой;
- AI-only не закрывает critical obligations.

## Phase 10. Central control plane — после 10–30 репозиториев

Строить, когда local schema/process стабилизированы:

- PostgreSQL central ledger;
- publish API/idempotency;
- repository inventory;
- policy distribution;
- waiver/SLA workflow;
- aggregate coverage;
- remediation queue.

Definition of done:

- source code не требуется central service;
- run reproducible from commit/toolchain;
- dashboards отвечают на operational questions;
- local audit продолжает работать при outage central plane.

## 17.2. Первые 90 дней

### Дни 1–30

- развернуть Sonar staging;
- установить StateGuard MVP на 3 repositories;
- включить Semgrep offline;
- собрать baseline;
- выбрать один workflow;
- обучить owners taxonomy.

### Дни 31–60

- main scans и SARIF;
- 10 company rules;
- catalog/migration tests;
- specification/mappings workflow;
- первые concurrency tests;
- metrics dashboard.

### Дни 61–90

- blocking new-code policy;
- Event-B/ProB pilot;
- Joern proof-of-concept на одном языке;
- generated fix prompts;
- restore/incident exercises;
- решение о следующем масштабе.

## 17.3. Не делать в первой версии

- универсальный IDE;
- собственный parser всех языков;
- полный перевод production code в SMT;
- central microservice zoo;
- AI-first audit без deterministic manifest;
- formal model каждой CRUD-таблицы;
- кастомный Sonar plugin для каждого правила;
- обещание «zero bugs».

## 17.4. Команда и бюджет

Pilot можно вести небольшой platform-группой, но production APG/control-plane — полноценный продукт.
Планируйте roadmap и ownership, а не «один разработчик прикрутит пару линтеров».

## 17.5. Exit criteria

Перед расширением на всю организацию:

- ≥80% high findings pilot подтверждаются полезными;
- PR p95 приемлем;
- false-green incidents расследуются;
- owners обновляют specs/mappings;
- strict gate прошёл хотя бы один release;
- доказан restore;
- security approve local processing;
- стоимость одного repo измерена.
