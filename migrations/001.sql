BEGIN IMMEDIATE;
CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value INTEGER NOT NULL);
INSERT OR IGNORE INTO meta VALUES ('telegram_offset', 0);
CREATE TABLE IF NOT EXISTS products (id TEXT PRIMARY KEY, rule_json TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS inbox (
 update_id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL, chat_id INTEGER NOT NULL,
 text TEXT NOT NULL, completed INTEGER NOT NULL DEFAULT 0, reply_json TEXT
);
CREATE TABLE IF NOT EXISTS list_lines (
 id TEXT PRIMARY KEY, product_id TEXT REFERENCES products(id), description TEXT NOT NULL,
 quantity INTEGER CHECK(quantity > 0), revision INTEGER NOT NULL CHECK(revision > 0),
 source_update_id INTEGER NOT NULL REFERENCES inbox(update_id)
);
CREATE TABLE IF NOT EXISTS orders (
 id TEXT PRIMARY KEY, mode TEXT NOT NULL CHECK(mode IN ('dry_run','live')),
 source_update_id INTEGER UNIQUE NOT NULL REFERENCES inbox(update_id),
 created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);
CREATE TABLE IF NOT EXISTS order_lines (
 order_id TEXT NOT NULL REFERENCES orders(id), position INTEGER NOT NULL,
 line_json TEXT NOT NULL, PRIMARY KEY(order_id, position)
);
CREATE TRIGGER IF NOT EXISTS immutable_orders_update BEFORE UPDATE ON orders
 BEGIN SELECT RAISE(ABORT, 'immutable order'); END;
CREATE TRIGGER IF NOT EXISTS immutable_orders_delete BEFORE DELETE ON orders
 BEGIN SELECT RAISE(ABORT, 'immutable order'); END;
CREATE TRIGGER IF NOT EXISTS immutable_order_lines_update BEFORE UPDATE ON order_lines
 BEGIN SELECT RAISE(ABORT, 'immutable snapshot'); END;
CREATE TRIGGER IF NOT EXISTS immutable_order_lines_delete BEFORE DELETE ON order_lines
 BEGIN SELECT RAISE(ABORT, 'immutable snapshot'); END;
CREATE TABLE IF NOT EXISTS suborders (
 id TEXT PRIMARY KEY, order_id TEXT NOT NULL REFERENCES orders(id), store_id TEXT NOT NULL,
 state TEXT NOT NULL CHECK(state IN ('pendiente_datos','buscando','preparado','enviando',
 'confirmado','requiere_intervencion','resultado_incierto','fallido','cancelado')),
 result TEXT CHECK(result IN ('simulado','confirmado')), quote_json TEXT,
 total_cents INTEGER CHECK(total_cents >= 0), external_id TEXT,
 UNIQUE(order_id, store_id)
);
CREATE TABLE IF NOT EXISTS attempts (
 id TEXT PRIMARY KEY, suborder_id TEXT NOT NULL REFERENCES suborders(id),
 fingerprint TEXT NOT NULL, evidence_json TEXT,
 created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);
CREATE TABLE IF NOT EXISTS events (
 id INTEGER PRIMARY KEY, suborder_id TEXT REFERENCES suborders(id), kind TEXT NOT NULL,
 payload_json TEXT NOT NULL,
 created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);
CREATE TABLE IF NOT EXISTS outbox (
 id TEXT PRIMARY KEY, update_id INTEGER UNIQUE REFERENCES inbox(update_id),
 chat_id INTEGER NOT NULL, reply_json TEXT NOT NULL, sent_at TEXT,
 created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);
PRAGMA user_version = 1;
COMMIT;
