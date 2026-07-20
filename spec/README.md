# Пример декларативной спецификации

- `order-workflow.specification.yaml` описывает entities, states, invariants, commands, outcomes,
  observations, external effects и assumptions.
- `order-workflow.mappings.yaml` связывает IDs с UI/API/server/SQL/database/tests.

Для нового проекта:

1. выполните `stateguard init`;
2. перенесите структуру примера в `.stateguard/specification.yaml`;
3. заполните mappings реальными stable symbols/routes/constraints;
4. выполните `stateguard validate`;
5. создайте proof policy для critical/high invariants.

Natural-language predicates в примере являются переходным форматом. Critical properties постепенно
переносятся в Event-B/SMT/SQL/reference functions, но сохраняют те же IDs.
