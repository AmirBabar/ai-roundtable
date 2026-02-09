-- ============================================================
-- COUNCIL MEMORY ARCHITECTURE - COMPLETE SCHEMA
-- Option 3.5: Accelerated Hybrid with Supermemory Patterns
-- ============================================================

PRAGMA journal_mode = WAL;
PRAGMA synchronous = NORMAL;
PRAGMA foreign_keys = ON;
PRAGMA busy_timeout = 5000;
PRAGMA temp_store = MEMORY;
PRAGMA cache_size = -64000;

-- ============================================================
-- LAYER 0: RAW EVENTS (Enhanced existing table)
-- ============================================================

CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL DEFAULT (datetime('now')),
    session_id TEXT NOT NULL,
    event_type TEXT NOT NULL CHECK (event_type IN (
        'user_input', 'agent_response', 'debate_turn',
        'vote_cast', 'decision_rendered', 'system_event'
    )),
    agent_name TEXT,
    content TEXT NOT NULL,
    metadata JSON,
    processed_to_l1 INTEGER DEFAULT 0,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_events_session ON events(session_id);
CREATE INDEX IF NOT EXISTS idx_events_timestamp ON events(timestamp);
CREATE INDEX IF NOT EXISTS idx_events_processed ON events(processed_to_l1);
CREATE INDEX IF NOT EXISTS idx_events_type ON events(event_type);

-- ============================================================
-- LAYER 1: ATOMIC FACTS
-- ============================================================

CREATE TABLE IF NOT EXISTS atomic_facts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fact_id TEXT UNIQUE NOT NULL,
    content TEXT NOT NULL,
    category TEXT NOT NULL CHECK (category IN (
        'user_preference', 'project_context', 'decision_made',
        'technical_constraint', 'relationship', 'goal',
        'learned_pattern', 'correction'
    )),
    confidence REAL DEFAULT 1.0 CHECK (confidence >= 0 AND confidence <= 1),
    source_event_ids JSON NOT NULL,
    embedding BLOB,
    first_observed TEXT NOT NULL DEFAULT (datetime('now')),
    last_confirmed TEXT NOT NULL DEFAULT (datetime('now')),
    observation_count INTEGER DEFAULT 1,
    is_active INTEGER DEFAULT 1,
    superseded_by TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_facts_category ON atomic_facts(category);
CREATE INDEX IF NOT EXISTS idx_facts_active ON atomic_facts(is_active);
CREATE INDEX IF NOT EXISTS idx_facts_confidence ON atomic_facts(confidence);
CREATE INDEX IF NOT EXISTS idx_facts_last_confirmed ON atomic_facts(last_confirmed);

-- ============================================================
-- LAYER 1.5: CONFLICT RESOLUTION LOG
-- ============================================================

CREATE TABLE IF NOT EXISTS fact_conflicts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    old_fact_id TEXT NOT NULL,
    new_fact_id TEXT NOT NULL,
    conflict_type TEXT NOT NULL CHECK (conflict_type IN (
        'contradiction', 'update', 'refinement', 'correction'
    )),
    resolution TEXT NOT NULL CHECK (resolution IN (
        'new_supersedes', 'old_retained', 'merged', 'both_valid'
    )),
    resolution_reason TEXT,
    resolved_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (old_fact_id) REFERENCES atomic_facts(fact_id),
    FOREIGN KEY (new_fact_id) REFERENCES atomic_facts(fact_id)
);

-- ============================================================
-- LAYER 2: CATEGORY SUMMARIES
-- ============================================================

CREATE TABLE IF NOT EXISTS category_summaries (
    category TEXT PRIMARY KEY,
    summary TEXT NOT NULL,
    fact_count INTEGER DEFAULT 0,
    key_facts JSON,
    last_synthesized TEXT DEFAULT (datetime('now')),
    synthesis_version INTEGER DEFAULT 1,
    token_count INTEGER,
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now'))
);

-- ============================================================
-- SCRIBE PROCESSING QUEUE
-- ============================================================

CREATE TABLE IF NOT EXISTS scribe_queue (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id INTEGER NOT NULL,
    priority INTEGER DEFAULT 5 CHECK (priority >= 1 AND priority <= 10),
    status TEXT DEFAULT 'pending' CHECK (status IN (
        'pending', 'processing', 'completed', 'failed', 'skipped'
    )),
    attempts INTEGER DEFAULT 0,
    last_attempt TEXT,
    error_message TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (event_id) REFERENCES events(id)
);

CREATE INDEX IF NOT EXISTS idx_queue_status ON scribe_queue(status, priority);

-- ============================================================
-- SANITIZATION RULES
-- ============================================================

CREATE TABLE IF NOT EXISTS sanitization_rules (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    rule_name TEXT UNIQUE NOT NULL,
    pattern TEXT NOT NULL,
    replacement TEXT DEFAULT '[REDACTED]',
    category TEXT NOT NULL CHECK (category IN (
        'pii', 'credential', 'path', 'internal', 'custom'
    )),
    is_active INTEGER DEFAULT 1,
    created_at TEXT DEFAULT (datetime('now'))
);

-- Pre-populate sanitization rules
INSERT OR IGNORE INTO sanitization_rules (rule_name, pattern, replacement, category) VALUES
    ('email', '\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', '[EMAIL]', 'pii'),
    ('phone', '\b\d{3}[-.]?\d{3}[-.]?\d{4}\b', '[PHONE]', 'pii'),
    ('ssn', '\b\d{3}-\d{2}-\d{4}\b', '[SSN]', 'pii'),
    ('api_key', '\b(api[_-]?key|apikey)[\s:=]+[\w-]{20,}', '[API_KEY]', 'credential'),
    ('password', '\b(password|passwd|pwd)[\s:=]+[^\s]{4,}', '[PASSWORD]', 'credential'),
    ('windows_path', '[A-Za-z]:\\[\w\\.-]+', '[PATH]', 'path'),
    ('unix_path', '(/[\w.-]+){3,}', '[PATH]', 'path');

-- ============================================================
-- MEMORY ACCESS LOG
-- ============================================================

CREATE TABLE IF NOT EXISTS memory_access_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    access_type TEXT NOT NULL CHECK (access_type IN (
        'context_injection', 'fact_query', 'summary_read', 'full_recall'
    )),
    session_id TEXT,
    facts_retrieved INTEGER,
    tokens_used INTEGER,
    latency_ms INTEGER,
    accessed_at TEXT DEFAULT (datetime('now'))
);

-- ============================================================
-- VIEWS FOR COMMON QUERIES
-- ============================================================

CREATE VIEW IF NOT EXISTS v_active_facts AS
SELECT fact_id, content, category, confidence, first_observed,
       observation_count, created_at
FROM atomic_facts
WHERE is_active = 1
ORDER BY category, last_confirmed DESC;

CREATE VIEW IF NOT EXISTS v_scribe_queue_status AS
SELECT
    COUNT(*) as pending_events,
    MIN(timestamp) as oldest_event,
    MAX(timestamp) as newest_event
FROM events
WHERE processed_to_l1 = 0;

-- ============================================================
-- MIGRATION TRACKING
-- ============================================================

CREATE TABLE IF NOT EXISTS schema_migrations (
    migration_id INTEGER PRIMARY KEY AUTOINCREMENT,
    version TEXT NOT NULL UNIQUE,
    applied_at TEXT NOT NULL DEFAULT (datetime('now')),
    description TEXT
);

INSERT OR IGNORE INTO schema_migrations (version, description)
VALUES ('1.0.0', 'Council Memory Architecture - Option 3.5 Accelerated Hybrid');
