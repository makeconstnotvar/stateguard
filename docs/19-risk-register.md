# 19. Реестр рисков реализации StateGuard

| Риск | Проявление | Контроль | Остаточный риск |
|---|---|---|---|
| Ложное чувство безопасности | clean dashboard называют доказательством | классы evidence, отдельный strict gate | неполная спецификация |
| Specification drift | модель отстаёт от кода | mappings, hashes, stale invalidation, PR review | скрытые runtime paths |
| Высокий false-positive rate | правила игнорируют | pilot, confidence, fixtures, staged rollout | framework diversity |
| False negatives | analyzer не видит dynamic behavior | APG uncertainty, tests, manual obligations | произвольная динамика |
| Слишком дорогой Joern | PR queue растёт | nightly/affected scope, workers, cache | большие monorepo |
| AI hallucination | неверный finding/fix | evidence refs, JSON schema, independent verify | смысловая неоднозначность |
| Утечка кода | scanner/LLM/CI отправляет данные | no-egress, internal mirrors, ACL, retention | compromised binary/admin |
| Ruleset compromise | checks выключены | protected repo, signed artifact, hash | insider/admin risk |
| Stale evidence | старый proof используется после change | artifact/input hashes, doctor | неполная dependency mapping |
| Ledger corruption | потеря audit history | WAL, backup, central publish, integrity checks | simultaneous filesystem failure |
| Sonar becomes source of truth | manual close скрывает finding | one-way SARIF, ledger authority | пользовательская путаница |
| Formal model too expensive | проект заброшен | critical scope only, phased pilot | нехватка expertise |
| Wrong model | доказано не то требование | domain review, animation, traces | business misunderstanding |
| Tool version drift | результаты невоспроизводимы | pinned versions/digests | vulnerability forces upgrade |
| Migration test unrealistic | production volume/locks отличаются | representative data, replica checks | production-only conditions |
| Flaky race tests | retry до зелёного | preserve first failure, deterministic barriers | scheduler variability |
| Waiver abuse | постоянные исключения | owner, expiry, approval, metrics | governance failure |
| Central outage | pipelines блокируются | local-first ledger, defined degradation | strict release delay |
| Adapter maintenance | framework upgrades ломают graph | golden fixtures, canary rollout | undocumented framework internals |
| Over-centralization | platform slows teams | repo-owned scripts/specs, stable contracts | inconsistent implementations |

## 19.1. Главный технический риск

Самый опасный риск — неполная связь модели с реализацией. Event-B может быть корректен, а реальный
handler иметь дополнительный обходной path. Поэтому StateGuard всегда разделяет:

```text
model correctness
implementation conformance
runtime/database verification
```

Зелёный статус требует evidence для всех трёх слоёв в critical scope.

## 19.2. Главный организационный риск

Команда может воспринимать StateGuard как сервис AppSec/платформы и перестать владеть инвариантами.
Без domain ownership инструмент вырождается в набор generic rules. Модель и mappings являются частью
продуктового кода и review процесса.

## 19.3. Decision log

Для существенных компромиссов создавайте ADR:

- почему выбран конкретный analyzer;
- почему свойство проверяется test, а не DB constraint;
- почему scope model checker bounded;
- почему waiver допустим;
- почему external effect использует конкретную delivery semantics.

ADR ID связывается с assumption/waiver/proof obligation.
