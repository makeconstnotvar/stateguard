import assert from "node:assert/strict";
import crypto from "node:crypto";
import fs from "node:fs";
import path from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

import pg from "pg";
import { GenericContainer, Wait } from "testcontainers";

import { createShipment } from "../server/create-shipment.js";
import { recordCheckpoint } from "../server/record-checkpoint.js";

const { Pool } = pg;
const here = path.dirname(fileURLToPath(import.meta.url));
const schema = fs.readFileSync(path.resolve(here, "../db/schema.sql"), "utf8");

async function databaseFixture(t) {
  const container = await new GenericContainer("postgres:17")
    .withEnvironment({
      POSTGRES_DB: "testdb",
      POSTGRES_USER: "test",
      POSTGRES_PASSWORD: "test",
    })
    .withExposedPorts(5432)
    .withWaitStrategy(Wait.forLogMessage(/database system is ready to accept connections/))
    .start();

  const pool = new Pool({
    host: container.getHost(),
    port: container.getMappedPort(5432),
    database: "testdb",
    user: "test",
    password: "test",
    max: 10,
  });
  // A Pool with zero 'error' listeners throws on an idle client's socket error
  // (EventEmitter semantics), which can otherwise crash teardown; log and swallow.
  pool.on("error", (error) => {
    console.error("pool error during test run/teardown:", error.message);
  });

  // Registration order matters: node:test runs `after` hooks in FIFO order, so
  // pool.end() must be registered (and therefore run) before container.stop() —
  // otherwise the container is killed while the pool still holds live sockets.
  t.after(() => pool.end());
  t.after(() => container.stop());

  await pool.query(schema);
  return pool;
}

async function seedShipment(pool) {
  const orderId = crypto.randomUUID();
  const created = await createShipment(pool, { orderId });
  assert.equal(created.kind, "accepted");
  return created.shipment;
}

test("checkpoint with sequence_no not greater than last_sequence is rejected as out_of_order", async (t) => {
  const pool = await databaseFixture(t);
  const shipment = await seedShipment(pool);

  const first = await recordCheckpoint(pool, {
    shipmentId: shipment.id,
    providerEventId: `evt-${crypto.randomUUID()}`,
    sequenceNo: 5,
    code: "in_transit",
  });
  assert.equal(first.kind, "accepted");
  assert.equal(first.duplicate, false);

  const stale = await recordCheckpoint(pool, {
    shipmentId: shipment.id,
    providerEventId: `evt-${crypto.randomUUID()}`,
    sequenceNo: 5,
    code: "exception",
  });
  assert.equal(stale.kind, "rejected");
  assert.equal(stale.reason, "out_of_order");
  assert.equal(stale.currentSequence, 5);

  const row = await pool.query("SELECT status, last_sequence FROM shipments WHERE id = $1", [shipment.id]);
  assert.equal(row.rows[0].status, "in_transit");
  assert.equal(Number(row.rows[0].last_sequence), 5);
});

test("checkpoint on a terminal shipment is rejected as wrong_state", async (t) => {
  const pool = await databaseFixture(t);
  const shipment = await seedShipment(pool);

  const toException = await recordCheckpoint(pool, {
    shipmentId: shipment.id,
    providerEventId: `evt-${crypto.randomUUID()}`,
    sequenceNo: 1,
    code: "exception",
  });
  assert.equal(toException.kind, "accepted");

  const afterTerminal = await recordCheckpoint(pool, {
    shipmentId: shipment.id,
    providerEventId: `evt-${crypto.randomUUID()}`,
    sequenceNo: 2,
    code: "in_transit",
  });
  assert.equal(afterTerminal.kind, "rejected");
  assert.equal(afterTerminal.reason, "wrong_state");
  assert.equal(afterTerminal.currentStatus, "exception");

  const row = await pool.query("SELECT status, last_sequence FROM shipments WHERE id = $1", [shipment.id]);
  assert.equal(row.rows[0].status, "exception");
  assert.equal(Number(row.rows[0].last_sequence), 1);
});

test("checkpoint code outside allowed_next(status) is rejected as invalid_transition", async (t) => {
  const pool = await databaseFixture(t);
  const shipment = await seedShipment(pool);

  // pending's allowed_next is {in_transit, exception}; delivered is not reachable
  // directly from pending, even though its sequence_no is validly increasing.
  const skipped = await recordCheckpoint(pool, {
    shipmentId: shipment.id,
    providerEventId: `evt-${crypto.randomUUID()}`,
    sequenceNo: 1,
    code: "delivered",
  });
  assert.equal(skipped.kind, "rejected");
  assert.equal(skipped.reason, "invalid_transition");
  assert.equal(skipped.currentStatus, "pending");

  const row = await pool.query("SELECT status, last_sequence FROM shipments WHERE id = $1", [shipment.id]);
  assert.equal(row.rows[0].status, "pending");
  assert.equal(Number(row.rows[0].last_sequence), 0);
});

test("creating a second shipment for the same order is rejected as duplicate_shipment", async (t) => {
  const pool = await databaseFixture(t);
  const orderId = crypto.randomUUID();

  const first = await createShipment(pool, { orderId });
  assert.equal(first.kind, "accepted");

  const second = await createShipment(pool, { orderId });
  assert.equal(second.kind, "rejected");
  assert.equal(second.reason, "duplicate_shipment");

  const count = await pool.query("SELECT COUNT(*) FROM shipments WHERE order_id = $1", [orderId]);
  assert.equal(Number(count.rows[0].count), 1);
});

test("two concurrent shipment creations for the same order: exactly one accepted, one duplicate_shipment", async (t) => {
  const pool = await databaseFixture(t);
  const orderId = crypto.randomUUID();

  const [left, right] = await Promise.all([
    createShipment(pool, { orderId }),
    createShipment(pool, { orderId }),
  ]);

  const accepted = [left, right].filter((result) => result.kind === "accepted");
  const rejected = [left, right].filter((result) => result.kind === "rejected");
  assert.equal(accepted.length, 1);
  assert.equal(rejected.length, 1);
  assert.equal(rejected[0].reason, "duplicate_shipment");

  const count = await pool.query("SELECT COUNT(*) FROM shipments WHERE order_id = $1", [orderId]);
  assert.equal(Number(count.rows[0].count), 1);
});

test("withRowLock genuinely blocks a concurrent recordCheckpoint call on the same shipment", async (t) => {
  const pool = await databaseFixture(t);
  const shipment = await seedShipment(pool);

  // Manually hold the row lock via a separate client, outside recordCheckpoint's own
  // machinery, so blocking is proven directly rather than inferred from Promise.all
  // timing (which connection-pool scheduling can make misleadingly look concurrent
  // even when the calls never actually contend on FOR UPDATE).
  const blocker = await pool.connect();
  await blocker.query("BEGIN");
  await blocker.query("SELECT id FROM shipments WHERE id = $1 FOR UPDATE", [shipment.id]);

  let settled = false;
  const blockedCall = recordCheckpoint(pool, {
    shipmentId: shipment.id,
    providerEventId: `evt-${crypto.randomUUID()}`,
    sequenceNo: 1,
    code: "in_transit",
  }).then((result) => {
    settled = true;
    return result;
  });

  // Generous margin for blockedCall to reach and block on FOR UPDATE (an in-process
  // await chain reaches this in well under a millisecond in practice).
  await new Promise((resolve) => setTimeout(resolve, 200));
  assert.equal(settled, false, "recordCheckpoint must still be blocked on the held row lock");

  await blocker.query("COMMIT");
  blocker.release();

  const result = await blockedCall;
  assert.equal(result.kind, "accepted");
  assert.equal(result.duplicate, false);
});

test("two concurrent identical webhook deliveries: exactly one mutates, one no-ops", async (t) => {
  const pool = await databaseFixture(t);
  const shipment = await seedShipment(pool);
  const providerEventId = `evt-${crypto.randomUUID()}`;
  const command = { shipmentId: shipment.id, providerEventId, sequenceNo: 1, code: "in_transit" };

  // Pre-warm two idle, already-authenticated connections so neither concurrent call
  // has to wait for a fresh TCP+auth handshake before reaching the row lock — without
  // this, pool scheduling can serialize the two calls over a single reused connection
  // and the assertions below would pass even with a broken/missing lock.
  const warm = await Promise.all([pool.connect(), pool.connect()]);
  warm.forEach((client) => client.release());

  const [left, right] = await Promise.all([
    recordCheckpoint(pool, command),
    recordCheckpoint(pool, command),
  ]);

  const duplicates = [left, right].filter((result) => result.duplicate === true);
  const originals = [left, right].filter((result) => result.duplicate === false);
  assert.equal(duplicates.length, 1);
  assert.equal(originals.length, 1);
  assert.ok([left, right].every((result) => result.kind === "accepted"));

  const count = await pool.query(
    "SELECT COUNT(*) FROM checkpoints WHERE shipment_id = $1 AND provider_event_id = $2",
    [shipment.id, providerEventId],
  );
  assert.equal(Number(count.rows[0].count), 1);
});

test("replaying an already-applied event after further progress still no-ops without reverting state", async (t) => {
  const pool = await databaseFixture(t);
  const shipment = await seedShipment(pool);
  const firstEvent = `evt-${crypto.randomUUID()}`;

  const first = await recordCheckpoint(pool, {
    shipmentId: shipment.id,
    providerEventId: firstEvent,
    sequenceNo: 1,
    code: "in_transit",
  });
  assert.equal(first.duplicate, false);

  const second = await recordCheckpoint(pool, {
    shipmentId: shipment.id,
    providerEventId: `evt-${crypto.randomUUID()}`,
    sequenceNo: 2,
    code: "out_for_delivery",
  });
  assert.equal(second.duplicate, false);

  const replay = await recordCheckpoint(pool, {
    shipmentId: shipment.id,
    providerEventId: firstEvent,
    sequenceNo: 1,
    code: "in_transit",
  });
  assert.equal(replay.kind, "accepted");
  assert.equal(replay.duplicate, true);

  const row = await pool.query("SELECT status, last_sequence FROM shipments WHERE id = $1", [shipment.id]);
  assert.equal(row.rows[0].status, "out_for_delivery");
  assert.equal(Number(row.rows[0].last_sequence), 2);
});

test("deferred database invariant rejects a shipment whose last_sequence does not match its checkpoints", async (t) => {
  const pool = await databaseFixture(t);
  const shipment = await seedShipment(pool);

  await recordCheckpoint(pool, {
    shipmentId: shipment.id,
    providerEventId: `evt-${crypto.randomUUID()}`,
    sequenceNo: 1,
    code: "in_transit",
  });

  const client = await pool.connect();
  try {
    await client.query("BEGIN");
    await client.query("UPDATE shipments SET last_sequence = 99 WHERE id = $1", [shipment.id]);
    await assert.rejects(
      client.query("COMMIT"),
      (error) => error.code === "23514" && error.constraint === "inv_ship_last_sequence_matches_checkpoints",
    );
  } finally {
    try {
      await client.query("ROLLBACK");
    } catch {}
    client.release();
  }

  const row = await pool.query("SELECT last_sequence FROM shipments WHERE id = $1", [shipment.id]);
  assert.equal(Number(row.rows[0].last_sequence), 1);
});
