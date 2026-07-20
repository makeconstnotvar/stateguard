# StateGuard: Бюро запрещённых состояний

**StateGuard** — локальная система возобновляемого аудита корректности обычных бизнес-приложений.
UI, API/сервер, фоновые процессы, база данных, интеграции и migrations рассматриваются как одна
реализация доменной машины состояний.

> **Бюро запрещённых состояний** расследует самовольные транзакции, потерянные обновления,
> незаконный оборот nullable-полей и другие способы тихо испортить данные.

Этот архив — подробный implementation kit, а не рекламная презентация. Он содержит архитектуру,
операционный план, конфигурации, starter rules, contracts, демонстрационный vertical slice и рабочий
MVP CLI с persistent ledger.

## Какой эффект даёт система

StateGuard проверяет не только отдельные строки кода, а цепочки:

```text
UI/input
→ decoder/validator
→ authorization
→ command/guard
→ transaction/database
→ external effect
→ query/response
→ UI projection
```

Цель для каждой команды:

```text
корректное состояние + допустимая команда
→ атомарно новое корректное состояние + типизированный результат
OR
→ типизированный отказ без частичного изменения
```

Для больших репозиториев результаты сохраняются по SHA-256. Аудит можно прервать, продолжить в другой
сессии или распределить между агентами. После изменения файла старое evidence автоматически
становится `stale`.

## Выбранная архитектура

```text
Declarative specification + Event-B
                ↓
Native analyzers + Semgrep CE + Sonar analyzers + SQL parser
                ↓
Joern CPG → Application Property Graph
                ↓
Generated proof obligations
                ↓
Rodin/ProB + Z3 + graph queries + PostgreSQL checks
                ↓
Integration/concurrency/migration tests
                ↓
Local AI review only for unresolved semantic cases
                ↓
Persistent ledger
                ↓
SonarQube dashboard + StateGuard strict gate + fix prompt
```

Разделение ответственности:

- **SonarQube Community Build** — центральные проекты, история, стандартные issues, coverage,
  duplication и quality gates;
- **Semgrep CE** — дешёвые корпоративные правила на каждом PR;
- **Joern** — глубокий межфайловый CPG/APG;
- **Event-B/Rodin/ProB** — критичные состояния, инварианты, события и counterexamples;
- **Z3** — узкие автоматически генерируемые формулы;
- **PostgreSQL/Testcontainers** — реальная семантика constraints, transactions и concurrency;
- **локальный ИИ** — неоднозначные случаи, fix/verify workflow;
- **StateGuard ledger** — источник истины по coverage, findings, proof status и stale evidence.

SonarQube не подменяет StateGuard ledger, а Semgrep CE не имеет ограничения платформенного тарифа на
число локально сканируемых репозиториев.

## Что уже реализовано в MVP CLI

```text
stateguard init
stateguard validate
stateguard scan
stateguard autoplan
stateguard claim
stateguard complete
stateguard import-sarif
stateguard export-sarif
stateguard apg-import
stateguard proof-record
stateguard finding-add
stateguard finding-status
stateguard status
stateguard doctor
stateguard generate-fix-prompt
```

MVP умеет:

- создавать `.stateguard/` и SQLite WAL ledger;
- валидировать config/specification/mappings;
- строить manifest файлов с SHA-256;
- автоматически делить репозиторий на review units;
- атомарно выдавать units воркерам через leases;
- инвалидировать review, findings и proofs после изменения файлов;
- импортировать/экспортировать SARIF 2.1.0;
- импортировать normalized APG JSONL;
- записывать proof attempts с input hashes;
- создавать доказательные findings;
- генерировать автономный prompt для fix-agent;
- блокировать финальный verdict через `doctor --strict`.

## Быстрый запуск CLI

Требования:

- Python 3.11+;
- Git;
- Docker Engine/Compose для containerized analyzers и integration tests;
- внешние инструменты устанавливаются отдельно по мере внедрения.

```bash
cd stateguard-implementation-kit
python -m venv .venv
. .venv/bin/activate
python -m pip install -e '.[dev,validation,smt]'
make test
make validate-kit
```

Либо установите собранный wheel из `dist/` через утверждённый внутренний Python mirror для
зависимостей:

```bash
python -m pip install dist/stateguard_mvp-0.1.0-py3-none-any.whl
```

Для полностью air-gapped установки заранее соберите внутренний wheelhouse зависимостей; сторонние
binaries и wheels намеренно не вложены в архив.

Инициализация продукта:

```bash
cd /path/to/product
stateguard init --project-key acme-order-service --project-name "Order Service"
cp /path/to/stateguard-implementation-kit/config/semgrep/rules/*.yml .stateguard/rules/

stateguard validate
stateguard scan
stateguard autoplan
stateguard claim --worker reviewer-1
```

После смыслового review выданного среза:

```bash
stateguard finding-add \
  --rule SG-TX-001 \
  --title "Неатомарный переход" \
  --message "Связанные записи выполняются вне общей транзакции" \
  --severity high \
  --file server/orders.js \
  --line 42 \
  --counterexample "Первая запись commit, вторая завершается ошибкой" \
  --remediation "Объединить writes в одну transaction и добавить rollback test" \
  --verification "Failure-injection test сохраняет исходное состояние"

stateguard complete --unit auto:server --worker reviewer-1
```

Полный локальный MVP-цикл:

```bash
/path/to/kit/scripts/run-local-mvp.sh "$PWD"
stateguard doctor
```

## Semgrep без отправки кода наружу

`run-semgrep.sh` запускает approved container:

- с `--network none`;
- без platform token;
- с `--metrics=off`;
- с read-only repository и rules;
- с единственным writable output.

```bash
/path/to/kit/scripts/verify-offline.sh "$PWD"
/path/to/kit/scripts/run-semgrep.sh "$PWD"
stateguard import-sarif .stateguard/results/semgrep.sarif
```

Starter rules являются шаблонами. Sources, sinks, sanitizers, transaction wrappers и paths нужно
адаптировать под framework конкретного проекта и покрыть fixtures.

## Локальный SonarQube

```bash
cd infra
cp .env.example .env
chmod 600 .env
# Установите длинный случайный SONAR_DB_PASSWORD.
sudo ./scripts/prepare-linux-host.sh
./scripts/up.sh
```

По умолчанию SonarQube привязан к `127.0.0.1:9000`. Production-развёртывание требует внутреннего
registry, immutable image digests, TLS proxy, secrets manager, backups, restore rehearsal, access
control и staging upgrade.

StateGuard SARIF подключается в `sonar-project.properties`:

```properties
sonar.sarifReportPaths=.stateguard/results/stateguard.sarif
```

## Joern/APG

```bash
/path/to/kit/scripts/run-joern.sh "$PWD"
```

В комплекте есть starter Joern export. Production adapter должен нормализовать CPG вместе с SQL AST,
PostgreSQL catalog, API schemas и mappings в APG JSONL:

```bash
stateguard apg-import .stateguard/results/application-graph.jsonl \
  --source-tool joern-apg-adapter
```

## Proof attempts

Пример записи model/static/test evidence:

```bash
stateguard proof-record \
  --key PO-CONC-ORDER-NO-LOST-UPDATE \
  --kind concurrency-safety \
  --title "Конкурирующие submit не теряют обновление" \
  --description "Ровно один submit принимает ожидаемую version" \
  --status verified \
  --solver postgres-concurrency-test \
  --criticality high \
  --input server/orders.js \
  --input database/queries/submit.sql \
  --command "npm test -- order-concurrency"
```

## Рекомендуемый порядок чтения

1. [`docs/00-executive-summary.md`](docs/00-executive-summary.md)
2. [`docs/01-goals-non-goals-and-guarantees.md`](docs/01-goals-non-goals-and-guarantees.md)
3. [`docs/02-reference-architecture.md`](docs/02-reference-architecture.md)
4. [`docs/17-implementation-roadmap.md`](docs/17-implementation-roadmap.md)
5. [`docs/20-production-readiness-checklist.md`](docs/20-production-readiness-checklist.md)
6. затем документы нужного слоя.

Полный индекс:

| Документ | Тема |
|---|---|
| 03 | контракт репозитория |
| 04 | specification и Event-B |
| 05 | стек анализаторов |
| 06 | SonarQube при масштабировании |
| 07 | программа Semgrep rules |
| 08 | Joern и APG |
| 09 | proof obligations |
| 10 | PostgreSQL, SQL, migrations |
| 11 | integration/concurrency/model tests |
| 12 | локальный AI agent |
| 13 | ledger и central control plane |
| 14 | CI/CD |
| 15 | offline/security/supply chain |
| 16 | эксплуатация и capacity |
| 17 | поэтапный roadmap |
| 18 | team process/governance |
| 19 | risk register |
| 20 | production readiness checklist |
| 21 | contracts/extension points |
| 22 | переход от Codex/Claude skill к engine |
| SOURCES | официальные ссылки |

## Структура архива

```text
stateguard-implementation-kit/
├── README.md
├── docs/                   подробная архитектура и runbooks
├── src/stateguard/         рабочий Python MVP
├── tests/                  тесты MVP
├── sql/ledger.sql          local ledger schema
├── schemas/                JSON Schema контрактов
├── config/                 StateGuard/Sonar/Semgrep examples
├── infra/                  SonarQube + PostgreSQL starter deployment
├── joern/                  CPG export/query examples
├── event-b/                ProB smoke model и formal workflow
├── z3/                     SMT examples
├── postgres/               catalog extraction и SQL AST contract
├── control-plane/          central PostgreSQL/OpenAPI design
├── ci/                     self-hosted GitHub/GitLab/Jenkins templates
├── scripts/                orchestration/validation/offline scripts
└── examples/order-workflow демонстрационный vertical slice
```

## Проверка комплекта

```bash
make test
make validate-kit
make smoke
```

`validate-kit` проверяет:

- JSON/YAML parsing;
- Python compilation/tests;
- shell syntax;
- идентичность distributable schemas;
- Semgrep syntax, если Semgrep установлен;
- Docker Compose rendering, если Docker установлен.

## Формулировка гарантии

StateGuard не обещает мистическое «ошибок нет». Зелёный verdict означает:

> Для текущих хэшей исходников все зарегистрированные critical/high свойства имеют актуальное
> evidence требуемого класса, все заявленные поверхности покрыты, открытых counterexamples и
> незакрытых обязательств в утверждённой области не осталось.

Гарантия ограничена specification, mappings, assumptions, supported runtime и явно указанной
доверенной базой.

## Статус комплекта

Это production-oriented blueprint и рабочий MVP control loop. Для промышленного внедрения нужно
разработать и поддерживать framework adapters, company rules, APG normalization, formal models и
central control plane согласно вашему стеку. В архив не входят сторонние binaries и лицензии.
