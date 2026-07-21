// Pessimistic-lock strategy: SELECT ... FOR UPDATE blocks concurrent callers for the
// same shipment rather than aborting them, so there is no retry loop here — unlike
// order-workflow's withSerializableRetry (server/transaction.js in that example), which
// aborts and retries on serialization failure. Registered under this name (not
// "withSerializableRetry") in mappings.yaml's framework_adapters.transaction_starts.
export async function withRowLock(pool, shipmentId, operation) {
  const client = await pool.connect();
  try {
    await client.query("BEGIN");
    const locked = await client.query(
      "SELECT id, order_id, status, last_sequence FROM shipments WHERE id = $1 FOR UPDATE",
      [shipmentId],
    );
    const result = await operation(client, locked.rows[0] ?? null);
    await client.query("COMMIT");
    return result;
  } catch (error) {
    try {
      await client.query("ROLLBACK");
    } catch {
      // Connection cleanup is handled by the pool; the original error remains authoritative.
    }
    throw error;
  } finally {
    client.release();
  }
}
