# Мастер-план реализации: автономный анализатор репозиториев

Статус на 2026-07-21 (обновлено после второго прохода: генерализация Z3/Event-B, 5
CI-скриптов, `apg.schema.json`). Этот документ — единая точка входа: что должен делать автономный
цикл, что из него реально работает сегодня, что построено как сквозной пример, и что
осталось сделать. Обновляется по мере прогресса; не дублирует `docs/00`–`docs/22` — там
архитектурное обоснование, здесь — конкретный статус и план.

## 1. Что значит «автономный»

Целевой цикл:

```
Декларативная спецификация
        ↓
Semgrep + нативные анализаторы + SonarQube
        ↓
Joern Code Property Graph
        ↓
StateGuard Application Property Graph
        ↓
Proof obligations
        ↓
Event-B/ProB + Z3 + PostgreSQL-проверки
        ↓
Интеграционные и конкурентные тесты
        ↓
Persistent audit ledger
```

**Локальный ИИ для неоднозначных случаев — отдельный, НЕ автономный слой**, а не одна из
стадий цикла. Причина не организационная, а по существу (см. `docs/12-local-ai-agent.md`,
§12.1 и §12.13):

- ИИ подключается только к тому, что детерминированные анализаторы уже не могут закрыть;
- ИИ не определяет полноту audit manifest;
- результат работы ИИ фиксируется статусом `reviewed-ai`, который `doctor --strict`
  специально трактует как *не* доказательство для critical/high obligations
  (`reviewed_ai_critical_proofs` в `src/stateguard/status.py`) — то есть система прямо
  запрограммирована не считать мнение модели автономным закрытием обязательства;
- ИИ требует внешний API/ключ и человека для independent verification (§12.7) — то есть
  по определению не самодостаточен.

Следовательно: **автономное ядро — 8 стадий** (спецификация, Semgrep/native/Sonar, Joern
CPG, APG, proof obligations, Event-B/ProB+Z3+Postgres, интеграционные/конкурентные тесты,
ledger). Локальный ИИ — supervised-надстройка поверх ядра, включается по необходимости и
никогда не заменяет доказательство.

## 2. Статус по стадиям

| # | Стадия | Статус | Ключевые файлы | Пробел |
|---|---|---|---|---|
| 1 | Декларативная спецификация | Валидатор рабочий; авторство вручную | `src/stateguard/validation.py`, `schemas/specification.schema.json`, `schemas/mappings.schema.json` | Генерации спецификации из кода нет и не планируется (сознательно — это human-authored контракт) |
| 2a | Semgrep | Правила реальные, авто-копирование в `.stateguard/rules` работает | `config/semgrep/rules/*.yml`, `src/stateguard/rules.py` (`sync_semgrep_rules`) | Fixture-покрытие неполное (`docs/07` §7.4 контракт соблюдён частично) |
| 2b | Нативные анализаторы (ESLint/Ruff/SpotBugs) | Не реализовано | — | Нулевая реализация; отдельная задача, не начата |
| 2c | SonarQube | Инфраструктура рабочая, интеграция намеренно однонаправленная | `infra/docker-compose.sonarqube.yml`, `infra/scripts/*.sh` | Не нужен для одного репозитория; актуален при организационном масштабе |
| 3 | Joern CPG | Скрипт рабочий, но живого Joern нет в среде разработки | `joern/export_stateguard.sc`, `scripts/run-joern.sh` | Поля вывода не сверены с реальным `joern-parse` — сверка в `src/stateguard/joern_adapter.py`'s `_enrich_line_range` помечена как provisional |
| 4 | StateGuard APG | **Адаптер Joern→APG написан и проверен** (mapping-only + enriched режимы, round-trip тест) + **типизированная JSON-schema для node/edge теперь есть и подключена** | `src/stateguard/joern_adapter.py`, `schemas/apg.schema.json`, `tests/test_joern_adapter.py` | Нет — валидация против словаря `docs/08` теперь обязательна при генерации |
| 5 | Proof obligations | **Генератор из specification.yaml работает** (`PO-<invariant>-BY-<command>`) | `src/stateguard/obligations.py`, `tests/test_obligations.py` | Правило проверено только для order-workflow; для другого репозитория сработает автоматически, т.к. общее |
| 6a | Event-B/ProB | Модель и wrapper реальные; **стадия обобщена** — путь к проекту берётся из `specification.event_b_project` (уже был в схеме, теперь читается `config.py`), `run-prob.sh` остаётся общим kit-level инструментом | `event-b/OrderWorkflow.mch`, `event-b/run-prob.sh`, `src/stateguard/probcli_parser.py`, `src/stateguard/cycle.py` (`_stage_event_b`) | **Требует установки `probcli` для живой проверки** — ни разу не запускался вживую; текст-парсер защитно возвращает `inconclusive` на нераспознанный вывод |
| 6b | Z3 | **Доказательства выведены из specification.yaml и реально проходят** (5/5 PROVED); **стадия обобщена** — `cycle.py` берёт все `<repo>/z3/*.py` по конвенции (`--json` контракт), не один захардкоженный файл | `examples/order-workflow/z3/order_workflow_proofs.py` (перемещён из `z3/` в сам пример) | Покрывает только order-workflow; для нового репозитория формулы нужно писать заново (ожидаемо — Z3 работает с конкретными guard/invariant, не обобщается) |
| 6c | PostgreSQL enforcement | Каталожный snapshot есть, отдельно не используется в цикле | `postgres/catalog_snapshot.sql` | Реальное enforcement-доказательство для order-workflow идёт через стадию 8 (интеграционный тест), не через отдельный catalog-шаг — осознанно не дублировали |
| 7 | Локальный ИИ (не входит в автономное ядро) | **Реализован полностью**: DeepSeek API, JSON-schema валидация ответа, prompt-injection защита (4 категории источников), graceful skip без ключа | `src/stateguard/ai_review.py`, `schemas/ai-finding-review.schema.json`, `tests/test_ai_review.py` | **Ждём `DEEPSEEK_API_KEY`** от пользователя — код не проверен живым вызовом, только через мок |
| 8 | Интеграционные/конкурентные тесты | Тесты в order-workflow реальные (testcontainers + race condition), но Docker не установлен в этой среде | `examples/order-workflow/tests/order.test.js`, `src/stateguard/test_evidence.py` | **Требует Docker для живой проверки** |
| 9 | Persistent audit ledger | **Production-уровня**, полностью протестирован | `sql/ledger.sql`, `src/stateguard/db.py`, `cli.py` (15+ subcommands) | Нет |
| — | Оркестратор всего цикла | **Реализован, проверен вживую end-to-end, и генерализован** (Z3/Event-B больше не хардкодят order-workflow) | `src/stateguard/cycle.py`, CLI `stateguard run-cycle` | Контент (mappings/Z3-формулы/Event-B-модель) остаётся order-workflow-специфичным — обобщение конструкции ≠ обобщение содержания |
| — | Central control plane | Только OpenAPI-спека + SQL DDL, сервиса нет. **`ci/publish-stateguard-summary.sh` теперь строит валидный CreateRun payload** из ledger и постит его, если сервер сконфигурирован — но не проверено вживую, сервера нет | `control-plane/`, `ci/publish-stateguard-summary.sh` | Сервис не существует; findings/proofs upload и `complete` endpoints не реализованы (осознанно — не строить непроверяемое против несуществующего сервера) |
| — | CI-обвязка | **Все 5 скриптов написаны и проверены** (кроме `project-full-checks.sh`, которому по своей природе нужен Docker) | `ci/project-fast-checks.sh`, `ci/project-full-checks.sh`, `ci/run-database-concurrency-suite.sh`, `ci/run-model-checking.sh`, `ci/publish-stateguard-summary.sh` | `project-fast-checks.sh`/`project-full-checks.sh` — starter-детекторы стека (Node/Python/Java), не универсальны, как и Semgrep-правила |
| — | `stateguard record-test-evidence` | Новый generic CLI primitive, не завязан на order-workflow | `src/stateguard/cli.py`, `src/stateguard/test_evidence.py` | Нет |

## 3. Что уже собрано: сквозной цикл на `examples/order-workflow`

Реализован walking skeleton — `stateguard run-cycle` реально проводит один
существующий, полностью специфицированный пример через весь автономный контур (8 стадий
+ опциональный ИИ), с записью evidence в SQLite ledger и финальным `doctor --strict`
вердиктом. Полная история решений и обоснований — `/Users/alexkot/.claude/plans/eager-nibbling-prism.md`
(локальный план сессии, не в репозитории).

### 3.1. Запуск

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e '.[dev,validation,smt]'
pip install semgrep

stateguard --repo examples/order-workflow run-cycle
stateguard --repo examples/order-workflow doctor --strict
python examples/order-workflow/z3/order_workflow_proofs.py

# Нижняя, model-checking-only часть цикла (используется nightly CI-скриптом):
ci/run-model-checking.sh examples/order-workflow
```

Или короче: `scripts/run-order-workflow-cycle.sh`.

### 3.2. Реальный результат (не предположение — проверено запуском)

| Стадия | Результат |
|---|---|
| validate | чисто |
| scan + review | 6 review units, авто-завершены (демо-упрощение, не замена человеку — помечено в notes) |
| semgrep | реально запущен, нашёл настоящий finding (empty catch в `server/transaction.js:13`) |
| joern | `SKIPPED: joern/joern-parse not installed` |
| apg | 25 узлов, 9 рёбер, mapping-only режим |
| obligations | 5 `PO-*` сгенерировано |
| event-b | `SKIPPED: probcli not installed` |
| z3 | **5/5 доказано** — единственное, что реально закрывает critical/high obligations в этой среде |
| ai-review | `SKIPPED: DEEPSEEK_API_KEY not set` |
| tests | `SKIPPED: docker not installed` |
| doctor (non-strict) | **ok** |
| doctor --strict | fails на 1 findings средней критичности — корректно: реальный finding ждёт триажа человеком, не спрятан |

21/21 unit-тестов проходят (`PYTHONPATH=src python -m pytest -q`).

### 3.3. Новые модули и конвенции

`src/stateguard/{rules,obligations,joern_adapter,probcli_parser,test_evidence,ai_review,cycle}.py`,
`examples/order-workflow/z3/order_workflow_proofs.py`, `schemas/{ai-finding-review,apg}.schema.json`,
`ci/{project-fast-checks,project-full-checks,run-database-concurrency-suite,run-model-checking,publish-stateguard-summary}.sh`.
Каждый Python-модуль — с юнит-тестами на реальных или честно рукописных фикстурах (см.
`tests/test_*.py`).

Две новые лёгкие конвенции для генерализации оркестратора (установлены в этом проходе,
задокументированы здесь, т.к. больше нигде не описаны):

- **Z3**: `<repo_root>/z3/*.py` — каждый скрипт принимает `--json` и печатает массив
  `{key, status, summary, counterexample, tool_version}`. `cycle.py` подбирает все такие
  скрипты автоматически. Референс — `examples/order-workflow/z3/order_workflow_proofs.py`.
- **Event-B**: `specification.event_b_project` в `stateguard.yaml` (поле уже было в
  `schemas/stateguard.schema.json`, теперь читается `config.py`) — путь (может выходить
  за `repo_root` через `../`) к каталогу с `*.mch` и `proof-obligations.yaml` той же
  формы, что `event-b/proof-obligations.yaml`. `run-prob.sh` остаётся общим kit-level
  инструментом, не копируется на проект.

### 3.4. Честные ограничения этого шага

- Оркестратор (`cycle.py`) генерализован механически (Z3/Event-B больше не хардкодят
  order-workflow), но mappings/specification/Z3-формулы/Event-B-модель по контенту
  написаны конкретно под этот один пример — на новом репозитории всё это пишется заново.
- Joern/ProB/Docker/DeepSeek — код написан и юнит-тестирован, но **живая** проверка
  требует внешних инструментов/ключа. Внешние инструменты сознательно не устанавливались
  в этой сессии — это реальный Mac пользователя, не одноразовая песочница; ставить
  JVM-тулинг/Docker Desktop без явного разрешения не стали.
- `ci/publish-stateguard-summary.sh` строит валидный (по `control-plane/openapi.yaml`)
  payload и готов постить его, но сервера нет и никогда не было — эта часть непроверяема
  в принципе до появления сервиса.
- SonarQube и нативные линтеры (кроме Semgrep) сознательно не включены в этот шаг (см.
  раздел 5); `ci/project-fast-checks.sh`/`project-full-checks.sh` — starter-детекторы
  стека, а не универсальное решение, тем же принципом, что и Semgrep-правила.

## 4. Дальнейшие шаги (по приоритету)

1. **Подключить DeepSeek живым ключом** — код готов (`stateguard ai-review`), нужен
   `DEEPSEEK_API_KEY`. Самый дешёвый следующий шаг.
2. **Установить Joern/probcli/Docker** и сверить провизорные части адаптеров
   (`_enrich_line_range` в `joern_adapter.py`, паттерны в `probcli_parser.py`) с реальным
   выводом инструментов. Осознанно не сделано автоматически в этой сессии — решение
   пользователя, где это ставить (dev-машина уже требует места на диске/системных
   изменений, CI self-hosted runner — более естественное место).
3. **Обобщить на второй репозиторий/пример** — докажет, что `cycle.py`/`obligations.py`/
   `joern_adapter.py` не переобучены на order-workflow. Z3-скрипт и Event-B-модель для
   нового примера придётся написать заново — это ожидаемо, не автоматизируется.
4. **Native analyzers** (ESLint/Ruff/SpotBugs) — нулевая реализация; `ci/project-fast-checks.sh`
   уже умеет их подхватить, если они появятся в проекте.
5. **Control-plane сервис** — `ci/publish-stateguard-summary.sh` готов постить, реализовать
   findings/proofs/complete endpoints из `control-plane/openapi.yaml`, когда появится
   реальный сервер для проверки.

## 5. Явно вне скоупа сейчас

- **SonarQube** — инфраструктура готова (`infra/`), но подключать ради одного репозитория
  избыточно; интеграция и так однонаправленная по архитектуре (`docs/02.4`).
- **Central control plane** — не нужен до 20-30 репозиториев (`docs/02.3`).
- **Формальная модель для каждой CRUD-таблицы** — явно запрещено `docs/17.3`
  ("не делать в первой версии").
- **Полный перевод production кода в SMT** — то же самое, явный non-goal.
