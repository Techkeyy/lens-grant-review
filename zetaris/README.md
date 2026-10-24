# Lens ↔ Zetaris live demo source

**Status, 24 October 2026:** the user's AWS-backed Zetaris Mini cluster is **Active**. All five synthetic Lens CSVs were uploaded to NDP File System and registered in `LENS_DEMO_FILES`. A live read-only snapshot returned all 21 rows: 4 timesheets, 1 receipt, 8 activities, and 4 rows from each draft. A local HTTP import followed by a check produced a source-linked `OVERALLOCATED_SOURCE` finding; Meterless stored the source and finding events. Keep the cluster running only while it is needed for the demo, since its AWS resources use Free plan credits.

## Verified API contract

Lens uses the **web UI proxy**, matching Zetaris's current [`query_zetaris.py`](https://github.com/zetaris/getting-started/blob/main/scripts/query_zetaris.py) and [`zetaris_api.py`](https://github.com/zetaris/getting-started/blob/main/scripts/zetaris_api.py):

- `ZETARIS_BASE_URL` is the web UI **origin** (local example `http://localhost:3000`), not the direct REST API base at `/api/v1.0`.
- A read request posts to `/api/proxy/sql-editor/sqls/run-query` with JSON `{"sql": "...", "limit": 1000}` and optional `engineId`.
- Headers carry `Authorization: Bearer <API key>`, numeric `X-Org-ID`, and a fresh UUID `X-Request-ID`.
- The client accepts the official positional `data` arrays, preserving them without invented column names. If a response includes valid string `headers`, it maps arrays to dictionaries. Missing or malformed result data is an error.
- Lens permits its fixed `SELECT` queries and the `SHOW LIGHTNING DATABASES` preflight. The Zetaris account should also have read-only privileges. This code does not create or modify remote objects.

The [official client setup](https://github.com/zetaris/getting-started/blob/main/docs/connections/client-setup.md) distinguishes UI proxy from direct REST and explains where to create the API key and find the numeric organisation ID. The earlier Lens client used `ZETARIS_SQL_URL` and `ZETARIS_BEARER_TOKEN` with an incomplete `{"sql": "..."}` body; those settings are obsolete here.

## Five-file onboarding recipe

The source files are labelled synthetic examples in `examples/`:

| File | Columns selected by Lens (exact names) | Registered table in this instance |
| --- | --- | --- |
| `timesheets.csv` | `source_id`, `person`, `date`, `hours`, `project_note` | `LENS_DEMO_FILES.timesheets` |
| `receipts.csv` | `source_id`, `vendor`, `date`, `amount_usd`, `description` | `LENS_DEMO_FILES.receipts` |
| `activity_log.csv` | `source_id`, `date`, `activity` | `LENS_DEMO_FILES.acivity_log` |
| `reading_futures_draft.csv` | `claim_id`, `grant`, `kind`, `source_id`, `quantity`, `unit`, `description` | `LENS_DEMO_FILES.reading_future_drafts` |
| `community_learning_draft.csv` | same seven claim columns | `LENS_DEMO_FILES.community_learning_drafts` |

The registered names above were verified with read-only `SHOW LIGHTNING TABLES LENS_DEMO_FILES`; they include spelling/plural differences from the filenames. Lens maps them in ignored `.env.local`. Do not rename the cloud tables merely to align the labels.

### Preferred: upload through NDP File System

Zetaris's [local CSV/JSON guide](https://kbase.zetaris.com/knowledge/how-to-ccnnect-to-json-from-local-machine) documents this path. The [file system overview](https://kbase.zetaris.com/knowledge/file-system-overview) confirms that uploaded CSVs must then be registered as file sources before SQL can query them. In the user's cloud UI, **NDP File System → `file-store`** is visible. The following registration labels come from Zetaris's guide; confirm them against the current cloud UI before creating sources.

1. In **NDP File System**, open `file-store`, create a folder named `lens-demo`, and open it. Upload the five files from the local [`examples/`](../examples/) folder. Keep each original filename. Confirm that all five appear in `file-store/lens-demo` before registering anything. These files are synthetic; do not upload real charity data for this demo.
2. Open **SQL Workspace**. Zetaris's guide shows a `+` beside **Virtual File Sources** to create a container, then a `+` beside that container to add each file. Name the container `LENS_DEMO_FILES` if the UI accepts that name. For each file, choose **File Store**, select the uploaded file from `lens-demo`, and create the corresponding table in the table above. Set the format to CSV, treat the first row as headers, and check the inferred field names and types before completing each registration. Repeat for all five files.
3. The cloud UI may instead place creation under **Data Explorer → File Source & API** or label the container differently. If **Virtual File Sources**, **File Store**, CSV header, or the expected table names are absent, stop at that screen and inspect its labels before proceeding. Do not create a source by guessing which storage option or format to select. If `LENS_DEMO_FILES` cannot be used, record the actual `database.table` names and update all five `ZETARIS_*_TABLE` settings in `.env.local` accordingly.
4. Preview every registered table in Zetaris, then run the five separate checks in [`sql/lens_select.sql`](sql/lens_select.sql) in SQL Workspace. Each must return the expected source IDs and rows. Confirm `hours`, `amount_usd`, and `quantity` can be read as numbers; a completed upload or table creation alone does not prove Lens can query them. If the UI chose a different container name, adjust the check queries to match it.

[`sql/lens_public_s3_create.sql.template`](sql/lens_public_s3_create.sql.template) is an **optional, unrun public-S3 fallback**. Its syntax follows Zetaris's [CSV cookbook](https://github.com/zetaris/getting-started/blob/main/open_data/parquet_csv/HOWTO.md) and [confirmed NOAA CSV example](https://github.com/zetaris/getting-started/blob/main/open_data/parquet_csv/sql/02_noaa_ghcn_create.sql). It requires an intentionally public bucket and reviewed bucket/region substitutions. Its `isS3BucketPublic` option is unsuitable for a private bucket; do not run that template against the user's private workspace bucket. Local Desktop paths are not visible to Zetaris automatically.

To use the now-running instance for Lens:

1. Follow the NDP upload and registration steps above. Check every table in SQL Workspace before using Lens.
2. Copy [`.env.example`](../.env.example) to an ignored `.env.local` at the Lens root and fill the values below, or set the same variables in the process environment. Lens loads `.env.local` without printing its values. Keep the API key out of Git, prompts, screenshots, and logs. If `.env.local` already exists, update only the five table names after registration; leave its credential values intact.
3. Run `python -m zetaris.smoke` from the Lens root. It checks `SELECT 1`, `SHOW LIGHTNING DATABASES`, the staff-hours join across both reports, the receipt allocation join across both reports, and the activity count. Returned rows and request IDs would prove **live connectivity and diagnostic cross-source queries only**.
4. Restart `python app.py` with the environment variables set, then use **Import registered Zetaris tables** in Lens. This reads every row from all five configured grant tables, including unmatched claims. A count query runs before and after each table read. Missing tables, empty/partial responses, duplicate IDs, and tables beyond the configured limit fail closed. The captured CSV snapshots, table names, primary keys, per-table SHA-256 hashes, and Zetaris query request IDs are saved in the local review; the app never writes to Zetaris. Confirm activity links in the Lens UI before checking, because the example activity log does not itself identify a grant.
5. A count check is not a cross-table transaction. Keep all five tables static during the import and reimport after any source change. The snapshot hash identifies the rows Lens read, **not a native Zetaris table version or original CSV line number**. Lens labels those locations as Zetaris table/key plus the snapshot hash.

```text
ZETARIS_BASE_URL=https://YOUR-UI-ORIGIN
ZETARIS_ORG_ID=<numeric ID from Management > Organisation>
ZETARIS_API_KEY=<key created in Management > API Tokens>
ZETARIS_QUERY_LIMIT=1000
ZETARIS_ENGINE_ID=<optional compute engine ID>
ZETARIS_TIMESHEETS_TABLE=LENS_DEMO_FILES.timesheets
ZETARIS_RECEIPTS_TABLE=LENS_DEMO_FILES.receipts
ZETARIS_ACTIVITY_TABLE=LENS_DEMO_FILES.acivity_log
ZETARIS_REPORT_A_TABLE=LENS_DEMO_FILES.reading_future_drafts
ZETARIS_REPORT_B_TABLE=LENS_DEMO_FILES.community_learning_drafts
```

`run_lens_diagnostics(...)` in `lens_adapter.py` still returns aggregate result sets with `review_eligible: false`. The app path uses `read_lens_snapshot(...)` in `raw_evidence.py` instead. It selects complete identified rows from each registered table, then lets Lens's existing deterministic core calculate findings from that captured snapshot. The aggregate queries remain diagnostics only: inner joins omit unmatched claims and activity counts lack grant/period scope. `python -m unittest zetaris.test_client zetaris.test_raw_evidence -q` tests the client and snapshot handling locally. On 24 October, `python -m zetaris.smoke` also returned live cross-source staff and receipt aggregates and the activity count; the full HTTP import and check were verified against the live tables in an isolated local state directory.

## Demo operation and cleanup

The user keeps the API key and numeric organisation ID locally in `.env.local`; never paste the key in chat or commit it. Use the cluster's **AI Data Gateway URL** as `ZETARIS_BASE_URL`, not `cloud.enterprise.zetaris.com`. Run the app's **Import registered Zetaris tables** action and check while the cluster is active. Reimport after changing any registered source. Suspend the cluster after filming to conserve AWS Free plan credits; the NAT gateway from the AWS account stack continues to accrue AWS charges until the stack is deleted.
