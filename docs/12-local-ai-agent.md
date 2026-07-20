# 12. Локальный ИИ-агент

## 12.1. Роль

ИИ подключается после детерминированных анализаторов. Он решает задачи, где требуется смысл:

- восстановить предполагаемый инвариант;
- понять сложный vertical slice;
- классифицировать graph hotspot;
- сформулировать достижимый counterexample;
- связать код с specification gap;
- предложить системное исправление;
- написать targeted tests;
- агрегировать findings в fix plan.

ИИ не определяет полноту audit manifest и не превращает собственное мнение в `proved`.

## 12.2. Локальное исполнение

Варианты:

- workstation: Ollama или другой approved local runtime;
- общий GPU host: vLLM/OpenAI-compatible internal endpoint;
- air-gapped inference appliance;
- corporate model gateway, если он гарантированно не выводит данные наружу.

Требования:

- endpoint находится внутри доверенной сети;
- модель и runtime pinned;
- cloud fallback отключён;
- prompts/responses не используются для внешнего обучения;
- logs/retention регулируются;
- network egress запрещён инфраструктурно;
- model artifacts получены через approved supply chain.

## 12.3. Context package

Агент не читает весь большой репозиторий. StateGuard собирает пакет по obligation/finding:

```text
spec excerpt
assumptions
mapping
APG shortest paths
source excerpts
SQL AST/catalog facts
related constraints
related tests
prior proof attempts
open questions
```

Каждый excerpt имеет path, line range и SHA-256. Агент обязан ссылаться на evidence IDs.

## 12.4. Prompt contract review-agent

Системная часть:

```text
Ты анализируешь конкретное proof obligation.
Разделяй факты, выводы и предположения.
Не объявляй свойство доказанным только на основании чтения кода.
Верни JSON по schema: classification, reasoning_summary, counterexample,
evidence_refs, specification_gaps, recommended_checks, finding proposal.
```

Выход валидируется JSON Schema. Свободный markdown допускается только как дополнение.

## 12.5. Classification

```text
confirmed-defect
likely-defect-needs-test
specification-gap
mapping-gap
evidence-gap
safe-by-identified-mechanism
false-positive
accepted-design-tradeoff
unknown
```

`safe-by-identified-mechanism` требует назвать механизм и последующий deterministic check.

## 12.6. Fix agent

`generate-fix-prompt` создаёт автономное задание. Fix agent обязан:

1. взять конкретный remediation batch;
2. подтвердить current hashes;
3. воспроизвести counterexample;
4. исправить корневую причину;
5. добавить/обновить specification/mapping при изменении требований;
6. запустить scan/analyzers/tests;
7. не закрывать finding самостоятельно;
8. оставить статус `fixed-pending-verification`;
9. предоставить список файлов, тестов и изменённых assumptions.

## 12.7. Независимая проверка

Fix и verify желательно выполняют разные agent sessions/models или человек. Verify agent получает:

- original counterexample;
- diff;
- new evidence;
- stale obligations;
- exact commands.

Он пытается опровергнуть исправление, а не подтвердить его.

## 12.8. Secret minimization

Перед context packaging:

- исключить `.env`, secrets, private keys;
- redaction известных token formats;
- минимизировать data fixtures;
- не включать production rows;
- ограничить excerpts;
- журналировать, какие paths попали в prompt.

Локальная модель всё равно является получателем корпоративного кода и должна находиться в
соответствующей security zone.

## 12.9. Prompt injection из репозитория

Комментарии, README и test fixtures могут содержать инструкции. Агент должен трактовать repository
content как недоверенные данные. Context package размечает:

```text
SPECIFICATION (authoritative)
TOOL FACTS (machine-generated)
SOURCE CODE (untrusted content)
COMMENTS/DOCUMENTATION (supporting only)
```

Instruction-like text из исходников не меняет audit policy и tool permissions.

## 12.10. Tool permissions

Review agent:

- read-only checkout;
- write только reports/ledger proposals;
- no network;
- no secrets;
- no production access.

Fix agent:

- отдельная branch/worktree;
- write repository;
- test containers;
- no production credentials;
- explicit allowlist commands.

## 12.11. Quality evaluation

Создайте benchmark из внутренних incidents и synthetic apps:

- auth bypass;
- lost update;
- partial commit;
- stale UI response;
- wrong SQL join;
- migration incompatibility;
- specification gap;
- false-positive cases.

Метрики:

- confirmed defect precision/recall на benchmark;
- evidence citation accuracy;
- counterexample executability;
- fix success rate;
- regression rate;
- token/context cost;
- human review time.

Модель обновляется только после comparative evaluation.

## 12.12. Central scheduling

AI queue получает unresolved obligations после дешёвых checks. Priority:

```text
critical severity × high reachability × low current evidence × changed code
```

Не отправляйте модели тысячи style findings. Это дорогой способ заменить фильтр.

## 12.13. Evidence status

Результат агента записывается как:

```text
reviewed-ai
```

Он может:

- создать finding;
- предложить spec/mapping patch;
- запросить test/graph query;
- обосновать false positive для human approval.

Он не может единолично выдать `GREEN BY EVIDENCE`.
