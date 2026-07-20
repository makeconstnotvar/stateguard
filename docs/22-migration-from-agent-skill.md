# 22. Переход от agent skill к инженерной системе

## 22.1. Что остаётся от skill

Существующий skill StateGuard полезен как orchestrator:

- объясняет методику;
- делит аудит на units;
- проводит смысловой review;
- создаёт findings;
- генерирует fix prompt;
- выполняет fix/verify workflow.

Он не должен сам хранить истину о покрытии в контексте модели. Истина переносится в CLI/ledger.

## 22.2. Целевая связка

```text
StateGuard CLI/engine
  deterministic manifest, analyzers, APG, proofs, ledger

StateGuard skill for Codex/Claude
  invokes CLI, reads bounded units, performs semantic review/fix/verify
```

## 22.3. Команды skill

Claude Code plugin:

```text
/stateguard:audit
/stateguard:fix
/stateguard:verify
```

Codex:

```text
$stateguard audit
$stateguard fix
$stateguard verify
```

Skill должен вызывать реальные CLI команды и ссылаться на ledger, а не вести параллельные markdown
списки без hashes.

## 22.4. Audit mode

```text
stateguard scan
stateguard autoplan
stateguard claim --worker <session>
```

Агент получает files unit, исследует vertical slice, добавляет findings, затем:

```text
stateguard complete --unit ... --worker ...
```

Если контекст закончился, следующий session claim-ит следующий unit. Complete result остаётся
current только до изменения input hashes.

## 22.5. Fix mode

Skill читает generated `fix-prompt.md`, берёт batch и исправляет в worktree/branch. После patch scan
автоматически инвалидирует старое evidence.

## 22.6. Verify mode

Независимая session:

- повторяет counterexample;
- проверяет diff и new tests;
- запускает affected analyzers;
- меняет finding status;
- закрывает related obligation только допустимым evidence;
- выполняет `doctor --strict`.

## 22.7. Что удалить из skill

- заявления о полном покрытии на основании «прочитал файлы»;
- собственную неструктурированную базу findings;
- команды, которые обходят ledger;
- автоматическое закрытие после собственного fix;
- prompt, отправляющий весь repository в модель.

## 22.8. Что добавить

- CLI capability detection;
- exact command templates;
- JSON output parsing;
- lease heartbeat/fencing при длительном review;
- evidence schema;
- tool failure handling;
- bounded context package;
- explicit `reviewed-ai` status;
- no-egress instruction и preflight.

## 22.9. Совместимость

Можно сохранить человекочитаемое имя:

> **StateGuard: Бюро запрещённых состояний**

Технические идентификаторы остаются `stateguard`, каталог `.stateguard`, команды `audit/fix/verify`.
