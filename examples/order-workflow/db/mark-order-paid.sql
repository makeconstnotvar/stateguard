UPDATE orders AS o
SET status = 'paid',
    payment_id = p.id,
    version = o.version + 1,
    updated_at = transaction_timestamp()
FROM payments AS p
WHERE o.id = $1
  AND o.status = 'submitted'
  AND o.version = $2
  AND p.id = $3
  AND p.order_id = o.id
  AND p.status = 'confirmed'
  AND p.amount_minor = o.total_minor
  AND p.currency = o.currency
RETURNING o.id, o.owner_id, o.status, o.total_minor, o.currency, o.payment_id, o.version, o.updated_at;
