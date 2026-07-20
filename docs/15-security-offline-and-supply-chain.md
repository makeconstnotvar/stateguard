# 15. Локальность, безопасность и supply chain

## 15.1. Требование

Корпоративный код, findings, APG и prompts не покидают утверждённую инфраструктуру. Это обеспечивается
не обещанием vendor, а сочетанием архитектуры и сетевых ограничений.

## 15.2. Execution zones

Рекомендуемые зоны:

```text
source checkout runner
fast analyzer containers
DB test network
Joern deep-analysis host
formal tools host
local LLM/GPU host
SonarQube zone
StateGuard control plane
artifact storage
```

Каждая зона имеет собственные ACL, secrets и retention.

## 15.3. Network-denied scanners

Semgrep/Joern/Z3 и другие scanners по возможности запускаются:

```text
network=none
read-only root filesystem
repository mount read-only
rules/config mount read-only
single writable output
non-root user
resource limits
temporary HOME/tmpfs
```

`run-semgrep.sh` демонстрирует этот режим. Перед запуском approved images заранее зеркалируются.

## 15.4. SonarQube

SonarScanner отправляет analysis data на внутренний SonarQube. Следовательно SonarQube — доверенная
система обработки исходного контекста. Требуются:

- internal-only address;
- TLS;
- access control;
- private projects;
- backups;
- patch management;
- plugin allowlist;
- restricted DB access;
- audit/log policy.

## 15.5. Local LLM

Cloud features/fallback отключаются конфигурацией и firewall. Model runtime не получает production
secrets. Prompts проходят redaction и хранятся минимально.

## 15.6. Image/package supply chain

Для каждого инструмента:

- скачать из approved source;
- проверить checksum/signature, где доступно;
- провести vulnerability/license review;
- mirror во внутренний registry/repository;
- pin digest/version;
- сформировать SBOM;
- подписать внутренним ключом;
- запретить runtime pull из public registry.

## 15.7. Rules/spec supply chain

Атака на ruleset может скрыть дефекты. Rules/spec/mappings:

- versioned в VCS;
- protected branch;
- CODEOWNERS;
- mandatory review;
- signed release artifact/hash;
- test fixtures;
- change log;
- rollback.

## 15.8. Analyzer trust

Статический анализатор исполняет сложный parser над недоверенным кодом. Контейнер/VM ограничивает:

- filesystem;
- network;
- CPU/RAM/pids;
- execution time;
- privileges;
- host sockets.

Не монтируйте Docker socket в scanner container без крайней необходимости.

## 15.9. Malicious repository content

Репозиторий может содержать:

- symlinks;
- huge files/decompression bombs;
- generated parser exploits;
- malicious build scripts;
- prompt injection;
- path traversal в reports.

StateGuard scanner пропускает symlinks, нормализует repository-relative paths и применяет size/time
limits. Build/test jobs запускаются в более изолированном контуре, чем read-only static scan.

## 15.10. Secrets

Preflight:

- secret scanner до публикации reports;
- исключение secret paths;
- redaction report messages;
- no environment dump;
- tokens project-scoped/short-lived;
- no admin tokens в repository CI.

## 15.11. Telemetry policy

Для каждого инструмента создайте запись:

```text
telemetry default
how disabled
network destinations
what metadata could be sent
verification method
approved version
```

Network deny остаётся последним техническим контролем. Проверка `verify-offline.sh` ловит часть
конфигурационных ошибок, но не является формальным аудитом бинарника.

## 15.12. Data classification

Артефакты классифицируются:

- source-derived sensitive;
- security finding restricted;
- aggregate internal;
- public tooling metadata.

SARIF может содержать snippets/messages. Не публикуйте его в общедоступные CI artifacts.

## 15.13. Retention и deletion

Удаление checkout не удаляет:

- SonarQube issue history;
- CI artifacts;
- central ledger;
- AI logs;
- backups.

Offboarding repository включает отдельную deletion procedure для каждого хранилища.

## 15.14. Threat model checklist

- compromised analyzer image;
- malicious dependency/build script;
- ruleset tampering;
- Sonar token leak;
- unauthorized project visibility;
- prompt exfiltration;
- central ledger path disclosure;
- forged proof result;
- stale evidence reused as current;
- waiver abuse;
- CI bypass.

Каждая угроза получает owner и control. StateGuard сам является security-sensitive development
system и требует такого же контроля, как CI/CD.
