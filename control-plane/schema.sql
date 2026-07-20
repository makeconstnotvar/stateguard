BEGIN;

CREATE TABLE organizations (
    id uuid PRIMARY KEY,
    key text NOT NULL UNIQUE,
    name text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE repositories (
    id uuid PRIMARY KEY,
    organization_id uuid NOT NULL REFERENCES organizations(id),
    repository_key text NOT NULL,
    display_name text NOT NULL,
    default_branch text NOT NULL DEFAULT 'main',
    tier smallint NOT NULL CHECK (tier BETWEEN 0 AND 3),
    active boolean NOT NULL DEFAULT true,
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (organization_id, repository_key)
);

CREATE TABLE components (
    id uuid PRIMARY KEY,
    repository_id uuid NOT NULL REFERENCES repositories(id) ON DELETE CASCADE,
    component_key text NOT NULL,
    kind text NOT NULL,
    owners jsonb NOT NULL DEFAULT '{}'::jsonb,
    criticality text NOT NULL DEFAULT 'medium'
      CHECK (criticality IN ('critical','high','medium','low')),
    active boolean NOT NULL DEFAULT true,
    UNIQUE (repository_id, component_key)
);

CREATE TABLE policies (
    id uuid PRIMARY KEY,
    organization_id uuid NOT NULL REFERENCES organizations(id),
    policy_key text NOT NULL,
    version text NOT NULL,
    content_sha256 text NOT NULL CHECK (length(content_sha256)=64),
    artifact_uri text,
    status text NOT NULL CHECK (status IN ('pilot','approved','deprecated','blocked')),
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (organization_id, policy_key, version)
);

CREATE TABLE analysis_runs (
    id uuid PRIMARY KEY,
    repository_id uuid NOT NULL REFERENCES repositories(id),
    idempotency_key text NOT NULL,
    run_type text NOT NULL CHECK (run_type IN ('pr','main','nightly','release','manual')),
    branch text,
    commit_sha text NOT NULL,
    policy_id uuid REFERENCES policies(id),
    policy_sha256 text NOT NULL,
    specification_sha256 text,
    mappings_sha256 text,
    source_manifest_sha256 text NOT NULL,
    toolchain jsonb NOT NULL DEFAULT '{}'::jsonb,
    status text NOT NULL CHECK (status IN ('uploading','completed','failed','superseded')),
    verdict text CHECK (verdict IN ('red','yellow','green-by-evidence','unknown')),
    started_at timestamptz NOT NULL,
    completed_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (repository_id, idempotency_key)
);

CREATE INDEX analysis_runs_current_idx
    ON analysis_runs(repository_id, run_type, completed_at DESC)
    WHERE status='completed';

CREATE TABLE run_artifacts (
    run_id uuid NOT NULL REFERENCES analysis_runs(id) ON DELETE CASCADE,
    path_hash text NOT NULL,
    artifact_sha256 text NOT NULL,
    kind text NOT NULL,
    component_key text,
    PRIMARY KEY (run_id, path_hash)
);

CREATE TABLE findings (
    id uuid PRIMARY KEY,
    repository_id uuid NOT NULL REFERENCES repositories(id),
    stable_key text NOT NULL,
    first_seen_run_id uuid NOT NULL REFERENCES analysis_runs(id),
    last_seen_run_id uuid NOT NULL REFERENCES analysis_runs(id),
    source_tool text NOT NULL,
    rule_id text NOT NULL,
    severity text NOT NULL CHECK (severity IN ('critical','high','medium','low','info')),
    confidence text NOT NULL CHECK (confidence IN ('high','medium','low')),
    category text NOT NULL,
    title text NOT NULL,
    message text NOT NULL,
    path_hash text,
    line_start integer,
    artifact_sha256 text,
    invariant_id text,
    transition_id text,
    counterexample text,
    remediation text,
    verification text,
    status text NOT NULL CHECK (status IN (
      'open','triaged','fixed-pending-verification','closed','false-positive',
      'accepted-risk','stale-evidence','not-observed','reopened'
    )),
    owner text,
    due_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (repository_id, stable_key)
);

CREATE INDEX findings_open_idx
    ON findings(repository_id, severity, status)
    WHERE status NOT IN ('closed','false-positive','accepted-risk');

CREATE TABLE run_findings (
    run_id uuid NOT NULL REFERENCES analysis_runs(id) ON DELETE CASCADE,
    finding_id uuid NOT NULL REFERENCES findings(id),
    observed boolean NOT NULL DEFAULT true,
    payload jsonb NOT NULL DEFAULT '{}'::jsonb,
    PRIMARY KEY (run_id, finding_id)
);

CREATE TABLE proof_obligations (
    id uuid PRIMARY KEY,
    repository_id uuid NOT NULL REFERENCES repositories(id),
    obligation_key text NOT NULL,
    kind text NOT NULL,
    criticality text NOT NULL CHECK (criticality IN ('critical','high','medium','low')),
    title text NOT NULL,
    description text NOT NULL,
    owner text,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (repository_id, obligation_key)
);

CREATE TABLE proof_attempts (
    id uuid PRIMARY KEY,
    run_id uuid NOT NULL REFERENCES analysis_runs(id) ON DELETE CASCADE,
    obligation_id uuid NOT NULL REFERENCES proof_obligations(id),
    result text NOT NULL CHECK (result IN (
      'pending','running','proved','verified','reviewed-ai','failed','inconclusive','waived','stale'
    )),
    evidence_class text,
    solver text,
    tool_version text,
    input_sha256 text NOT NULL,
    assumptions jsonb NOT NULL DEFAULT '[]'::jsonb,
    bounds jsonb NOT NULL DEFAULT '{}'::jsonb,
    command text,
    summary text,
    counterexample jsonb,
    evidence_uri text,
    started_at timestamptz NOT NULL,
    finished_at timestamptz
);

CREATE INDEX proof_attempts_latest_idx
    ON proof_attempts(obligation_id, finished_at DESC);

CREATE TABLE waivers (
    id uuid PRIMARY KEY,
    repository_id uuid NOT NULL REFERENCES repositories(id),
    finding_id uuid REFERENCES findings(id),
    obligation_id uuid REFERENCES proof_obligations(id),
    reason text NOT NULL,
    impact text NOT NULL,
    compensating_controls text,
    approved_by text NOT NULL,
    owner text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    expires_at timestamptz NOT NULL,
    status text NOT NULL CHECK (status IN ('proposed','approved','rejected','expired','revoked')),
    CHECK ((finding_id IS NOT NULL)::int + (obligation_id IS NOT NULL)::int = 1)
);

CREATE TABLE remediation_batches (
    id uuid PRIMARY KEY,
    repository_id uuid NOT NULL REFERENCES repositories(id),
    batch_key text NOT NULL,
    title text NOT NULL,
    priority integer NOT NULL,
    status text NOT NULL CHECK (status IN ('pending','claimed','fixed','verifying','closed','failed')),
    claimed_by text,
    fencing_token bigint NOT NULL DEFAULT 0,
    lease_until timestamptz,
    finding_ids uuid[] NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (repository_id, batch_key)
);

COMMIT;
