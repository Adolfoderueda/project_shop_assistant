BEGIN IMMEDIATE;
CREATE TABLE observed_products (
 id TEXT PRIMARY KEY, store_id TEXT NOT NULL, product_id TEXT NOT NULL,
 title TEXT NOT NULL, url TEXT NOT NULL, observed_on TEXT NOT NULL,
 price_cents INTEGER CHECK(price_cents >= 0),
 availability INTEGER CHECK(availability IN (0,1)), format_note TEXT
);
CREATE TABLE product_requests (
 name TEXT PRIMARY KEY, requested_on TEXT NOT NULL DEFAULT (date('now'))
);
PRAGMA user_version = 5;
COMMIT;
