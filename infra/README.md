# Внутренний SonarQube Community Build

## Быстрый запуск

```bash
cp .env.example .env
chmod 600 .env
# Замените пароль в .env.
sudo ./scripts/prepare-linux-host.sh
./scripts/up.sh
```

По умолчанию web port привязан к `127.0.0.1:9000`. Для общего сервера размещайте SonarQube за
корпоративным TLS reverse proxy и не публикуйте PostgreSQL наружу.

## Production changes

- замените image tags на approved immutable digests;
- используйте внутренний registry;
- вынесите PostgreSQL согласно корпоративному DB стандарту;
- подключите secret manager вместо `.env`;
- настройте backup/restore monitoring;
- ограничьте extensions/plugins allowlist;
- создайте staging для upgrades;
- настройте SSO/permissions доступными средствами выбранной редакции.

## Backup

```bash
./scripts/backup.sh /secure/backup/path
```

Скрипт останавливает SonarQube compute/web и делает custom-format `pg_dump`. Это starter runbook;
production backup должен быть частью общей системы и регулярно восстанавливаться в test environment.

## Project provisioning

```bash
export SONAR_HOST_URL=https://sonarqube.internal
export SONAR_ADMIN_TOKEN=...
./scripts/provision-project.sh acme:commerce:order-service "Order Service"
```

Admin token используется только provisioning job. Project pipeline получает отдельный analysis token.
