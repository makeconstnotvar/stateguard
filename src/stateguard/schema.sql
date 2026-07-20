PRAGMA foreign_keys = ON;
PRAGMA journal_mode = WAL;
PRAGMA synchronous = NORMAL;
PRAGMA busy_timeout = 10000;

CREATE TABLE IF NOT EXISTS metadata (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS audit_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    kind TEXT NOT NULL,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    status TEXT NOT NULL DEFAULT 'running',
    repo_root TEXT NOT NULL,
    git_commit TEXT,
    config_hash TEXT,
    notes TEXT
);

CREATE TABLE IF NOT EXISTS artifacts (
    path TEXT PRIMARY KEY,
    kind TEXT NOT NULL,
    sha256 TEXT NOT NULL,
    size_bytes INTEGER NOT NULL,
    mtime_ns INTEGER NOT NULL,
    generated INTEGER NOT NULL DEFAULT 0,
    deleted INTEGER NOT NULL DEFAULT 0,
    first_seen_run_id INTEGER NOT NULL REFERENCES audit_runs(id),
    last_seen_run_id INTEGER NOT NULL REFERENCES audit_runs(id),
    last_changed_run_id INTEGER NOT NULL REFERENCES audit_runs(id),
    reviewed_sha256 TEXT,
    review_status TEXT NOT NULL DEFAULT 'unreviewed',
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_artifacts_review_status
    ON artifacts(review_status, deleted);

CREATE TABLE IF NOT EXISTS review_units (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    unit_key TEXT NOT NULL UNIQUE,
    title TEXT NOT NULL,
    component TEXT,
    priority INTEGER NOT NULL DEFAULT 100,
    status TEXT NOT NULL DEFAULT 'pending',
    current_hash TEXT,
    reviewed_hash TEXT,
    claimed_by TEXT,
    lease_until TEXT,
    notes TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS review_unit_artifacts (
    unit_id INTEGER NOT NULL REFERENCES review_units(id) ON DELETE CASCADE,
    artifact_path TEXT NOT NULL REFERENCES artifacts(path) ON DELETE CASCADE,
    PRIMARY KEY (unit_id, artifact_path)
);

CREATE INDEX IF NOT EXISTS idx_review_units_claim
    ON review_units(status, priority, lease_until);

CREATE TABLE IF NOT EXISTS tool_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    audit_run_id INTEGER REFERENCES audit_runs(id),
    tool_name TEXT NOT NULL,
    tool_version TEXT,
    command TEXT,
    config_hash TEXT,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    status TEXT NOT NULL DEFAULT 'running',
    exit_code INTEGER,
    stdout_path TEXT,
    stderr_path TEXT,
    report_path TEXT
);

CREATE TABLE IF NOT EXISTS findings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    external_key TEXT NOT NULL UNIQUE,
    source_tool TEXT NOT NULL,
    rule_id TEXT NOT NULL,
    title TEXT NOT NULL,
    message TEXT NOT NULL,
    severity TEXT NOT NULL,
    confidence TEXT NOT NULL DEFAULT 'medium',
    category TEXT NOT NULL DEFAULT 'implementation-defect',
    status TEXT NOT NULL DEFAULT 'open',
    file_path TEXT,
    start_line INTEGER,
    start_column INTEGER,
    end_line INTEGER,
    end_column INTEGER,
    artifact_sha256 TEXT,
    invariant_id TEXT,
    transition_id TEXT,
    counterexample TEXT,
    impact TEXT,
    root_cause TEXT,
    remediation TEXT,
    verification TEXT,
    first_seen_run_id INTEGER REFERENCES audit_runs(id),
    last_seen_run_id INTEGER REFERENCES audit_runs(id),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_findings_open
    ON findings(status, severity, source_tool);
CREATE INDEX IF NOT EXISTS idx_findings_location
    ON findings(file_path, start_line);

CREATE TABLE IF NOT EXISTS evidence (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    finding_id INTEGER REFERENCES findings(id) ON DELETE CASCADE,
    obligation_id INTEGER REFERENCES proof_obligations(id) ON DELETE CASCADE,
    evidence_type TEXT NOT NULL,
    file_path TEXT,
    start_line INTEGER,
    end_line INTEGER,
    artifact_sha256 TEXT,
    excerpt TEXT,
    payload_json TEXT,
    created_at TEXT NOT NULL,
    CHECK (finding_id IS NOT NULL OR obligation_id IS NOT NULL)
);

CREATE TABLE IF NOT EXISTS proof_obligations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    obligation_key TEXT NOT NULL UNIQUE,
    kind TEXT NOT NULL,
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    criticality TEXT NOT NULL DEFAULT 'medium',
    status TEXT NOT NULL DEFAULT 'pending',
    solver TEXT,
    specification_hash TEXT,
    input_hash TEXT,
    last_attempt_id INTEGER,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS proof_inputs (
    obligation_id INTEGER NOT NULL REFERENCES proof_obligations(id) ON DELETE CASCADE,
    artifact_path TEXT NOT NULL REFERENCES artifacts(path) ON DELETE CASCADE,
    artifact_sha256 TEXT NOT NULL,
    PRIMARY KEY (obligation_id, artifact_path)
);

CREATE TABLE IF NOT EXISTS proof_attempts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    obligation_id INTEGER NOT NULL REFERENCES proof_obligations(id) ON DELETE CASCADE,
    audit_run_id INTEGER REFERENCES audit_runs(id),
    status TEXT NOT NULL,
    solver TEXT,
    tool_version TEXT,
    command TEXT,
    result_summary TEXT,
    counterexample TEXT,
    evidence_json TEXT,
    started_at TEXT NOT NULL,
    finished_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS apg_nodes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    external_id TEXT NOT NULL UNIQUE,
    node_type TEXT NOT NULL,
    name TEXT,
    artifact_path TEXT,
    start_line INTEGER,
    end_line INTEGER,
    properties_json TEXT NOT NULL DEFAULT '{}',
    source_tool TEXT NOT NULL,
    source_hash TEXT,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_apg_nodes_type
    ON apg_nodes(node_type);
CREATE INDEX IF NOT EXISTS idx_apg_nodes_artifact
    ON apg_nodes(artifact_path, start_line);

CREATE TABLE IF NOT EXISTS apg_edges (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    external_id TEXT NOT NULL UNIQUE,
    source_external_id TEXT NOT NULL,
    target_external_id TEXT NOT NULL,
    edge_type TEXT NOT NULL,
    properties_json TEXT NOT NULL DEFAULT '{}',
    source_tool TEXT NOT NULL,
    source_hash TEXT,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_apg_edges_source
    ON apg_edges(source_external_id, edge_type);
CREATE INDEX IF NOT EXISTS idx_apg_edges_target
    ON apg_edges(target_external_id, edge_type);

CREATE TABLE IF NOT EXISTS waivers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    finding_id INTEGER REFERENCES findings(id),
    obligation_id INTEGER REFERENCES proof_obligations(id),
    reason TEXT NOT NULL,
    approved_by TEXT NOT NULL,
    expires_at TEXT,
    created_at TEXT NOT NULL,
    CHECK (finding_id IS NOT NULL OR obligation_id IS NOT NULL)
);

CREATE TABLE IF NOT EXISTS remediation_batches (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    batch_key TEXT NOT NULL UNIQUE,
    title TEXT NOT NULL,
    priority INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    finding_ids_json TEXT NOT NULL,
    claimed_by TEXT,
    lease_until TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
