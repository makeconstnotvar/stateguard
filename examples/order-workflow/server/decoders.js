function isUuid(value) {
  return typeof value === "string" && /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(value);
}

export function decodeSubmitOrder(raw) {
  if (!raw || typeof raw !== "object") {
    return { kind: "rejected", reason: "invalid_structure" };
  }
  if (!isUuid(raw.orderId) || !Number.isSafeInteger(raw.expectedVersion) || raw.expectedVersion < 1) {
    return { kind: "rejected", reason: "invalid_value" };
  }
  return {
    kind: "accepted",
    command: Object.freeze({
      orderId: raw.orderId,
      expectedVersion: raw.expectedVersion,
    }),
  };
}
