-- Comments table
CREATE TABLE IF NOT EXISTS comments (
    id TEXT PRIMARY KEY,
    parent_id TEXT,
    tier INTEGER NOT NULL,
    author TEXT NOT NULL,
    message TEXT NOT NULL,
    created_time TIMESTAMP NOT NULL,
    last_seen TIMESTAMP NOT NULL,
    display_order INTEGER DEFAULT 0,
    is_deleted BOOLEAN DEFAULT 0,
    post_url TEXT NOT NULL,
    FOREIGN KEY (parent_id) REFERENCES comments(id)
);

-- Index for faster queries
CREATE INDEX IF NOT EXISTS idx_parent_id ON comments(parent_id);
CREATE INDEX IF NOT EXISTS idx_post_url ON comments(post_url);
CREATE INDEX IF NOT EXISTS idx_created_time ON comments(created_time);
CREATE INDEX IF NOT EXISTS idx_display_order ON comments(display_order);
CREATE INDEX IF NOT EXISTS idx_tier ON comments(tier);

-- Posts table
CREATE TABLE IF NOT EXISTS posts (
    url TEXT PRIMARY KEY,
    group_name TEXT,
    post_id TEXT,
    author TEXT,
    content TEXT,
    first_seen TIMESTAMP NOT NULL,
    last_monitored TIMESTAMP NOT NULL
);

-- Session table
CREATE TABLE IF NOT EXISTS sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TIMESTAMP NOT NULL,
    expires_at TIMESTAMP,
    is_active BOOLEAN DEFAULT 1
);
