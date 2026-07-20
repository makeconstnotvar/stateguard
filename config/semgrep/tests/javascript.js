async function badSql(db, req) {
  // ruleid: stateguard.javascript.sql-template-interpolation
  return db.query(`select * from users where id = '${req.params.id}'`);
}

async function swallowed() {
  try {
    await doWork();
  // ruleid: stateguard.javascript.empty-catch
  } catch (error) {}
}

async function dangerousEffect(withTransaction, bus) {
  return withTransaction(async () => {
    await updateRows();
    // ruleid: stateguard.javascript.external-effect-inside-transaction-callback
    await bus.publish({ kind: "done" });
  });
}

async function goodSql(db, req, schema) {
  const command = schema.parse(req.body);
  // ok: stateguard.javascript.sql-template-interpolation
  return db.query("select * from users where id = $1", [command.id]);
}
