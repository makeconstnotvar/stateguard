import java.nio.charset.StandardCharsets
import java.nio.file.{Files, Path, Paths}

private def writeUtf8(path: Path, value: String): Unit = {
  Files.createDirectories(path.getParent)
  Files.writeString(path, value, StandardCharsets.UTF_8)
}

@main def exec(cpgFile: String, outDir: String) = {
  importCpg(cpgFile)
  run.ossdataflow

  val output = Paths.get(outDir)
  Files.createDirectories(output)

  writeUtf8(output.resolve("methods.json"), cpg.method.toJsonPretty)
  writeUtf8(output.resolve("calls.json"), cpg.call.toJsonPretty)
  writeUtf8(output.resolve("files.json"), cpg.file.toJsonPretty)
  writeUtf8(output.resolve("type-declarations.json"), cpg.typeDecl.toJsonPretty)

  // These are candidate framework surfaces. They are deliberately broad and must be refined
  // by StateGuard mappings instead of being treated as proof on their own.
  writeUtf8(
    output.resolve("candidate-endpoint-calls.json"),
    cpg.call.name("(?i)(get|post|put|patch|delete|route|mapGet|mapPost|handle|register)").toJsonPretty
  )
  writeUtf8(
    output.resolve("candidate-database-calls.json"),
    cpg.call.name("(?i)(query|execute|exec|save|update|delete|insert|find|select)").toJsonPretty
  )
  writeUtf8(
    output.resolve("candidate-authorization-calls.json"),
    cpg.call.name("(?i)(authorize|authorise|requirePermission|checkPermission|canAccess|isAllowed)").toJsonPretty
  )
  writeUtf8(
    output.resolve("candidate-external-effects.json"),
    cpg.call.name("(?i)(fetch|send|publish|post|request|enqueue|dispatch|emit)").toJsonPretty
  )

  println(s"StateGuard Joern export written to $outDir")
}
