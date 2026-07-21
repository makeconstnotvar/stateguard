UPDATE shipments
SET status = $2,
    last_sequence = $3
WHERE id = $1
RETURNING id, order_id, status, last_sequence, created_at;
