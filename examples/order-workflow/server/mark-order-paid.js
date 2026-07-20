import crypto from "node:crypto";
import { markOrderPaidSql } from "./sql.js";
import { withSerializableRetry } from "./transaction.js";

export async function markOrderPaid(pool, command) {
  return withSerializableRetry(pool, async (client) => {
    const updated = await client.query(markOrderPaidSql, [
      command.orderId,
      command.expectedVersion,
      command.paymentId,
    ]);

    if (updated.rowCount === 0) {
      return { kind: "rejected", reason: "guard_failed" };
    }

    const order = updated.rows[0];
    await client.query(
      `INSERT INTO outbox(id, topic, aggregate_id, idempotency_key, payload)
       VALUES ($1, 'order.paid', $2, $3, $4::jsonb)
       ON CONFLICT (idempotency_key) DO NOTHING`,
      [
        crypto.randomUUID(),
        order.id,
        `order-paid:${order.id}:${order.version}`,
        JSON.stringify({ orderId: order.id, version: Number(order.version) }),
      ],
    );

    // No network call occurs here. A separate idempotent worker publishes committed outbox rows.
    return { kind: "accepted", order };
  });
}
