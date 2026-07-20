const SERIALIZATION_FAILURE = "40001";
const DEADLOCK_DETECTED = "40P01";

export async function withSerializableRetry(pool, operation, { maxAttempts = 4 } = {}) {
  for (let attempt = 1; attempt <= maxAttempts; attempt += 1) {
    const client = await pool.connect();
    try {
      await client.query("BEGIN ISOLATION LEVEL SERIALIZABLE");
      const result = await operation(client, attempt);
      await client.query("COMMIT");
      return result;
    } catch (error) {
      try {
        await client.query("ROLLBACK");
      } catch {
        // Connection cleanup is handled by the pool; the original error remains authoritative.
      }
      const retryable = error?.code === SERIALIZATION_FAILURE || error?.code === DEADLOCK_DETECTED;
      if (!retryable || attempt === maxAttempts) {
        throw error;
      }
    } finally {
      client.release();
    }
  }
  throw new Error("unreachable retry loop");
}
