BEGIN IMMEDIATE;
ALTER TABLE execution ADD COLUMN legacy_quarantined INTEGER NOT NULL DEFAULT 0 CHECK(legacy_quarantined IN (0,1));
-- v3 did not distinguish old snapshots from newly authorized reserved orders.
-- Fail closed for every pre-v4 snapshot; recovery may still reconcile its attempts.
UPDATE execution SET legacy_quarantined=1;
UPDATE execution SET state='requiere_intervencion',resume_requested=0
 WHERE state NOT IN ('confirmado','simulado');
ALTER TABLE suborders ADD COLUMN awaiting_resume INTEGER NOT NULL DEFAULT 0 CHECK(awaiting_resume IN (0,1));
UPDATE suborders SET awaiting_resume=1,state='requiere_intervencion'
 WHERE state='preparado' AND EXISTS (
 SELECT 1 FROM attempts a WHERE a.suborder_id=suborders.id AND a.settled=1
 AND COALESCE(json_extract(a.evidence_json,'$.status'),'') != 'confirmed');
PRAGMA user_version = 4;
COMMIT;
