BEGIN IMMEDIATE;
CREATE TABLE IF NOT EXISTS agent_proposals (
 user_id INTEGER NOT NULL, chat_id INTEGER NOT NULL, proposal_json TEXT NOT NULL,
 PRIMARY KEY(user_id,chat_id)
);
CREATE TABLE IF NOT EXISTS conversation_routes (
 user_id INTEGER NOT NULL, chat_id INTEGER NOT NULL,
 route TEXT NOT NULL CHECK(route IN ('legacy','agent')),
 command_update_id INTEGER REFERENCES inbox(update_id),
 PRIMARY KEY(user_id,chat_id)
);
PRAGMA user_version = 9;
COMMIT;
