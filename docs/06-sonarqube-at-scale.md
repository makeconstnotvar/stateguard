# 06. SonarQube при десятках и сотнях репозиториев

## 6.1. Роль в StateGuard

SonarQube — центральная витрина инженерного качества, а не источник истины по доменной корректности.
Он хранит проекты, историю, стандартные issues, coverage и quality gates. StateGuard ledger хранит
proof obligations, модель, хэши evidence, waivers и counterexamples.

```text
Developer/CI
  ├─ SonarScanner ───────────────→ SonarQube
  └─ StateGuard/Semgrep/Joern ───→ local ledger → central StateGuard DB
                                      └─ SARIF → SonarScanner → SonarQube
```

## 6.2. Развёртывание

В `infra/docker-compose.sonarqube.yml` дан односерверный внутренний контур:

- SonarQube Community Build;
- отдельный PostgreSQL;
- persistent volumes;
- internal DB network;
- localhost bind по умолчанию;
- kernel/ulimit настройки;
- backup script.

Это стартовый вариант, а не эталон высокой доступности. Для production:

- образы зеркалируются во внутренний registry и фиксируются digest;
- PostgreSQL переносится на управляемый внутренний кластер или отдельные VM;
- TLS завершается на корпоративном reverse proxy;
- аутентификация подключается к корпоративному IdP в доступной редакции;
- secrets выдаются через vault/CI secret store;
- volumes и database backup включаются в корпоративный DR;
- upgrade сначала проходит на staging-копии БД.

## 6.3. Project provisioning

Project key должен быть детерминирован:

```text
<org>:<business-unit>:<repository>[:<subproject>]
```

Пример:

```text
acme:commerce:order-service
acme:commerce:backoffice:web
```

Provisioning автоматизируется через API и IaC. Скрипт в архиве создаёт проект; production-версия
должна дополнительно назначать:

- owner group;
- quality profile;
- quality gate;
- permission template;
- default branch;
- tags;
- retention policy;
- project-analysis token.

Admin token не передаётся в project pipeline. Pipeline получает только project-scoped analysis
token.

## 6.4. Quality profiles

Создайте минимальное число профилей:

```text
Company Java
Company JavaScript
Company CSharp
Company Python
Company Go
```

Не клонируйте профиль на каждый продукт. Отличия продукта оформляются StateGuard policy и Semgrep
rules, а не сотней дрейфующих Sonar profiles.

Профиль меняется через versioned change request:

- rule added/removed;
- ожидаемый объём новых issues;
- false-positive sample;
- rollout date;
- migration/SLA для existing code.

## 6.5. Quality gates

Рекомендуемый gate нового кода:

- new reliability/security rating соответствует корпоративной политике;
- new coverage не ниже согласованного порога;
- new duplication ограничена;
- critical/high StateGuard external issues отсутствуют;
- внешний StateGuard CI status пройден.

Не применяйте жесткий gate ко всей legacy codebase в первый день. Используйте подход:

```text
legacy baseline зафиксирован
новый код не ухудшает состояние
critical legacy findings имеют отдельный remediation plan
```

При этом нарушения ключевых инвариантов не «дедушкуются»: они блокируют независимо от возраста.

## 6.6. External SARIF

StateGuard экспортирует SARIF в `.stateguard/results/stateguard.sarif`. В
`sonar-project.properties` задаётся:

```properties
sonar.sarifReportPaths=.stateguard/results/stateguard.sarif
```

Перед SonarScanner должны завершиться:

1. StateGuard scan;
2. Semgrep import;
3. proof/test aggregation;
4. SARIF export.

External issues используются для видимости. Их lifecycle в Sonar не считается authoritative,
поскольку закрытие/принятие в Sonar не обновляет StateGuard ledger. Следующий анализ пересоздаст
issue, если доказательная причина сохраняется.

## 6.7. Branches и pull requests

Бесплатная Community Build удобна как main-branch dashboard. PR gate можно независимо реализовать
через CI:

```text
Semgrep + StateGuard incremental + tests → required CI status
merge
→ full main analysis → SonarQube
```

Если организации нужны полноценная branch history и PR decoration внутри Sonar, это отдельное
решение о платной редакции. Не покупайте её ради функции, которую текущий CI уже надёжно выполняет.
Покупайте, когда централизованная PR-операционка действительно экономит больше, чем стоит лицензия.

## 6.8. Масштабирование ресурсов

Нагрузку определяют:

- суммарный LOC;
- частота analysis jobs;
- число языков;
- размер reports;
- параллелизм compute engine;
- retention истории;
- объём Elasticsearch indexes.

Порядок:

1. собрать p50/p95 длительности и queue time;
2. ограничить бессмысленные повторные scans;
3. разделить fast PR checks и main analysis;
4. увеличить CPU/RAM;
5. оптимизировать DB и storage latency;
6. переходить к следующей архитектуре только после измерений.

SonarQube и Joern не должны жить на одном перегруженном host: у них разные профили памяти и I/O.

## 6.9. Backup и recovery

Backup включает:

- PostgreSQL dump/snapshot;
- extensions/plugins inventory;
- exact image digest;
- server configuration;
- encryption/secret references;
- restore runbook.

Data/search indexes Sonar восстанавливаются согласно поддерживаемой процедуре выбранной версии.
Проверка восстановления проводится регулярно на изолированном окружении. Backup, который никто не
восстанавливал, является предположением, а не гарантией.

## 6.10. Upgrade

Процедура обновления:

1. прочитать release/upgrade notes;
2. проверить совместимость PostgreSQL, Java/runtime и plugins;
3. сделать tested backup;
4. клонировать production DB на staging;
5. запустить новую pinned image;
6. выполнить smoke scans нескольких языков;
7. сравнить issue delta и duration;
8. назначить maintenance window;
9. обновить production;
10. зафиксировать image digest и tool version в StateGuard.

Auto-update контейнера запрещён. Он уничтожает воспроизводимость анализа.

## 6.11. Доступ и приватность

SonarQube находится в доверенной корпоративной зоне, потому что analysis reports содержат:

- пути файлов;
- fragments/messages;
- имена символов;
- security findings;
- repository metadata.

Минимум:

- network ACL;
- TLS;
- SSO/strong auth;
- least privilege;
- audit logs;
- project permission templates;
- запрет публичных проектов;
- проверенная backup encryption;
- controlled plugins.

## 6.12. Метрики эксплуатации

Следить нужно не только за количеством issues:

- analysis success rate;
- queue p95;
- main branch freshness;
- scanner version drift;
- projects without scan N days;
- failed SARIF imports;
- gate bypass count;
- false-positive rate по профилям;
- mean time to remediate critical/high;
- число project tokens старше policy срока.
