import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const directory = path.dirname(fileURLToPath(import.meta.url));
const dbDirectory = path.resolve(directory, "../db");

export const createShipmentSql = fs.readFileSync(path.join(dbDirectory, "create-shipment.sql"), "utf8");
export const applyCheckpointSql = fs.readFileSync(path.join(dbDirectory, "apply-checkpoint.sql"), "utf8");
