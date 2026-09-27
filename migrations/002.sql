BEGIN IMMEDIATE;
CREATE TABLE IF NOT EXISTS clarifications (
 user_id INTEGER PRIMARY KEY,
 intent_json TEXT NOT NULL
);
PRAGMA user_version = 2;
COMMIT;
