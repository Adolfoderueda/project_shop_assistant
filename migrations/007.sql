BEGIN IMMEDIATE;
CREATE TABLE presentation_jobs (
 update_id INTEGER PRIMARY KEY REFERENCES inbox(update_id),
 user_id INTEGER NOT NULL,
 chat_id INTEGER NOT NULL,
 snapshot_json TEXT NOT NULL,
 created_at TEXT NOT NULL
);
PRAGMA user_version = 7;
COMMIT;
