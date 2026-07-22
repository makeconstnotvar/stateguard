# Мастер-план реализации: автономный анализатор репозиториев

Статус на 2026-07-22 (третий проход: native analyzers, фикс `sarif.py`, и второй
независимый пример `examples/shipment-tracking`, доказывающий генерализацию за пределы
order-workflow). Этот документ — единая точка входа: что должен делать автономный
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
| 2b | Нативные анализаторы (Ruff, ESLint) | **Реализовано и проверено вживую**: Ruff через нативный `--output-format sarif` (реально нашёл dead import в самом ките), ESLint через `@microsoft/eslint-formatter-sarif` (реально прогнан на обоих примерах) | `src/stateguard/native_analyzers.py`, `tests/test_native_analyzers.py` | SpotBugs (Java)/Roslyn (C#)/staticcheck (Go)/Clippy (Rust) не реализованы — нет цели для проверки в этом ките |
| 2b′ | Попутный фикс: `sarif.py` абсолютные `file://` URI | **Исправлено** — Ruff (в отличие от Semgrep) всегда пишет абсолютный `file://` URI независимо от cwd; `_uri_to_path` теперь относительнизирует его против `ledger.repo_root` | `src/stateguard/sarif.py`, `tests/test_sarif.py` | Нет |
| 2c | SonarQube | Инфраструктура рабочая, интеграция намеренно однонаправленная | `infra/docker-compose.sonarqube.yml`, `infra/scripts/*.sh` | Не нужен для одного репозитория; актуален при организационном масштабе |
| 3 | Joern CPG | **Живой `joern-parse`+`joern` прогон на ДВУХ примерах, реальный CPG экспорт** — поля вывода сверены построчно, `_enrich_line_range` не потребовал изменений (см. 3.6) | `joern/export_stateguard.sc`, `scripts/run-joern.sh` | На этой конкретной Homebrew-установке `astgen` резолвится неверно без `ASTGEN_BIN` в окружении (даёт пустой CPG при exit 0) — баг окружения, не кита; `cycle.py`'s `joern`-стадия теперь детектирует и репортит это как `failed`, а не ложный `ok` |
| 4 | StateGuard APG | **Адаптер Joern→APG написан и проверен на ДВУХ независимых примерах** (mapping-only + enriched режимы, round-trip тест) + типизированная JSON-schema для node/edge подключена. **Три найденных пробела генерализации (см. 3.5) исправлены и переверифицированы адверсариальным review**: (1) handler-detection теперь config-driven — `framework_adapters[].rules.decoders`, зеркалящий `transaction_starts`, вместо хардкода `decode*`-префикса; (2) `kind: query`-узел, на который ссылаются и command, и invariant, детерминированно получает имя от command (секция `commands` обрабатывается раньше `invariants`); (3) invariant-локация любого enforcement-kind (`constraint`/`symbol`/`query`/`index`/`job`/`ui-action`/`event-b-element`), не только `constraint`, теперь получает `ENFORCES`-ребро — но НЕ структурные kind (`table`/`column`), это удержано отдельным тестом после того, как review нашёл, что первая версия фикса была слишком широкой | `src/stateguard/joern_adapter.py`, `schemas/apg.schema.json`, `tests/test_joern_adapter.py` | Нет открытых пробелов генерализации — оба примера дают ожидаемые APG вживую (`stateguard run-cycle`, проверено построчным SQL-запросом к `apg_edges`) |
| 5 | Proof obligations | **Генератор из specification.yaml подтверждён на двух независимых примерах** (`PO-<invariant>-BY-<command>`) — 0 изменений кода потребовалось для второго примера | `src/stateguard/obligations.py`, `tests/test_obligations.py` | Нет — генерализация подтверждена, не предположение |
| 6a | Event-B/ProB | **Живой `probcli` 1.15.1-final прогон на ОБЕИХ моделях — обе PROVED** (см. 3.6); **обе формы `event_b_project` подтверждены** — order-workflow указывает на общий kit-level каталог (`../../event-b`), shipment-tracking — на собственный (`event-b`, первый такой пример) | `event-b/OrderWorkflow.mch`, `examples/shipment-tracking/event-b/ShipmentTracking.mch`, `src/stateguard/probcli_parser.py`, `src/stateguard/cycle.py` (`_stage_event_b`) | Нет — `probcli_parser.py`'s фразировка была неверна по трём пунктам (исправлено), `ShipmentTracking.mch` имел реальный синтаксический баг (`seq` — зарезервированное слово, исправлено переименованием в `seqn`), негативный контроль пройден по-настоящему |
| 6b | Z3 | **Доказательства выведены из specification.yaml и реально проходят на ДВУХ примерах** (5/5 + 6/6 PROVED, включая негативные контроли; адверсариальный review нашёл, что 2 из исходных доказательств shipment-tracking были не нагружены — исправлено, см. 3.5) | `examples/order-workflow/z3/order_workflow_proofs.py`, `examples/shipment-tracking/z3/shipment_tracking_proofs.py` | Формулы для каждого нового репозитория пишутся заново — ожидаемо, Z3 работает с конкретными guard/invariant, не обобщается |
| 6c | PostgreSQL enforcement | Каталожный snapshot есть, отдельно не используется в цикле | `postgres/catalog_snapshot.sql` | Реальное enforcement-доказательство для order-workflow идёт через стадию 8 (интеграционный тест), не через отдельный catalog-шаг — осознанно не дублировали |
| 7 | Локальный ИИ (не входит в автономное ядро) | **Реализован полностью**: DeepSeek API, JSON-schema валидация ответа, prompt-injection защита (4 категории источников), graceful skip без ключа | `src/stateguard/ai_review.py`, `schemas/ai-finding-review.schema.json`, `tests/test_ai_review.py` | **Ждём `DEEPSEEK_API_KEY`** от пользователя — код не проверен живым вызовом, только через мок |
| 8 | Интеграционные/конкурентные тесты | Тесты в order-workflow реальные (testcontainers + race condition), но Docker не установлен в этой среде | `examples/order-workflow/tests/order.test.js`, `src/stateguard/test_evidence.py` | **Требует Docker для живой проверки** |
| 9 | Persistent audit ledger | **Production-уровня**, полностью протестирован | `sql/ledger.sql`, `src/stateguard/db.py`, `cli.py` (15+ subcommands) | Нет |
| — | Оркестратор всего цикла | **Реализован, проверен вживую end-to-end на ДВУХ независимых примерах** | `src/stateguard/cycle.py`, CLI `stateguard run-cycle` | Контент (mappings/Z3-формулы/Event-B-модель) остаётся example-специфичным — обобщение конструкции подтверждено, обобщение содержания и не предполагалось |
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

`src/stateguard/{rules,obligations,joern_adapter,probcli_parser,test_evidence,ai_review,cycle,native_analyzers}.py`,
`examples/order-workflow/z3/order_workflow_proofs.py`, `schemas/{ai-finding-review,apg}.schema.json`,
`ci/{project-fast-checks,project-full-checks,run-database-concurrency-suite,run-model-checking,publish-stateguard-summary}.sh`,
плюс точечный фикс `src/stateguard/sarif.py`'s `_uri_to_path` (относительнизация абсолютных
`file://` URI — понадобился Ruff, у которого, в отличие от Semgrep, нет режима, где URI
получаются repo-relative от cwd). Каждый Python-модуль — с юнит-тестами на реальных или
честно рукописных фикстурах (см. `tests/test_*.py`); `native_analyzers.py` — на настоящем
Ruff (реальный dead import найден в `src/stateguard/findings.py`) плюс на stub-бинарнике
для ESLint в юнит-тестах; сама связка реального ESLint 10 + `@microsoft/eslint-formatter-sarif`
проверена отдельно вручную и живым прогоном `run-cycle` на обоих примерах — реальные
пакеты, не моки.

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
- **Joern и ProB — с тех пор установлены пользователем и живая проверка пройдена на
  обоих примерах** (см. раздел 3.6): `joern_adapter.py`'s поля оказались верны без
  изменений, `probcli_parser.py` имел реальный баг (чинил вживую, найден только сейчас),
  и в `ShipmentTracking.mch` нашёлся реальный баг модели (`seq` — зарезервированное слово
  classical B). Это больше не гипотетический пробел.
- **Docker** — по-прежнему не установлен (сознательно, реальный Mac пользователя, не
  одноразовая песочница); интеграционные/конкурентные тесты (стадия 8) остаются
  непроверенными живьём.
- **DeepSeek** — ключ теперь установлен пользователем через `.env` (см. `cli.py`'s
  `_load_dotenv`), но реальный вызов падает с SSL-ошибкой локального Python
  (`CERTIFICATE_VERIFY_FAILED` — `/Library/Frameworks/Python.framework`'s интерпретатор не
  подтягивает системный trust store по умолчанию). Это не баг `ai_review.py` — код и HTTP-
  путь к DeepSeek правильные, просто у Python.org-сборки нет CA-бандла, пока не
  выполнен `Install Certificates.command`. Фикс — на стороне пользователя.
- `ci/publish-stateguard-summary.sh` строит валидный (по `control-plane/openapi.yaml`)
  payload и готов постить его, но сервера нет и никогда не было — эта часть непроверяема
  в принципе до появления сервиса.
- SonarQube и нативные линтеры (кроме Semgrep) сознательно не включены в этот шаг (см.
  раздел 5); `ci/project-fast-checks.sh`/`project-full-checks.sh` — starter-детекторы
  стека, а не универсальное решение, тем же принципом, что и Semgrep-правила.

### 3.5. Второй пример: `examples/shipment-tracking` — доказательство генерализации

Построен намеренно ПО-ДРУГОМУ, чем order-workflow (домен и конкретные приёмы выбраны и
обсуждены отдельным Workflow-процессом — 4 независимых предложения, затем судья с доступом
к реальному коду выбрал и уточнил победителя): carrier-webhook трекер доставки с:

- инвариантом на *внешне заданный* вход (`sequence_no` от перевозчика, строго
  возрастающий) — не на собственный счётчик системы, как `version` в order-workflow;
- идемпотентным replay (`Implies(already_processed, no-op)`) — форма Z3-доказательства,
  которой не было в order-workflow;
- pessimistic locking (`SELECT ... FOR UPDATE`, `server/locking.js`'s `withRowLock`) вместо
  optimistic version-guard — блокирует конкурентов, а не откатывает и повторяет;
- append-only логом checkpoint'ов вместо мутируемой строки;
- собственным (не общим) `event_b_project`.

#### Результат: генерализация подтверждена, найден намеренный пробел (с тех пор исправлен) + адверсариальный review нашёл 13 других (все исправлены)

**Что подтвердилось без единого изменения кода:**
- `src/stateguard/obligations.py` сгенерировал ровно ожидаемые 5 `PO-*` ключей из нового
  specification.yaml;
- `src/stateguard/cycle.py`'s `z3/*.py`-конвенция подобрала новый скрипт автоматически —
  5/5 доказано, плюс 2 негативных контроля (намеренно сломанные guard'ы) корректно
  провалились, подтверждая что доказательства не vacuous;
- `event_b_project`, указывающий на собственный (не общий) каталог, разрешился корректно;
- `native_analyzers`/ESLint, Semgrep, весь `run-cycle` прошли по новому примеру так же
  честно, как по первому (1 настоящий finding — тот же паттерн empty-catch, что и в
  order-workflow, `doctor` non-strict зелёный, `--strict` ждёт триажа).

**Найденный и подтверждённый пробел — теперь исправлен** (изначально намеренно не
закрыт переименованием, чтобы сначала зафиксировать реальный баг — см. историю в
`examples/shipment-tracking/README.md`): `src/stateguard/joern_adapter.py`'s определение
handler'а — `not location["selector"].lower().startswith("decode")` — хардкодило один
naming convention (`decode*` из order-workflow), а не читало роль из `mappings.yaml`, в
отличие от `transaction_starts`, который config-driven. Входной parser
`parseCarrierWebhook` (та же роль, что `decodeSubmitOrder`, но другое имя), будучи
запущен через `run-cycle`, **реально** получал ошибочные `WRITES`-рёбра на
`public.shipments`/`public.checkpoints` и `PART_OF_TRANSACTION`-ребро — проверено прямым
SQL-запросом к `apg_edges` в ledger, не предположение.

Исправление: новая функция `_decoder_selectors()` (зеркалит
`_transaction_wrapper_selectors()`) читает `framework_adapters[].rules.decoders` из
`mappings.yaml`. `parseCarrierWebhook` теперь явно объявлена в этом списке в
`examples/shipment-tracking/mappings.yaml` — без переименования функции, что и
доказывает: фикс закрывает пробел конфигурацией, а не навязыванием naming convention
целевому коду. Живо перепроверено: после фикса `parseCarrierWebhook` не получает ни
одного ребра в сгенерированном APG (`stateguard run-cycle` на shipment-tracking).

**Честное ограничение**: Event-B-модель (`ShipmentTracking.mch`) и тесты
(`tests/shipment.test.js`) написаны и проверены статически/синтаксически, но не
верифицированы вживую (нет `probcli`/Docker в этой среде) — тот же честный лимит, что и у
order-workflow.

#### Адверсариальный review (5 направлений через Workflow) нашёл 15 реальных проблем — 12 исправлены, 3 осознанно оставлены как задокументированные ограничения

Каждая находка была независимо переверифицирована (второй проход агентов, читающих файлы
заново, а не доверяющих тексту первого review); часть — эмпирически, мутацией кода с
реальным `z3-solver`. Итог: **все 15 находок подтверждены, ни одна не была ложной**.
Исправлено 12:

- **SQL/конкурентность**: `createShipment` не обрабатывал гонку на `order_id` (реальный
  Postgres `unique_violation` вместо смоделированного `duplicate_shipment`) — добавлена
  обработка `23505`.
- **Z3 (существенно)**: обнаружено, что guard `code in allowed_next(status)` был закодирован,
  но НИ ОДНО из 5 доказательств от него не зависело (проверено мутацией — удаление guard'а
  не ломало ни одного PROVED). Добавлен новый инвариант `INV-SHIP-004` с доказательством,
  которое действительно от него зависит (перепроверено: теперь ломается). Отдельно,
  `INV-SHIP-001`'s доказательство проверяло `>=` вместо заявленного строгого `>` — усилено.
  **Это была самая существенная находка**: два из шести доказательств реально ничего не
  доказывали о том, что заявляли.
- **mappings.yaml**: em-dash вместо двоеточия в одном test-селекторе (молча ронял evidence —
  `test_evidence.py` матчит по точной строке); DB-trigger тест не был привязан как
  `kind: test` к `INV-SHIP-001` (асимметрично со схемой order-workflow); `kind: query` на
  `.js`-файл коллизировал node ID с другими query-локациями.
- **Тесты**: порядок `t.after`-хуков мог убить контейнер до закрытия пула (риск
  необработанного `error` на EventEmitter); тест конкурентности не гарантировал настоящую
  SQL-гонку (pool мог тривиально сериализовать вызовы) — добавлен отдельный тест, явно
  держащий `FOR UPDATE`-лок вторым client'ом, что доказывает блокировку напрямую; добавлено
  покрытие `wrong_state`/`invalid_transition`/`duplicate_shipment`/конкурентного create.
- **Event-B**: `event_shipment`/`event_sequence` были keyed глобально по `EVENT`, а не по
  паре `(SHIPMENT, EVENT)` — второй shipment мог молча «украсть» событие первого, и
  заявленный INVARIANT этого не ловил (probcli всё равно не установлен, поэтому вживую это
  не было бы поймано). Исправлено: `event_sequence` теперь функция от пары, зеркалируя
  `UNIQUE(shipment_id, provider_event_id)`.

**3 находки изначально осознанно оставлены незакрытыми** (задокументированы, не
спрятаны) — **2 из 3 с тех пор исправлены** (см. ниже), 1 остаётся открытой:
- lossy `Number()` на `bigint`-колонках (`record-checkpoint.js`) выше 2^53 — **остаётся
  открытой**: реально недостижимо сегодня (единственный писатель, `parseCarrierWebhook`,
  уже валидирует `Number.isSafeInteger`), но нет defense-in-depth проверки в самом
  `record-checkpoint.js`;
- 6-й, недокументированный outcome-branch (`not_found`) в `record-checkpoint.js`,
  которого нет в specification.yaml's списке из 5 outcomes — **остаётся открытой**:
  поведение разумно, просто не описано в спеке;
- ~~два системных пробела в `joern_adapter.py`~~ — **исправлены**: `kind: query`'s
  external ID оставлен path-only намеренно (один `.sql`-файл == один узел), но секция
  `commands` теперь обрабатывается раньше `invariants`, так что при коллизии на одном
  файле command's короткое имя детерминированно побеждает по display name; и
  invariant-секция теперь генерирует `ENFORCES`-ребро для любой enforcement-kind локации
  (`constraint`/`symbol`/`query`/`index`/`job`/`ui-action`/`event-b-element`), не только
  `kind: constraint` — `INV-SHIP-003`/`INV-SHIP-004` и order-workflow's
  `INV-ORDER-002`/`003` больше не остаются узлами с нулевой входящей степенью. Structural
  kind (`table`/`column`) намеренно исключены из ENFORCES — адверсариальный review
  второго раунда (см. ниже) поймал, что первая версия фикса (`kind != "test"`) была
  слишком широкой и давала `column:public.orders.version -ENFORCES-> INV-ORDER-003`,
  семантически неверное ребро.

#### Второй раунд адверсариального review (после фикса joern_adapter.py) нашёл 2 реальные проблемы — обе исправлены

Отдельный агент, независимо перечитавший диф (не доверяя описанию первого прохода),
запустил тесты, сделал мутационное тестирование каждого из трёх фиксов по отдельности
(временно откатывал каждый и убеждался, что тест ловит регресс) и проверил
`schemas/mappings.schema.json` на совместимость с новым `decoders`-ключом. Нашёл:
1. **`ENFORCES`-условие `kind != "test"` было живой семантической ошибкой**, не только
   теоретическим риском — реально воспроизведено на order-workflow's INV-ORDER-003
   (`kind: column`). Исправлено сужением до явного списка `_ENFORCING_KINDS`.
2. **Тест на декодер проходил vacuously** против старой (до фикса) версии кода:
   `test_declared_decoder_is_excluded_from_writes_via_config_not_naming` не различал
   "исключён по конфигурации" от "исключён по имени", потому что `decodeSubmitOrder`
   удовлетворяет обоим механизмам. Исправлено: тест теперь дополнительно удаляет ТОЛЬКО
   `decoders:`-декларацию (не трогая имя селектора) и подтверждает, что `WRITES`-ребро
   при этом появляется — то есть именно декларация причинно ответственна за исключение.

Обе находки исправлены, добавлен регрессионный тест на структурные kind (`column`), полный
`pytest` (33/33) и `stateguard run-cycle` на обоих примерах перепроверены после фикса.

### 3.6. Живая проверка Joern и ProB — оба провизорных места оказались реальными, оба исправлены

Пользователь установил `joern` (4.0.580, Homebrew) и `probcli` (1.15.1-final, вручную с
`prob.hhu.de`) на свою машину. Через Workflow (2 параллельных агента — независимые файлы,
без общего состояния — затем барьер полной переверификации, затем адверсариальный review
каждого диффа) сверили реальный вывод обоих инструментов против кода, который до этого
момента ни разу не видел живого вывода ни того, ни другого.

**Joern → `joern_adapter.py`'s `_enrich_line_range`**: предположения о полях (`filename`,
`name`, `lineNumber`, `lineNumberEnd`) оказались **верны без единого изменения кода** —
проверено на реальном `cpg.method.toJsonPretty` выводе для обоих примеров, line ranges
сверены построчно с реальным исходным кодом (`submitOrder` → строки 3–39, и т.д., без
смещения). Комментарий "provisional" заменён на то, что реально проверено. Добавлен тест
на реальном захваченном фрагменте `methods.json` (не синтетическом).

Отдельно найден **реальный, воспроизводимый баг окружения** (не код кита): на этой машине
`joern-parse`/`joern` молча резолвят `astgen`-бинарник не туда (relative path от JVM's cwd
вместо `frontends/jssrc2cpg/bin/astgen/astgen-macos-arm`), выходят с кодом 0, но CPG
получается **пустым** (0 methods/files/calls) — экспорт технически "успешен", но бесполезен.
Обход: `ASTGEN_BIN=<путь-к-бинарнику>` в окружении перед вызовом `scripts/run-joern.sh`
(джерновская `AstGenRunner.binFromEnvVar()` проверяет эту переменную первой). Это чисто
Homebrew-layout-специфичная проблема самого Joern, не относится к `joern_adapter.py`.

**Из этого нашёлся отдельный, реальный пробел в `cycle.py`** — стадия `joern` доверяла
только exit-коду `run-joern.sh`, а не тому, реально ли что-то обогатилось. Из-за
ASTGEN_BIN-бага стадия молча репортила бы `"joern": "ok"` при пустом экспорте. Исправлено:
`_stage_joern_and_apg` теперь считает узлы с `sourceTool="joern-apg-adapter"` и репортит
`"joern": "failed"`, если попытка обогащения была (`joern-parse`/`joern` есть и вернули 0),
в mapping'е есть хотя бы одна `kind: symbol`-локация, но ни одна не обогатилась — то есть
именно тот сценарий, который реально произошёл на этой машине без `ASTGEN_BIN`. Покрыто
тестами (`tests/test_cycle.py`, 3 теста: пустой экспорт → failed, реальные данные → ok,
инструмент не установлен → skipped).

**ProB → `probcli_parser.py`'s `parse_prob_output`**: здесь предположения о фразировке
**оказались неверны по трём независимым пунктам** — реальный успешный вывод probcli
1.15.1-final не совпадал ни с одним из паттернов успеха/провала, ни с regex на states/
version. Fail-safe сработал (падало в `inconclusive`, никогда не в ложный `proved`), но
результат был бесполезен: **любой реальный вызов probcli классифицировался бы как
inconclusive, независимо от того, доказано что-то на самом деле или нет** — это было бы
незамеченным блокером для `doctor --strict`'s Event-B-путь на любом реальном прогоне.
Исправлено: добавлены реальные фразы ("no counter example found" тремя словами без дефиса,
"states analysed: N", "VERSION x.y.z"), снятие ANSI-escape-последовательностей перед
матчингом, задокументировано, что `"! *** error occurred ***"` уходит в stderr, а не
stdout (`run-prob.sh`'s `tee` и `cycle.py`'s чтение лога его не видят).

**Негативный контроль пройден по-настоящему**: скопирована `OrderWorkflow.mch`, инвариант
намеренно ослаблен (`payment_confirmed` → `payment_rejected`), реальный probcli нашёл
настоящий 7-шаговый контрпример, парсер корректно вернул `status="failed"` с полной
трассой. Адверсариальный review переоткрыл этот же негативный контроль независимо и
подтвердил.

**Побочно найден и исправлен реальный баг модели**: `examples/shipment-tracking/event-b/
ShipmentTracking.mch` **не парсился реальным probcli вообще** — `seq` использовался как
имя параметра операции, а это зарезервированное слово classical B (конструктор
последовательностей). Модель была написана и провалидирована только синтаксически в
прошлой сессии (см. раздел 3.5's "честное ограничение" — теперь снято), живого прогона
не было. Исправлено переименованием `seq` → `seqn` (4 места, `last_sequence`/
`event_sequence` не затронуты — они лишь содержат подстроку `seq`). После фикса модель
проходит чисто: **73 441 состояние, контрпримеров нет**, ~3.5 минуты на реальной машине.

**Итоговый живой прогон обоих примеров** (`ASTGEN_BIN` установлена, `pytest` 42/42):

| Стадия | order-workflow | shipment-tracking |
|---|---|---|
| joern | ok | ok |
| apg | enriched mode, 25 nodes/15 edges | enriched mode, 24 nodes/18 edges |
| event-b | **OrderWorkflow.mch: proved** | **ShipmentTracking.mch: proved** |
| z3 | 5/5 proved | 6/6 proved |

Попутно: `*.prob`/`prob-run.log` (артефакты компиляции probcli рядом с `.mch`) добавлены
в `.gitignore` — раньше не были покрыты и могли случайно попасть в коммит.

**Что осталось непроверенным живьём**: Docker (тесты, стадия 8) и DeepSeek (ключ
установлен, но локальный Python блокирует SSL — см. 3.4).

## 4. Дальнейшие шаги (по приоритету)

1. **Починить SSL для DeepSeek** — ключ уже установлен через `.env`, но
   `/Library/Frameworks/Python.framework`'s интерпретатор не имеет CA-бандла
   (`CERTIFICATE_VERIFY_FAILED`). Разовая команда на стороне пользователя
   (`Install Certificates.command`, лежит рядом с самим Python.framework для версии
   3.14) — не код-фикс. Самый дешёвый следующий шаг.
2. **Установить Docker** и прогнать стадию 8 (интеграционные/конкурентные тесты,
   testcontainers + реальный postgres:17) на обоих примерах — единственная оставшаяся
   непроверенная живьём стадия автономного ядра. Осознанно не сделано автоматически —
   решение пользователя, ставить ли Docker Desktop на реальную машину.
3. **Third пример на другом стеке** (не Node.js/Postgres) — доказал бы, что joern-адаптер
   и APG-конвенции не завязаны на JS/SQL специфично. Оба текущих примера — Node+Postgres.
4. **Control-plane сервис** — `ci/publish-stateguard-summary.sh` готов постить, реализовать
   findings/proofs/complete endpoints из `control-plane/openapi.yaml`, когда появится
   реальный сервер для проверки.
5. **SpotBugs/Roslyn/staticcheck/Clippy** — `native_analyzers.py`'s архитектура (SARIF-based)
   расширяется на них тривиально, но нет цели (Java/C#/Go/Rust кода) в ките для проверки.

**Закрыто с прошлой ревизии этого документа**: Joern и probcli установлены и живо
верифицированы на обоих примерах, включая реальный баг в `probcli_parser.py` и реальный
баг в `ShipmentTracking.mch` — оба исправлены (см. 3.6). `.env`-поддержка добавлена в
`cli.py` (`_load_dotenv`) по просьбе пользователя.

## 5. Явно вне скоупа сейчас

- **SonarQube** — инфраструктура готова (`infra/`), но подключать ради одного репозитория
  избыточно; интеграция и так однонаправленная по архитектуре (`docs/02.4`).
- **Central control plane** — не нужен до 20-30 репозиториев (`docs/02.3`).
- **Формальная модель для каждой CRUD-таблицы** — явно запрещено `docs/17.3`
  ("не делать в первой версии").
- **Полный перевод production кода в SMT** — то же самое, явный non-goal.
