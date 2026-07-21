import crypto from "node:crypto";
import { createShipmentSql } from "./sql.js";

const UNIQUE_VIOLATION = "23505";

export async function createShipment(pool, command) {
  const id = crypto.randomUUID();
  try {
    const inserted = await pool.query(createShipmentSql, [id, command.orderId]);
    if (inserted.rowCount === 1) {
      return { kind: "accepted", shipment: inserted.rows[0] };
    }
    return { kind: "rejected", reason: "duplicate_shipment" };
  } catch (error) {
    // The WHERE NOT EXISTS guard is only safe sequentially: two concurrent creates for
    // the same order_id can both pass the guard before either commits, and the loser
    // fails the orders_order_id_key unique index instead of getting rowCount === 0.
    if (error?.code === UNIQUE_VIOLATION) {
      return { kind: "rejected", reason: "duplicate_shipment" };
    }
    throw error;
  }
}
