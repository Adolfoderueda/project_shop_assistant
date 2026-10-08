BEGIN IMMEDIATE;
CREATE TABLE dialogue_state (
 user_id INTEGER, chat_id INTEGER, state_json TEXT NOT NULL,
 PRIMARY KEY(user_id, chat_id)
);
-- Undated legacy questions must not acquire a fresh contextual permission.
DELETE FROM clarifications;
PRAGMA user_version = 6;
COMMIT;
