-- Run after applying every migration to an empty disposable database.
-- Example:
--   psql "$DATABASE_URL" -X -v ON_ERROR_STOP=1 -f postgres/catalog_snapshot.sql \
--     > .stateguard/results/postgres-catalog.jsonl

SELECT jsonb_build_object(
  'kind', 'table',
  'schema', n.nspname,
  'name', c.relname,
  'rls_enabled', c.relrowsecurity,
  'rls_forced', c.relforcerowsecurity
)
FROM pg_class c
JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE c.relkind IN ('r', 'p')
  AND n.nspname NOT IN ('pg_catalog', 'information_schema')
ORDER BY n.nspname, c.relname;

SELECT jsonb_build_object(
  'kind', 'column',
  'schema', n.nspname,
  'table', c.relname,
  'name', a.attname,
  'position', a.attnum,
  'type', pg_catalog.format_type(a.atttypid, a.atttypmod),
  'not_null', a.attnotnull,
  'identity', a.attidentity,
  'generated', a.attgenerated,
  'default', pg_get_expr(d.adbin, d.adrelid)
)
FROM pg_attribute a
JOIN pg_class c ON c.oid = a.attrelid
JOIN pg_namespace n ON n.oid = c.relnamespace
LEFT JOIN pg_attrdef d ON d.adrelid = a.attrelid AND d.adnum = a.attnum
WHERE a.attnum > 0
  AND NOT a.attisdropped
  AND c.relkind IN ('r', 'p')
  AND n.nspname NOT IN ('pg_catalog', 'information_schema')
ORDER BY n.nspname, c.relname, a.attnum;

SELECT jsonb_build_object(
  'kind', 'constraint',
  'schema', n.nspname,
  'table', c.relname,
  'name', con.conname,
  'constraint_type', con.contype,
  'deferrable', con.condeferrable,
  'initially_deferred', con.condeferred,
  'validated', con.convalidated,
  'definition', pg_get_constraintdef(con.oid, true)
)
FROM pg_constraint con
JOIN pg_class c ON c.oid = con.conrelid
JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE n.nspname NOT IN ('pg_catalog', 'information_schema')
ORDER BY n.nspname, c.relname, con.conname;

SELECT jsonb_build_object(
  'kind', 'index',
  'schema', n.nspname,
  'table', table_class.relname,
  'name', index_class.relname,
  'unique', index_meta.indisunique,
  'primary', index_meta.indisprimary,
  'valid', index_meta.indisvalid,
  'ready', index_meta.indisready,
  'definition', pg_get_indexdef(index_class.oid)
)
FROM pg_index index_meta
JOIN pg_class table_class ON table_class.oid = index_meta.indrelid
JOIN pg_class index_class ON index_class.oid = index_meta.indexrelid
JOIN pg_namespace n ON n.oid = table_class.relnamespace
WHERE n.nspname NOT IN ('pg_catalog', 'information_schema')
ORDER BY n.nspname, table_class.relname, index_class.relname;

SELECT jsonb_build_object(
  'kind', 'trigger',
  'schema', n.nspname,
  'table', c.relname,
  'name', t.tgname,
  'enabled', t.tgenabled,
  'definition', pg_get_triggerdef(t.oid, true)
)
FROM pg_trigger t
JOIN pg_class c ON c.oid = t.tgrelid
JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE NOT t.tgisinternal
  AND n.nspname NOT IN ('pg_catalog', 'information_schema')
ORDER BY n.nspname, c.relname, t.tgname;

SELECT jsonb_build_object(
  'kind', 'policy',
  'schema', schemaname,
  'table', tablename,
  'name', policyname,
  'permissive', permissive,
  'roles', roles,
  'command', cmd,
  'using', qual,
  'check', with_check
)
FROM pg_policies
ORDER BY schemaname, tablename, policyname;

SELECT jsonb_build_object(
  'kind', 'function',
  'schema', n.nspname,
  'name', p.proname,
  'identity_arguments', pg_get_function_identity_arguments(p.oid),
  'result', pg_get_function_result(p.oid),
  'language', l.lanname,
  'volatility', p.provolatile,
  'security_definer', p.prosecdef,
  'definition', pg_get_functiondef(p.oid)
)
FROM pg_proc p
JOIN pg_namespace n ON n.oid = p.pronamespace
JOIN pg_language l ON l.oid = p.prolang
WHERE n.nspname NOT IN ('pg_catalog', 'information_schema')
ORDER BY n.nspname, p.proname, pg_get_function_identity_arguments(p.oid);
