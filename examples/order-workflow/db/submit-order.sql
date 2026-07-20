UPDATE orders
SET status = 'submitted',
    version = version + 1,
    updated_at = transaction_timestamp()
WHERE id = $1
  AND owner_id = $2
  AND status = 'draft'
  AND version = $3
RETURNING id, owner_id, status, total_minor, currency, payment_id, version, updated_at;
