// Deliberately named parseCarrierWebhook, not decodeCarrierWebhook — see
// mappings.yaml's notes on CMD-SHIPMENT-RECORD-CHECKPOINT for why.

function isUuid(value) {
  return typeof value === "string" && /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(value);
}

const CHECKPOINT_CODES = new Set(["in_transit", "out_for_delivery", "delivered", "exception"]);

export function parseCarrierWebhook(raw) {
  if (!raw || typeof raw !== "object") {
    return { kind: "rejected", reason: "invalid_structure" };
  }
  if (!isUuid(raw.shipmentId)) {
    return { kind: "rejected", reason: "invalid_value", field: "shipmentId" };
  }
  if (typeof raw.providerEventId !== "string" || raw.providerEventId.length === 0) {
    return { kind: "rejected", reason: "invalid_value", field: "providerEventId" };
  }
  if (!Number.isSafeInteger(raw.sequenceNo) || raw.sequenceNo < 0) {
    return { kind: "rejected", reason: "invalid_value", field: "sequenceNo" };
  }
  if (!CHECKPOINT_CODES.has(raw.code)) {
    return { kind: "rejected", reason: "invalid_value", field: "code" };
  }
  return {
    kind: "accepted",
    event: Object.freeze({
      shipmentId: raw.shipmentId,
      providerEventId: raw.providerEventId,
      sequenceNo: raw.sequenceNo,
      code: raw.code,
    }),
  };
}
