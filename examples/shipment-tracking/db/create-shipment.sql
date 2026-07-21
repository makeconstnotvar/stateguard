INSERT INTO shipments (id, order_id, status, last_sequence)
SELECT $1, $2, 'pending', 0
WHERE NOT EXISTS (SELECT 1 FROM shipments WHERE order_id = $2)
RETURNING id, order_id, status, last_sequence, created_at;
