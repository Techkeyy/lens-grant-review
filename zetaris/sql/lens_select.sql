-- Run each statement separately after confirming registration. These are the
-- five data checks before any join or Lens integration claim.
SELECT source_id, person, hours FROM LENS_DEMO_FILES.timesheets LIMIT 5;
SELECT source_id, vendor, amount_usd FROM LENS_DEMO_FILES.receipts LIMIT 5;
SELECT source_id, date, activity FROM LENS_DEMO_FILES.acivity_log LIMIT 10;
SELECT claim_id, kind, source_id, quantity, unit FROM LENS_DEMO_FILES.reading_future_drafts LIMIT 10;
SELECT claim_id, kind, source_id, quantity, unit FROM LENS_DEMO_FILES.community_learning_drafts LIMIT 10;

-- Expected synthetic source IDs: TS-101/TS-102 in timesheets and RC-201 in
-- receipts. The final cross-source SELECTs are generated in smoke.py from the
-- configured table names, and must return actual instance rows.
