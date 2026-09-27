BEGIN IMMEDIATE;
CREATE TABLE execution (
 order_id TEXT PRIMARY KEY REFERENCES orders(id),
 state TEXT NOT NULL DEFAULT 'pendiente', claimed INTEGER NOT NULL DEFAULT 0,
 resume_requested INTEGER NOT NULL DEFAULT 0, requests_json TEXT
);
-- Pre-checkout orders had no reservations: do not automatically execute them.
INSERT INTO execution(order_id,state) SELECT id,'requiere_intervencion' FROM orders;
CREATE TABLE reservations (
 line_id TEXT PRIMARY KEY, order_id TEXT NOT NULL REFERENCES orders(id)
);
INSERT OR IGNORE INTO reservations(line_id,order_id)
 SELECT json_extract(line_json,'$.id'),order_id FROM order_lines ORDER BY rowid;
ALTER TABLE attempts ADD COLUMN cart_json TEXT;
ALTER TABLE attempts ADD COLUMN settled INTEGER NOT NULL DEFAULT 0;
PRAGMA user_version = 3;
COMMIT;
