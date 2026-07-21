import crypto from "node:crypto";
import { applyCheckpointSql } from "./sql.js";
import { withRowLock } from "./locking.js";

const TERMINAL_STATUSES = new Set(["delivered", "exception"]);
const ALLOWED_NEXT = {
  pending: new Set(["in_transit", "exception"]),
  in_transit: new Set(["out_for_delivery", "exception"]),
  out_for_delivery: new Set(["delivered", "exception"]),
};

export async function recordCheckpoint(pool, command) {
  return withRowLock(pool, command.shipmentId, async (client, shipment) => {
    if (!shipment) {
      return { kind: "rejected", reason: "not_found" };
    }

    // Duplicate check first: a replay must never be misread as an ordering violation.
    const duplicate = await client.query(
      "SELECT 1 FROM checkpoints WHERE shipment_id = $1 AND provider_event_id = $2",
      [command.shipmentId, command.providerEventId],
    );
    if (duplicate.rowCount > 0) {
      return { kind: "accepted", duplicate: true, shipment };
    }

    if (TERMINAL_STATUSES.has(shipment.status)) {
      return { kind: "rejected", reason: "wrong_state", currentStatus: shipment.status };
    }
    if (Number(shipment.last_sequence) >= command.sequenceNo) {
      return {
        kind: "rejected",
        reason: "out_of_order",
        currentSequence: Number(shipment.last_sequence),
      };
    }
    const allowed = ALLOWED_NEXT[shipment.status] ?? new Set();
    if (!allowed.has(command.code)) {
      return { kind: "rejected", reason: "invalid_transition", currentStatus: shipment.status };
    }

    const updated = await client.query(applyCheckpointSql, [
      command.shipmentId,
      command.code,
      command.sequenceNo,
    ]);
    await client.query(
      `INSERT INTO checkpoints(id, shipment_id, provider_event_id, sequence_no, code)
       VALUES ($1, $2, $3, $4, $5)`,
      [crypto.randomUUID(), command.shipmentId, command.providerEventId, command.sequenceNo, command.code],
    );
    return { kind: "accepted", duplicate: false, shipment: updated.rows[0] };
  });
}
