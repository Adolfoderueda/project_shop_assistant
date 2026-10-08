BEGIN;
-- Only old conversational permission expires; saved products and prepared v1
-- presentations remain intact. A closed reply now needs a fresh request:
-- "El contexto anterior ha caducado; repite la petición".
DELETE FROM dialogue_state;
PRAGMA user_version = 8;
COMMIT;
