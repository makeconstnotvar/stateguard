# StateGuard central control plane — implementation contract

Этот каталог содержит DDL и OpenAPI-контракт будущего центрального сервиса. Local CLI остаётся
работоспособным без него. Control plane следует реализовывать после стабилизации процесса на 10–30
репозиториях.

## Что хранится

- repository/component inventory;
- immutable analysis runs;
- toolchain/policy hashes;
- normalized findings;
- proof obligation summaries;
- waivers;
- remediation batches;
- ownership/SLA.

Исходники и raw CPG не обязательны.

## Старт PostgreSQL schema

```bash
createdb stateguard_control
psql stateguard_control -v ON_ERROR_STOP=1 -f schema.sql
```

## API semantics

1. `POST /v1/runs` идемпотентен по `idempotencyKey`.
2. Findings/proofs можно загружать chunks до `complete`.
3. Завершённый run immutable.
4. Новый run supersedes предыдущий main run того же repository/policy scope.
5. Auth и tenant isolation реализуются инфраструктурой/API, не полагаясь только на client input.
