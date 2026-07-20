# 18. Процесс команды и governance

## 18.1. Definition of Done для critical command

Command считается готовым, когда:

- input decoder тотален;
- authorization определена на сервере;
- states/guards/outcomes внесены в specification;
- invariant impact рассмотрен;
- mapping указывает handler/SQL/UI/tests;
- transaction/linearization point явен;
- concurrency mechanism указан;
- external effects имеют delivery semantics;
- DB constraints добавлены где возможно;
- negative/concurrency tests существуют;
- proof obligations закрыты по policy;
- observability и typed failures предусмотрены.

## 18.2. Code review

Reviewer смотрит не только diff, но affected proof slice:

```text
какие states/transitions изменились
какие invariants затронуты
какие SQL/schema изменения
какие outcomes/UI projections
какие obligations stale
```

StateGuard генерирует review summary.

## 18.3. Specification review

Участники:

- domain owner;
- implementation owner;
- DB/concurrency reviewer для critical flow;
- security reviewer для auth/data visibility;
- formal-methods champion при Event-B scope.

Natural-language requirements и formal predicate должны иметь одинаковый ID/decision record.

## 18.4. Change classification

Каждый PR отмечает:

```text
no-domain-change
new-command
state-transition-change
invariant-change
observation/visibility-change
schema/migration-change
external-effect-change
assumption-change
```

Класс определяет required jobs/reviewers.

## 18.5. Ownership

CODEOWNERS дополняется StateGuard ownership:

```yaml
components:
  order-workflow:
    domain_owner: commerce-team
    technical_owner: order-platform
    db_owner: data-platform
    security_owner: appsec
```

Finding не должен жить без owner.

## 18.6. Severity triage

Triage отвечает:

1. Достижим ли counterexample?
2. Какое свойство нарушено?
3. Каков blast radius?
4. Существуют ли компенсирующие controls?
5. Нужен code fix, spec fix или evidence?
6. Требуется ли production data check?
7. Какие releases/commits затронуты?

## 18.7. SLA

Пример:

- critical: немедленный triage, release blocked;
- high: triage в 1 рабочий день, fix по risk policy;
- medium: backlog с owner/date;
- evidence/spec gap critical scope: рассматривается как high до разрешения.

## 18.8. Waiver board

Critical/high accepted risk проходит отдельное утверждение. Meeting не должен обсуждать style noise;
на вход подаются counterexample, impact, alternatives, expiry и compensating controls.

## 18.9. Rule governance

Каждое новое правило:

- имеет owner;
- связано с failure mode;
- tested;
- измерено;
- документировано;
- rollout staged;
- переоценивается через 3–6 месяцев.

Правила с persistently low precision удаляются или становятся hotspot.

## 18.10. Proof debt

Debt dashboards:

- missing mappings;
- pending/stale obligations;
- AI-only critical reviews;
- unvalidated migrations;
- expired waivers;
- components без model owner.

Proof debt планируется так же, как security debt.

## 18.11. Architecture discipline

StateGuard стимулирует стандартные primitives:

- command handlers;
- closed result types;
- transaction wrapper;
- conditional updates;
- outbox;
- explicit query services;
- form/remote/operation UI state separation;
- versioned mappings.

Исключения допускаются, но стоят дороже по evidence.

## 18.12. Обучение

Команда должна понимать:

- safety vs liveness;
- invariant/guard/outcome;
- atomicity/isolation/idempotency;
- unknown outcome;
- stale evidence;
- false positive vs specification gap;
- что модель и реализация проверяются отдельно.

## 18.13. Success criteria

Успех — не рост числа findings. Признаки:

- меньше incidents запрещённых состояний;
- более быстрый review критичных изменений;
- race/migration defects находятся до production;
- constraints и typed outcomes становятся нормой;
- remediation prompt воспроизводим;
- аудит продолжается между сессиями без потери контекста.
