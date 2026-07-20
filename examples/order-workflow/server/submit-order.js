import { submitOrderSql } from "./sql.js";

export async function submitOrder(pool, actor, command) {
  const updated = await pool.query(submitOrderSql, [
    command.orderId,
    actor.id,
    command.expectedVersion,
  ]);

  if (updated.rowCount === 1) {
    return { kind: "accepted", order: updated.rows[0] };
  }

  // This read does not decide whether a mutation may happen; the UPDATE guard already did that
  // atomically. It only creates a useful authoritative rejection response.
  const current = await pool.query(
    `SELECT id, owner_id, status, version
       FROM orders
      WHERE id = $1`,
    [command.orderId],
  );

  if (current.rowCount === 0) {
    return { kind: "rejected", reason: "not_found" };
  }
  const order = current.rows[0];
  if (order.owner_id !== actor.id) {
    return { kind: "rejected", reason: "forbidden" };
  }
  if (Number(order.version) !== command.expectedVersion) {
    return {
      kind: "rejected",
      reason: "stale_version",
      currentVersion: Number(order.version),
      currentState: order.status,
    };
  }
  return { kind: "rejected", reason: "wrong_state", currentState: order.status };
}
