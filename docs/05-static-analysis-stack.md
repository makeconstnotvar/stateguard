# 05. Стек статического анализа

## 5.1. Основной принцип

StateGuard не выбирает один «лучший анализатор». Он строит конвейер, в котором каждый инструмент
поставляет факты строго определённого класса. Это позволяет заменять компоненты и не путать
эвристику с доказательством.

```text
compiler/native checks  → локальная семантика языка
Semgrep CE              → дешёвые корпоративные шаблоны и локальный taint
Sonar analyzers         → стандартные дефекты, coverage, duplication, quality history
Joern                   → межфайловый CPG, control/data-flow и graph slices
SQL/catalog adapters    → фактическая реляционная семантика
StateGuard              → нормализация, proof obligations, evidence lifecycle
```

Инструмент не получает статус `proved-static` только потому, что завершился с кодом 0. Для каждого
правила задаются:

- тип проверяемого свойства;
- supported languages/frameworks;
- область межпроцедурного анализа;
- известные источники false negative;
- класс результата: finding, hotspot, evidence или proof;
- обязательные дополнительные проверки.

## 5.2. Native analyzers

Первым слоем остаются штатные инструменты языка и сборки:

- Java/Kotlin: компилятор, Error Prone, SpotBugs, NullAway по политике проекта;
- C#: Roslyn analyzers, nullable reference types, build warnings as errors;
- Go: `go vet`, staticcheck, race detector в тестовом контуре;
- Python: Ruff/Pylint, mypy/pyright при наличии типовой дисциплины;
- JavaScript/TypeScript: ESLint и type checker, если проект использует TypeScript;
- Rust: compiler + Clippy;
- SQL: dialect parser, migration checker и реальная БД.

StateGuard импортирует их findings через SARIF, JSON или адаптер. Эти инструменты лучше собственного
универсального анализатора понимают семантику языка. Дублировать их внутри StateGuard бессмысленно.

## 5.3. Semgrep CE

Semgrep CE выполняется на каждом pull request и при локальном запуске. Его роль:

- запрет известных архитектурных обходов;
- поиск опасных API и шаблонов;
- локальные taint-пути;
- контроль границ транзакций;
- обнаружение «сырого» внешнего ввода;
- дешёвые правила миграций и SQL-строительства;
- быстрый feedback до тяжёлого графового анализа.

Правила хранятся в отдельном внутреннем репозитории:

```text
stateguard-rules/
├── policy-version.yaml
├── common/
├── javascript/
├── java/
├── dotnet/
├── python/
├── go/
├── sql/
├── frameworks/
│   ├── express/
│   ├── spring/
│   ├── aspnet/
│   └── django/
└── tests/
```

Каждый rule обязан иметь:

```yaml
metadata:
  owner: platform-correctness
  category: concurrency
  stateguard_surface: transaction-to-effect
  confidence: medium
  evidence_class: finding
  specification_required: false
  introduced: 2026-07-20
```

Для high/critical правила обязательны положительные и отрицательные fixtures. Изменение правила
проходит review так же, как production code.

Semgrep CE не считается достаточным для свойства, требующего полного межфайлового пути. Его
отрицательный результат означает только «правило не нашло совпадение в своей области».

## 5.4. Sonar analyzers

SonarQube сканирует main branch и, при наличии соответствующей редакции, pull requests. Он отвечает
за стандартный baseline:

- дефекты и security hotspots встроенных analyzers;
- coverage;
- duplication;
- maintainability;
- quality gate нового кода;
- историю и ownership.

StateGuard импортирует часть Sonar findings обратно только если это необходимо для единого release
gate. В простом варианте используются два независимых условия:

```text
Sonar quality gate == PASSED
AND
StateGuard doctor --strict == PASSED
```

Это лучше, чем пытаться свести все понятия в одну шкалу Sonar severity.

## 5.5. Joern

Joern запускается:

- ночью на main branch;
- перед релизом;
- при изменении critical bounded context;
- вручную для расследования сложного finding.

Он строит Code Property Graph и поставляет:

- symbols;
- calls;
- CFG;
- data-flow;
- candidate sources/sinks/sanitizers;
- методы, типы и файлы;
- графовые slices для агента.

Сырой CPG не является API StateGuard. Адаптер преобразует его в стабильный Application Property
Graph. Это позволяет обновлять Joern или заменять frontend, не мигрируя весь ledger.

## 5.6. SQL и schema analyzers

SQL анализируется несколькими способами:

1. literal SQL разбирается dialect parser;
2. query builder/ORM извлекается из framework adapter;
3. migrations применяются к disposable database;
4. PostgreSQL catalog экспортируется после всех migrations;
5. критичные запросы выполняются на generated fixtures;
6. план запросов проверяется отдельно как performance evidence, а не correctness proof.

Dynamic SQL классифицируется:

- `static`: строка известна полностью;
- `parameterized`: структура известна, значения параметры;
- `bounded-dynamic`: части выбираются из закрытого allowlist;
- `unbounded-dynamic`: структура строится из runtime values.

`unbounded-dynamic` SQL в критичном срезе автоматически создаёт evidence gap, даже если scanner не
нашёл injection.

## 5.7. Нормализация findings

Все анализаторы приводятся к общей модели:

```text
external_key
source_tool
rule_id
severity
confidence
category
location + artifact SHA-256
property/invariant/transition reference
counterexample
impact
root cause
remediation
verification
```

При импорте severity не копируется слепо. Используется policy map:

```yaml
severity_mapping:
  semgrep:
    ERROR: high
    WARNING: medium
    INFO: info
  sonar:
    BLOCKER: critical
    CRITICAL: high
    MAJOR: medium
```

Отдельная policy может повысить severity для paths `payments/**`, `authorization/**`, migrations и
PII projections.

## 5.8. Дедупликация

Findings считаются одинаковыми по стабильному fingerprint:

```text
hash(tool family, normalized rule, normalized symbol, semantic location, message class)
```

Номер строки сам по себе не используется: вставка комментария не должна создавать новый дефект.
Предпочтительны symbol ID и AST node fingerprint. При отсутствии семантического ID используется
`path + surrounding token hash`.

## 5.9. Политика запуска

| Контур | Инструменты | Цель | Бюджет |
|---|---|---|---|
| локально | native + Semgrep selected rules | ранний feedback | минуты |
| PR fast | native + Semgrep + unit tests | блокировать очевидное | до 10–15 минут |
| PR critical | + targeted DB/APG | критичный срез | до 30 минут |
| main | + Sonar + full integration | организационный baseline | десятки минут |
| nightly | + Joern + model/SMT + concurrency | глубокий анализ | часы допустимы |
| release | полный strict profile | release evidence | контролируемый gate |

Время является инженерным бюджетом. Любой новый анализатор сначала измеряется на 5–10 типичных
репозиториях; правило, замедлившее PR без высокого сигнала, переносится в nightly.

## 5.10. Критерии выбора нового анализатора

Новый инструмент добавляется, если он:

- работает локально и имеет приемлемую лицензию;
- предоставляет машинный отчёт;
- поддерживает фиксированную версию;
- документирует область анализа;
- имеет воспроизводимые fixtures;
- даёт уникальный сигнал, не дублирующий существующий слой;
- не требует передачи корпоративного кода внешнему сервису;
- может запускаться без сети.

Иначе он увеличивает поверхность сопровождения без увеличения доказательной силы.
