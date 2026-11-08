CREATE TABLE
    run (
        singleton INTEGER PRIMARY KEY CHECK (singleton = 1),
        identity TEXT NOT NULL,
        config TEXT NOT NULL,
        provenance TEXT NOT NULL,
        status TEXT NOT NULL,
        started_at TEXT,
        finished_at TEXT,
        primary_error TEXT,
        cleanup_errors TEXT NOT NULL DEFAULT '[]'
    );

CREATE TABLE
    state (
        key TEXT PRIMARY KEY,
        value TEXT,
        revision INTEGER NOT NULL CHECK (revision > 0),
        writer TEXT NOT NULL,
        invocation_id TEXT NOT NULL,
        operation_id TEXT NOT NULL,
        updated_at TEXT NOT NULL
    );

CREATE TABLE
    events (
        sequence INTEGER PRIMARY KEY AUTOINCREMENT,
        created_at TEXT NOT NULL,
        kind TEXT NOT NULL,
        details TEXT NOT NULL
    );

CREATE TABLE
    operations (
        operation_id TEXT PRIMARY KEY,
        payload TEXT NOT NULL,
        result TEXT NOT NULL
    );

CREATE TABLE
    debates (
        manager_id TEXT PRIMARY KEY,
        invocation_id TEXT NOT NULL,
        debate_id TEXT NOT NULL,
        generation INTEGER NOT NULL,
        outcome TEXT NOT NULL,
        round_number INTEGER NOT NULL DEFAULT 0,
        opening_sequence INTEGER NOT NULL
    );

CREATE TABLE
    rounds (
        manager_id TEXT NOT NULL,
        generation INTEGER NOT NULL,
        round_number INTEGER NOT NULL,
        contributions TEXT NOT NULL,
        snapshot_sequence INTEGER NOT NULL,
        PRIMARY KEY (manager_id, generation, round_number)
    );

CREATE TABLE
    artifacts (
        kind TEXT PRIMARY KEY,
        relative_path TEXT NOT NULL,
        sha256 TEXT NOT NULL,
        byte_length INTEGER NOT NULL,
        state_sequence INTEGER NOT NULL
    );
