# Order workflow example

Минимальный вертикальный срез показывает:

- тотальный decoder;
- atomic conditional update для перехода `draft → submitted`;
- optimistic concurrency через `version`;
- typed rejections;
- `SERIALIZABLE` retry для составной команды;
- outbox вместо внешнего эффекта внутри транзакции;
- deferred constraint trigger для критичного cross-table invariant;
- monotonic version handling в MobX store;
- конкурентный тест на настоящем PostgreSQL.

Запуск:

```bash
npm install
npm test
```

Пример учебный. В production UUID, роли, миграции, observability, retry budgets, connection
settings и permissions должны следовать стандартам конкретной компании.
