# 00. Резюме решения

## Решение в одном абзаце

StateGuard строится как локальная доказательная система поверх нескольких специализированных
инструментов. SonarQube Community Build централизует проекты, историю, quality gates, coverage и
внешние findings. Semgrep CE быстро исполняет понятные корпоративные правила. Joern строит CPG и
даёт межфайловые control/data-flow факты. Декларативная спецификация и Event-B описывают бизнес-
состояния, инварианты и события. ProB ищет counterexamples, Z3 закрывает небольшие формулы,
PostgreSQL и Testcontainers проверяют реальную транзакционную семантику. ИИ-агент разбирает только
неоднозначные graph slices. SQLite/PostgreSQL ledger сохраняет хэши, evidence и lifecycle каждого
обязательства.

## Почему не один анализатор

Один анализатор неизбежно смешивает разные классы задач:

- синтаксические дефекты;
- межпроцедурные пути;
- бизнес-семантику;
- реляционные ограничения;
- конкурентность;
- поведение UI;
- соответствие реализации спецификации.

SonarQube хорошо управляет качеством организации, но не является application property graph.
Semgrep хорошо выражает локальные шаблоны, но Community Edition не следует считать полным
межфайловым доказателем. Joern понимает граф программы, но не знает бизнес-требований. Event-B
доказывает модель, но не автоматически написанный вручную production code. Поэтому StateGuard
сводит результаты в единый контракт доказательств.

## Целевая цепочка

```text
Declarative specification + Event-B
                ↓
Repository manifest and framework mappings
                ↓
Native analyzers + Semgrep CE + Sonar analyzers + SQL parser
                ↓
Joern CPG → normalized Application Property Graph
                ↓
Generated proof obligations
                ↓
Rodin/ProB + Z3 + graph queries + PostgreSQL checks
                ↓
Integration, migration and concurrency tests
                ↓
Local AI review of unresolved obligations
                ↓
Persistent audit ledger
                ↓
SonarQube dashboard + StateGuard release gate + fix prompt
```

## Выбранные компоненты

| Назначение | Компонент | Статус |
|---|---|---|
| Организационная витрина | SonarQube Community Build | обязательный при масштабировании |
| Быстрые корпоративные правила | Semgrep CE | обязательный |
| Глубокий граф программы | Joern | ночной/релизный и критичные PR |
| Доменная спецификация | YAML contract + Event-B | критичные bounded contexts |
| Proof/model checking | Rodin + ProB | обязательный для Event-B scope |
| SMT | Z3 | только узкие формулы |
| PostgreSQL parser | libpg_query adapter | обязательный для PostgreSQL SQL |
| Реальная БД | PostgreSQL + Testcontainers | обязательный |
| Migration safety | Squawk + собственные checks | PostgreSQL projects |
| Findings interchange | SARIF 2.1.0 | обязательный |
| Local ledger | SQLite WAL | один репозиторий/агентный аудит |
| Central ledger | PostgreSQL | десятки и сотни репозиториев |
| Неоднозначности | локальный LLM через Ollama/vLLM | после детерминированных проверок |

## Граница ответственности SonarQube

SonarQube отвечает за:

- каталог проектов;
- стандартные bugs/vulnerabilities/code smells;
- coverage, duplication, complexity;
- историю main branch;
- quality gates;
- показ SARIF findings разработчикам.

SonarQube не отвечает за:

- истинность бизнес-инвариантов;
- полноту вертикальных срезов;
- связь Event-B event с SQL transaction;
- актуальность evidence после изменения конкретных файлов;
- multi-agent claims;
- lifecycle proof obligations;
- решение о том, что AI-review является доказательством.

## Начальная стоимость

Лицензионная стоимость базовой локальной версии близка к нулю. Существенные затраты:

- разработка framework adapters;
- создание корпоративного ruleset;
- формализация критичных workflow;
- поддержка CI runners;
- обучение команды писать инварианты и counterexamples;
- управление false positives и proof debt.

## Реалистичный результат первого квартала

За 8–12 недель команда может получить:

- внутренний SonarQube;
- Semgrep baseline для всех репозиториев;
- StateGuard manifest/ledger;
- 10–20 высокосигнальных правил;
- один формализованный bounded context;
- PostgreSQL catalog extraction;
- generated fix prompt;
- release gate для critical/high findings;
- измеримые показатели покрытия и stale evidence.

Попытка сразу формально доказать все репозитории приведёт к дорогому проекту без ранней пользы.
Внедрение должно идти слоями, сохраняя работающий результат после каждого этапа.
