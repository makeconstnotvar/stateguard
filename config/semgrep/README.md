# StateGuard Semgrep starter rules

Это стартовый, а не универсальный ruleset. Правила делятся на три класса:

1. Высокоуверенные механические запреты — например, SQL template interpolation и пустой catch.
2. Архитектурные эвристики — например, внешний эффект внутри transaction callback.
3. Шаблоны, которые обязаны быть адаптированы под framework и каталоги конкретного проекта.

Перед блокированием CI каждое правило проходит три стадии:

- `audit`: только отчёт;
- `warn`: предупреждение в PR;
- `enforce`: ненулевой exit code для нового кода.

Semgrep CE не является межфайловым доказателем. Любая находка, требующая call graph, dominance,
межпроцедурного data flow или понимания транзакционной границы, подтверждается Joern/StateGuard
APG, тестом или ручным evidence.

Проверка ruleset:

```bash
semgrep --validate --config config/semgrep/rules
semgrep --test config/semgrep
```
