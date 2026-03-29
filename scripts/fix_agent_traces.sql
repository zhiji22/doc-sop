DROP TABLE IF EXISTS agent_trace_spans;
DROP TABLE IF EXISTS agent_traces;

CREATE TABLE agent_traces (
    id            TEXT PRIMARY KEY,
    user_id       TEXT NOT NULL,
    file_id       TEXT,
    question      TEXT NOT NULL,
    agent_mode    TEXT NOT NULL DEFAULT 'react',
    status        TEXT NOT NULL DEFAULT 'running',
    total_duration_ms  INTEGER,
    total_tokens       INTEGER DEFAULT 0,
    span_count         INTEGER DEFAULT 0,
    created_at    TIMESTAMP DEFAULT NOW(),
    finished_at   TIMESTAMP
);

CREATE TABLE agent_trace_spans (
    id            TEXT PRIMARY KEY,
    trace_id      TEXT NOT NULL REFERENCES agent_traces(id) ON DELETE CASCADE,
    span_type     TEXT NOT NULL,
    name          TEXT NOT NULL,
    input_data    TEXT,
    output_data   TEXT,
    duration_ms   INTEGER,
    token_count   INTEGER DEFAULT 0,
    meta          JSONB DEFAULT '{}',
    created_at    TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_traces_user_created ON agent_traces(user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_spans_trace ON agent_trace_spans(trace_id);

