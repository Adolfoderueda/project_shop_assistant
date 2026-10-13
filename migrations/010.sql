BEGIN IMMEDIATE;
ALTER TABLE inbox ADD COLUMN kind TEXT NOT NULL DEFAULT 'message'
 CHECK(kind IN ('message','callback'));
ALTER TABLE inbox ADD COLUMN payload_json TEXT CHECK(payload_json IS NULL OR json_valid(payload_json));
ALTER TABLE inbox ADD COLUMN callback_query_id TEXT;
ALTER TABLE inbox ADD COLUMN callback_ack_state TEXT
 CHECK(callback_ack_state IS NULL OR callback_ack_state IN ('pending','sent','expired'));
CREATE UNIQUE INDEX inbox_callback_query ON inbox(callback_query_id)
 WHERE callback_query_id IS NOT NULL;
CREATE TRIGGER inbox_event_insert BEFORE INSERT ON inbox
 WHEN (NEW.kind='message' AND (NEW.callback_query_id IS NOT NULL OR NEW.callback_ack_state IS NOT NULL))
 OR (NEW.kind='callback' AND (NEW.text!='' OR NEW.payload_json IS NULL
 OR NEW.callback_query_id IS NULL OR length(NEW.callback_query_id)=0 OR NEW.callback_ack_state IS NULL))
 BEGIN SELECT RAISE(ABORT,'invalid inbox event'); END;
CREATE TRIGGER inbox_event_update BEFORE UPDATE ON inbox
 WHEN (NEW.kind='message' AND (NEW.callback_query_id IS NOT NULL OR NEW.callback_ack_state IS NOT NULL))
 OR (NEW.kind='callback' AND (NEW.text!='' OR NEW.payload_json IS NULL
 OR NEW.callback_query_id IS NULL OR length(NEW.callback_query_id)=0 OR NEW.callback_ack_state IS NULL))
 BEGIN SELECT RAISE(ABORT,'invalid inbox event'); END;
CREATE TABLE guided_questions (
 id TEXT NOT NULL, version INTEGER NOT NULL CHECK(version>0),
 user_id INTEGER NOT NULL, chat_id INTEGER NOT NULL,
 source_update_id INTEGER NOT NULL REFERENCES inbox(update_id),
 notice_id TEXT NOT NULL REFERENCES outbox(id),
 question_json TEXT NOT NULL CHECK(json_valid(question_json)),
 PRIMARY KEY(id,version)
);
CREATE UNIQUE INDEX guided_active_question ON guided_questions(user_id,chat_id)
 WHERE json_extract(question_json,'$.status')='active';
CREATE TABLE guided_topics (
 id TEXT NOT NULL, version INTEGER NOT NULL CHECK(version>0),
 user_id INTEGER NOT NULL, chat_id INTEGER NOT NULL,
 source_update_id INTEGER NOT NULL REFERENCES inbox(update_id),
 topic_json TEXT NOT NULL CHECK(json_valid(topic_json)), PRIMARY KEY(id,version)
);
CREATE TABLE guided_tokens (
 token TEXT PRIMARY KEY CHECK(length(token)=24 AND substr(token,1,2)='q:'
 AND substr(token,3) NOT GLOB '*[^A-Za-z0-9_-]*'),
 user_id INTEGER NOT NULL, chat_id INTEGER NOT NULL,
 question_id TEXT NOT NULL, question_version INTEGER NOT NULL,
 choice_index INTEGER NOT NULL CHECK(choice_index>=0),
 notice_id TEXT NOT NULL REFERENCES outbox(id),
 consumed_update_id INTEGER REFERENCES inbox(update_id),
 result_json TEXT CHECK(result_json IS NULL OR json_valid(result_json)),
 FOREIGN KEY(question_id,question_version) REFERENCES guided_questions(id,version),
 CHECK((consumed_update_id IS NULL)=(result_json IS NULL))
);
CREATE TABLE telegram_deliveries (
 notice_id TEXT NOT NULL REFERENCES outbox(id), chat_id INTEGER NOT NULL,
 message_id INTEGER NOT NULL CHECK(message_id>0), digest TEXT NOT NULL CHECK(length(digest)>0),
 PRIMARY KEY(notice_id,chat_id,message_id)
);
PRAGMA user_version = 10;
COMMIT;
