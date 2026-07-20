# Joern adapter

Joern строит CPG и используется в StateGuard для межфайловых фактов: call graph, control flow,
data flow и candidates для архитектурных поверхностей. Он не является бизнес-спецификацией.

## Базовый запуск

```bash
joern-parse /repo --output /repo/.stateguard/work/joern.cpg.bin
joern \
  --script joern/export_stateguard.sc \
  --param cpgFile=/repo/.stateguard/work/joern.cpg.bin \
  --param outDir=/repo/.stateguard/results/joern
```

Скрипт экспортирует широкие candidate sets. Следующий адаптер должен:

1. прочитать `mappings.yaml`;
2. классифицировать framework symbols;
3. создать нормализованные APG nodes/edges;
4. сохранить только необходимые slices и evidence, а не копировать весь CPG в SQLite;
5. связать каждый результат с версиями Joern, script hash и source hashes.

## Производственный режим

Для большого monorepo CPG строится по компонентам или языковым модулям. Полный анализ запускается
ночью и перед релизом; PR-проверка использует кэшированный base graph и ограниченный changed slice.
Joern server разрешается только во внутреннем сегменте и с аутентификацией. Исходный код и CPG
рассматриваются как одинаково чувствительные данные.
