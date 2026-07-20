# 14. CI/CD и release gate

## 14.1. Общая схема

```text
PR fast
  native build/analyzers
  unit/property tests
  Semgrep fast
  StateGuard incremental scan
  selected DB/concurrency tests
  required CI status

main
  full build/tests
  Sonar analysis + SARIF
  StateGuard standard
  publish central summary

nightly/release
  Joern/APG
  Event-B/ProB
  Z3 obligations
  full migration/concurrency/failure tests
  local AI unresolved review
  doctor --strict
```

Шаблоны для GitHub Actions self-hosted, GitLab и Jenkins находятся в `ci/`.

## 14.2. Только self-hosted runners

Корпоративный код остаётся внутри сети. Runner policy:

- ephemeral или регулярно reset;
- no shared untrusted workloads;
- internal package/container mirrors;
- no unrestricted egress;
- least-privilege repository token;
- isolated Docker daemon/rootless strategy по корпоративному стандарту;
- secrets только для конкретного job;
- artifact encryption/retention.

## 14.3. Job ordering

StateGuard external SARIF должен быть создан до SonarScanner. Правильный порядок main job:

```bash
stateguard scan
stateguard autoplan
run native analyzers
run Semgrep
stateguard import-sarif ...
run targeted proofs/tests and record results
stateguard export-sarif
sonar-scanner
stateguard doctor
publish summary
```

## 14.4. Incremental scope

Changed paths вычисляются относительно merge base. Затем dependency/APG graph расширяет scope:

```text
changed handler
→ command
→ related SQL/migration
→ entity/invariants
→ UI callers
→ tests
```

Если graph отсутствует или не уверен, scope расширяется до компонента. Скорость не должна достигаться
ценой молчаливого пропуска.

## 14.5. Caching

Можно кэшировать:

- package dependencies;
- analyzer images;
- Joern CPG по exact commit/tool version;
- parsed SQL AST;
- unchanged APG components;
- model proof outputs по input hash.

Нельзя повторно использовать результат, если не совпадает:

```text
source hash + spec/mapping hash + policy/ruleset hash + tool version + assumptions
```

## 14.6. Artifacts

Каждый job публикует:

```text
manifest.json
semgrep.sarif
stateguard.sarif
status.json
doctor.json
proofs.json
catalog snapshot hash
selected test reports
fix-prompt.md при failure
```

Raw source excerpts и CPG публикуются только в защищённое хранилище с коротким retention.

## 14.7. Gate policy

PR блокируется при:

- новый critical/high confirmed finding;
- failing critical/high obligation в touched scope;
- stale required evidence без recheck;
- migration/concurrency test failure;
- invalid specification/mapping;
- scanner/tool execution failure для обязательного слоя;
- expired waiver.

Analyzer crash нельзя трактовать как clean scan.

## 14.8. Legacy rollout

Режимы:

```text
observe      — только сбор
warn         — non-blocking annotations
new-code     — блокировать новые нарушения
critical-all — блокировать critical независимо от возраста
strict       — полный gate
```

Переход по репозиториям контролируется central policy. Не оставляйте `observe` бессрочно.

## 14.9. Release evidence bundle

Для релиза создаётся immutable bundle:

```text
release/version/commit
source manifest hash
spec/mapping hash
toolchain and images
Sonar gate result
StateGuard verdict
proof attempts
model checker bounds
DB/test reports
waivers
known limitations
```

Bundle подписывается/хэшируется и хранится рядом с release artifacts.

## 14.10. Fix workflow

При failure:

```bash
stateguard generate-fix-prompt
```

Agent/human исправляет в branch. После patch:

```bash
stateguard scan
# affected units/proofs становятся stale
run selected analyzers/tests
set finding fixed-pending-verification
independent verify
stateguard doctor --strict
```

## 14.11. Monorepo

Pipeline один раз получает manifest и changed graph, затем запускает matrix по affected components.
Sonar project strategy выбирается заранее:

- один project на monorepo;
- либо project на deployable application.

Не создавайте project на каждый package без операционной необходимости.

## 14.12. Multi-language builds

SonarScanner и native analyzers требуют build-specific setup. StateGuard orchestration вызывает
project-owned scripts:

```text
ci/project-fast-checks.sh
ci/project-full-checks.sh
ci/run-database-concurrency-suite.sh
```

StateGuard не должен угадывать build каждой технологии. Он задаёт вход/выход и required evidence.

## 14.13. Failure handling

- transient infrastructure failure → job retry по явной policy;
- deterministic analyzer failure → engineering incident;
- flaky test → сохраняется counterexample, obligation не закрыт;
- unavailable deep worker → release policy решает fail closed/open; critical release обычно fail closed;
- Sonar unavailable → StateGuard может продолжить локально, но organizational gate считается unknown.

## 14.14. Метрики pipeline

- p50/p95 duration по layer;
- queue time;
- cache hit;
- analyzer failure rate;
- findings per changed KLOC;
- false-positive ratio;
- stale obligations after merge;
- mean remediation time;
- strict coverage by repository.
