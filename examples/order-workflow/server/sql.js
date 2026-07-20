import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const directory = path.dirname(fileURLToPath(import.meta.url));
const dbDirectory = path.resolve(directory, "../db");

export const submitOrderSql = fs.readFileSync(path.join(dbDirectory, "submit-order.sql"), "utf8");
export const markOrderPaidSql = fs.readFileSync(path.join(dbDirectory, "mark-order-paid.sql"), "utf8");
