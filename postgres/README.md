# PostgreSQL analysis contour

StateGuard анализирует одновременно два представления:

1. SQL AST каждого запроса и migration, полученный parser'ом PostgreSQL (`libpg_query` или
   доверенным binding'ом к нему).
2. Фактический catalog временной базы после последовательного применения migrations.

Текстовый regex-поиск не заменяет ни одно из них. AST отвечает, что запрос читает и меняет;
catalog отвечает, какие constraints, типы, indexes, triggers и RLS policies реально существуют.

## Рекомендуемый процесс

```text
create disposable PostgreSQL
→ apply migrations from the supported previous version
→ apply current migrations
→ dump normalized catalog
→ parse repository SQL into normalized AST contracts
→ compare specification mappings with catalog and query facts
→ execute model-derived and concurrency tests
```

`catalog_snapshot.sql` выводит JSONL-факты. В production к каждой записи добавляются:

- PostgreSQL server version;
- migration-set hash;
- container image digest;
- extraction script hash;
- timestamp и audit run ID.

## Обязательства, закрываемые реальной БД

- `NOT NULL`, `CHECK`, `UNIQUE`, `FOREIGN KEY`, `EXCLUDE` действительно активны и validated;
- partial unique index имеет ожидаемый predicate;
- transaction isolation и retry дают допустимую историю;
- query projection совпадает с эталонной функцией наблюдения;
- migrations преобразуют существующие данные и поддерживают rolling deployment;
- constraint triggers закрывают только те cross-row/cross-table свойства, для которых измерена
  стоимость и отсутствует более простое представление.
