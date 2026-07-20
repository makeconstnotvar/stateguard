import assert from "node:assert/strict";
import crypto from "node:crypto";
import fs from "node:fs";
import path from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

import pg from "pg";
import { GenericContainer, Wait } from "testcontainers";

import { submitOrder } from "../server/submit-order.js";

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
  t.after(() => container.stop());

  const pool = new Pool({
    host: container.getHost(),
    port: container.getMappedPort(5432),
    database: "testdb",
    user: "test",
    password: "test",
    max: 10,
  });
  t.after(() => pool.end());
  await pool.query(schema);
  return pool;
}

test("two concurrent submissions yield exactly one accepted transition", async (t) => {
  const pool = await databaseFixture(t);
  const ownerId = crypto.randomUUID();
  const orderId = crypto.randomUUID();
  await pool.query("INSERT INTO app_user(id, display_name) VALUES ($1, 'Owner')", [ownerId]);
  await pool.query(
    "INSERT INTO orders(id, owner_id, total_minor, currency) VALUES ($1, $2, 1000, 'GBP')",
    [orderId, ownerId],
  );

  const command = { orderId, expectedVersion: 1 };
  const [left, right] = await Promise.all([
    submitOrder(pool, { id: ownerId }, command),
    submitOrder(pool, { id: ownerId }, command),
  ]);

  assert.equal([left, right].filter((result) => result.kind === "accepted").length, 1);
  const row = await pool.query("SELECT status, version FROM orders WHERE id = $1", [orderId]);
  assert.equal(row.rows[0].status, "submitted");
  assert.equal(Number(row.rows[0].version), 2);
});

test("deferred database invariant rejects a paid order with rejected payment", async (t) => {
  const pool = await databaseFixture(t);
  const ownerId = crypto.randomUUID();
  const orderId = crypto.randomUUID();
  const paymentId = crypto.randomUUID();
  await pool.query("INSERT INTO app_user(id, display_name) VALUES ($1, 'Owner')", [ownerId]);
  await pool.query(
    "INSERT INTO orders(id, owner_id, status, total_minor, currency) VALUES ($1, $2, 'submitted', 1000, 'GBP')",
    [orderId, ownerId],
  );
  await pool.query(
    `INSERT INTO payments(id, order_id, status, provider_operation_id, amount_minor, currency)
     VALUES ($1, $2, 'rejected', $3, 1000, 'GBP')`,
    [paymentId, orderId, `provider:${paymentId}`],
  );

  const client = await pool.connect();
  try {
    await client.query("BEGIN");
    await client.query(
      "UPDATE orders SET status='paid', payment_id=$2, version=version+1 WHERE id=$1",
      [orderId, paymentId],
    );
    await assert.rejects(
      client.query("COMMIT"),
      (error) => error.code === "23514" && error.constraint === "inv_paid_order_requires_matching_payment",
    );
  } finally {
    try { await client.query("ROLLBACK"); } catch {}
    client.release();
  }

  const row = await pool.query("SELECT status, payment_id FROM orders WHERE id = $1", [orderId]);
  assert.equal(row.rows[0].status, "submitted");
  assert.equal(row.rows[0].payment_id, null);
});
