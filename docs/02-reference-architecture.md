# 02. Референсная архитектура

## 2.1. Логические контуры

```text
┌──────────────────────────────────────────────────────────────────┐
│ Specification plane                                              │
│ YAML specification · mappings · Event-B · assumptions · waivers │
└───────────────────────────────┬──────────────────────────────────┘
                                │
┌───────────────────────────────▼──────────────────────────────────┐
│ Extraction plane                                                 │
│ manifest · native analyzers · Semgrep · Sonar · Joern · SQL AST │
│ PostgreSQL catalog · OpenAPI/GraphQL · migration graph           │
└───────────────────────────────┬──────────────────────────────────┘
                                │
┌───────────────────────────────▼──────────────────────────────────┐
│ Normalization plane                                              │
│ Application Property Graph + normalized findings + source hashes │
└───────────────────────────────┬──────────────────────────────────┘
                                │
┌───────────────────────────────▼──────────────────────────────────┐
│ Verification plane                                               │
│ graph obligations · Rodin/ProB · Z3 · PostgreSQL · tests          │
└───────────────────────────────┬──────────────────────────────────┘
                                │
┌───────────────────────────────▼──────────────────────────────────┐
│ Review plane                                                     │
│ local AI slices · human decisions · remediation batches          │
└───────────────────────────────┬──────────────────────────────────┘
                                │
┌───────────────────────────────▼──────────────────────────────────┐
│ Evidence plane                                                   │
│ local SQLite ledger · central PostgreSQL · SARIF · reports        │
└──────────────────────────────────────────────────────────────────┘
```

## 2.2. Репозиторный агент

В каждом репозитории существует тонкий local agent/CLI:

- читает `.stateguard/stateguard.yaml`;
- строит manifest;
- запускает разрешённые analyzers;
- нормализует результаты;
- создаёт proof obligations;
- хранит локальный ledger;
- отдаёт summary центральному control plane;
- выполняет release gate.

Исходный код не публикуется в control plane. По умолчанию передаются:

- repository ID и commit;
- artifact hashes;
- paths и line ranges;
- finding metadata;
- proof status;
- tool/ruleset versions;
- evidence hashes;
- короткий approved excerpt при необходимости.

## 2.3. Центральный control plane

После 20–30 репозиториев SQLite-файлы недостаточны для организационного управления. Центральный
StateGuard service использует PostgreSQL и предоставляет:

- inventory репозиториев;
- policy/ruleset versions;
- proof coverage;
- stale evidence;
- risk acceptance workflow;
- cross-project findings;
- remediation batches;
- ownership и SLA;
- API для dashboards и release systems.

Он не обязан хранить CPG или исходники. CPG остаётся на выделенных анализаторах и удаляется по
retention policy.

## 2.4. SonarQube

SonarQube разворачивается отдельно от StateGuard control plane. Причины:

- жизненный цикл Sonar обновляется независимо;
- Sonar хранит собственные индексы и БД;
- Sonar external issue state не синхронизируется автоматически назад;
- proof obligations требуют другой модели данных;
- Sonar нельзя превращать в неофициальную graph database плагинами сомнительной поддержки.

Интеграция однонаправленная:

```text
StateGuard/Semgrep → SARIF → SonarScanner → SonarQube
```

SonarQube показывает finding. Решение о закрытии остаётся в StateGuard ledger и следующем анализе.

## 2.5. Analyzer workers

Рекомендуются разные worker pools:

- `fast`: Semgrep, native linters, manifest, schema validation;
- `db`: migrations, disposable PostgreSQL, pgTAP, concurrency tests;
- `deep`: Joern и APG;
- `formal`: ProB/Rodin/Z3;
- `ai`: локальные GPU workers для unresolved slices.

Так тяжёлый Joern не блокирует каждый PR, а AI не получает сетевой доступ только потому, что он
запущен на общей CI-машине.

## 2.6. Хранилища

| Данные | Локально | Централизованно | Retention |
|---|---|---|---|
| Исходный код | checkout | VCS | политика VCS |
| CPG/APG raw | deep worker | обычно нет | 1–14 дней |
| APG normalized slices | ledger/cache | опционально | 30–180 дней |
| Findings | SQLite | PostgreSQL + Sonar | долгосрочно |
| Proof attempts | SQLite | PostgreSQL | долгосрочно |
| Test logs | artifacts | artifact storage | 30–365 дней |
| AI prompts/responses | local encrypted store | опционально | минимально необходимый срок |
| Tool images | internal registry | internal registry | поддерживаемые версии |

## 2.7. Trust boundaries

Отдельно моделируются:

- developer workstation;
- CI runner;
- analyzer container;
- SonarQube;
- StateGuard control plane;
- local LLM runtime;
- artifact storage;
- production-like test database.

Каждая граница получает:

- network allowlist;
- read/write mounts;
- secrets scope;
- retention;
- audit logs;
- resource limits;
- владельца обновлений.
