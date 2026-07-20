// Load this file into an interactive Joern shell after importCpg(...).
// These are investigative queries. Production obligations should be implemented as versioned
// scripts with expected output schemas and regression fixtures.

// Calls and callers for database APIs.
cpg.call.name("(?i)(query|execute|save|update)").map(call =>
  (call.file.name.headOption, call.lineNumber, call.method.fullName.headOption, call.code)
).l

// Candidate HTTP route registration calls.
cpg.call.name("(?i)(get|post|put|patch|delete)").where(_.argument.isLiteral).code.l

// Candidate direct writes to a field named status.
cpg.assignment.where(_.target.code(".*\\.status")).map(a =>
  (a.file.name.headOption, a.lineNumber, a.method.fullName.headOption, a.code)
).l

// Example local data-flow investigation. Adapt sources/sinks to framework semantics first.
val sources = cpg.identifier.name("(?i)(body|params|query|request|input)")
val sinks = cpg.call.name("(?i)(query|execute|save|update)").argument
sinks.reachableByFlows(sources).p
