# Lens

Lens helps a small charity's grant reviewer check two draft funder reports against timesheets, receipts, and activity records before those reports go out.

> "Do the hours, costs, and workshops in these reports have the records to support them?"

Lens is a local review workspace for the Open Agent Hackathon 2026, Track 02, *The Agent That Can Explain Why*. It raises questions for a person to investigate. It does not certify compliance, detect fraud, or submit a report to a funder.

## Why shared allocation matters

A four-hour timesheet entry charged as four hours to each of two grants needs review: the claims total eight hours against one four-hour source. A two-hour allocation to each grant can be valid. The same distinction applies to a receipt split between grants. Lens uses stable source IDs and source locations to show the calculation. Similar names without a reliable link stay in review rather than becoming an invented match.

## Current workflow

1. **Import** two draft report CSVs, a timesheet CSV, a receipts CSV, and an activity log CSV. Lens validates the supported fields and keeps row locations.
2. **Link** ambiguous report claims or activity records to their sources through the interface. Lens does not silently choose a person or source.
3. **Check** both reports. Deterministic reconciliation compares each claim with the source and totals allocations across grants. Lens then selects one bounded follow-up: an overallocated timesheet prompts a reread of the timesheet and both draft reports; otherwise an activity support gap prompts a reread of the activity register. The reread is compared with the original import snapshot, never with a locally edited claim.
4. **Review** questions beside the affected claims, source rows, and arithmetic. The selected follow-up shows its reason, table names, source references, request IDs, outcome, and next human question. Open **Inspect the investigation steps** for the executed timeline. A changed or unavailable Zetaris source cannot be live-confirmed and should be reimported. Local CSV reviews are labelled snapshot-only. A workshop gap means supplied evidence is missing; it does not prove the workshop never happened.
5. **Correct or explain** a finding, then rerun. Lens saves the review in local SQLite and records source, finding, and human-decision events in the Meterless World Model reference runtime. An explanation is a human note, not an automatic clearance.
6. **Reopen or export** the saved review. The current check's execution trace remains in local SQLite and is included in the internal JSON export; a rerun replaces the previous check steps while retaining the import steps.

The included [sample case](examples/synthetic_case.json) is synthetic and labelled as such in the interface. It includes an overallocated timesheet, valid proportional splits, and an activity evidence gap.

The timeline captures steps only when they run; it is not a model thought log. The planner is deterministic and chooses one allowlisted follow-up from current findings, with no model-authored SQL or automatic source linking. Reviews saved before the timeline was added will show new check steps after a rerun, but need a fresh Zetaris import to show import query receipts. A fresh import replaces the current local review; export anything you want to keep first.

## Run locally on Windows

Requirements: Python 3.11 or newer and Node.js 24. No Python packages or npm packages need to be installed for the current local path. Node's built-in TypeScript type transform is used by the Meterless bridge.

From a PowerShell terminal in the project folder:

```powershell
python --version
node --version
python app.py
```

Open `http://127.0.0.1:8765` and choose **Load sample case**. Then check both reports, open a finding, correct the duplicated time allocation, rerun, refresh, and reopen the saved review. To use your own supported CSVs, upload the five files shown in the form. The [sample CSVs](examples/) show the required columns. Loading a different case replaces the current local review, so export a review you want to retain first.

In local mode, records and review history are written under `data/`, which Git ignores. The legacy local review remains single-user and binds only to `127.0.0.1`. The backend also supports separate named reviews. A public bind requires configured Supabase authentication and per-account storage. Google sign-in and the saved-review interface are implemented locally; the deployed two-account journey still requires UAT. Do not put real charity or donor records into a publicly reachable instance until the public user flow and privacy controls pass UAT.

## Public review backend (under development)

The public backend verifies each bearer token with Supabase Auth, derives the owner ID from that response, and stores each named review in Supabase Postgres. Review JSON and Meterless event history are saved in the same row, so an ephemeral web host can restore both after sleep or redeploy. An `owner_id` filter is applied to every server read and update. Browser roles have no direct table privileges or Row Level Security policies, preventing them from replacing saved state outside the Lens API. Writes use a row version check so a stale tab receives a conflict instead of silently overwriting a newer review. The service-role key remains server-only.

The database schema is [docs/lens_reviews.sql](docs/lens_reviews.sql). Set `SUPABASE_URL`, `SUPABASE_ANON_KEY`, and `SUPABASE_SERVICE_ROLE_KEY` in the private server environment. `GET /api/config` returns only the URL and browser-safe anon key; it never returns the service-role key. Public API calls require `Authorization: Bearer <Supabase access token>`. `GET /api/reviews` lists the authenticated account's reviews; `POST /api/reviews` with `{ "title": "..." }` creates one. `GET /api/state`, `/api/integrations`, and `/api/export` take `review_id` in the query string; existing POST actions take it in the JSON body. Other accounts' review IDs return 404. The public service caps each account at 5 saved reviews, five CSV files at 100 KB combined and 200 data rows per file, and each review with its Meterless history at 750 KB. Import/check actions are limited to 12 per account and 60 globally per five minutes in the one server process; a second import or check on the same review receives 409. Meterless and Zetaris calls each run one at a time to bound memory use. Rate and busy limits return 429; size limits return 413. These in-process limits are sized for one free Render instance, not a distributed deployment. The public Zetaris demo import is restricted to the account ID configured as `LENS_ZETARIS_DEMO_OWNER_ID` and uses only the owner's synthetic tables. See [the public deployment plan](docs/PUBLIC_DEPLOYMENT.md) and [UAT plan](docs/PUBLIC_UAT.md); neither document proves deployment has happened.

## Test and sponsor proof

From the project root:

```powershell
python -m unittest discover -s tests -v
python -m unittest zetaris.test_client zetaris.test_raw_evidence -v
```

From `meterless/`:

```powershell
npm test
npm run proof
$env:WORLD_MODEL_IMPL=(Resolve-Path .\meterless\vendor\src\index.ts).Path
node --experimental-transform-types .\vendor\conformance\runner.ts
```

The Python tests cover reconciliation, the HTTP journey, and the bounded investigator's branch choice, stale-source abstention, and unavailable-source behavior. The Meterless tests exercise real reference-runtime state across independent processes. Live Zetaris evidence is described separately from local tests. See [Meterless details](meterless/README.md) and [Zetaris setup](zetaris/README.md) for the integration paths and exact proof commands.

Zetaris requires five registered Lens grant tables and these local environment variables: `ZETARIS_BASE_URL` (the cluster UI origin), `ZETARIS_API_KEY`, numeric `ZETARIS_ORG_ID`, `ZETARIS_TIMESHEETS_TABLE`, `ZETARIS_RECEIPTS_TABLE`, `ZETARIS_ACTIVITY_TABLE`, `ZETARIS_REPORT_A_TABLE`, and `ZETARIS_REPORT_B_TABLE`. Keep the key out of Git. After registration, run `python -m zetaris.smoke` for aggregate diagnostics, then use **Import registered Zetaris tables** in the app to capture complete identified rows. Any missing or partial table read prevents import. See [Zetaris setup](zetaris/README.md) for the registration and read path.

**Status as of 24 October 2026:** The local interface, deterministic checks, SQLite review state, and Meterless reference-runtime bridge work. The user's AWS-backed Zetaris Mini cluster hosts all five synthetic Lens CSVs as registered file tables. A live read-only import returned 4 timesheets, 1 receipt, 8 activities, and 4 rows from each of the two report drafts. Through the local HTTP app, that import and a subsequent check produced an `OVERALLOCATED_SOURCE` finding linked to `LENS_DEMO_FILES.timesheets`, a source key, and a snapshot hash; Meterless ingested the records and finding. A later isolated live HTTP run verified the adaptive follow-up: the initial allocation finding reread the timesheet and both report tables with three Zetaris request IDs; after a local correction, the next check reread the activity table with one request ID. Both follow-ups matched the imported snapshot. The table names differ slightly from the CSV names, so use [the verified mapping](zetaris/README.md). During development in Cursor, its Agent added the Zetaris evidence snapshot panel to `web/`. Lens saves an execution timeline and conditionally chooses one further evidence probe. This is a bounded deterministic investigation, not model-driven reasoning. A filmed demonstration and public GitHub submission remain incomplete.

## Architecture

| Module | Job |
| --- | --- |
| `web/` | Render the local import, check, correction, and review interface. |
| `app.py` | Validate imports, serve the API, and save local review state. |
| `lens_core.py` | Reconcile claims deterministically against canonical source records. |
| `lens_investigator.py` | Select and verify one bounded, read-only follow-up against the imported Zetaris snapshot. |
| `zetaris/` | Query registered evidence tables through the documented SQL Editor API. |
| `meterless/` | Preserve source, finding, and human-decision history in the reference runtime. |
| `examples/` | Provide a labelled synthetic case and supported CSV format. |
| `tests/` | Exercise reconciliation boundaries and the local HTTP journey. |

## Boundaries

- A valid shared allocation is accepted when the total fits the source quantity; the app does not decide each funder's policy for you.
- Missing source IDs, incompatible units or periods, and uncertain identity links produce review states rather than a false clear verdict.
- Findings depend on the records supplied. Lens cannot prove an event did not happen just because its log entry is absent.
- The local SQLite store and Meterless reference runtime are intended for a single-user demonstration. They do not provide production access control or concurrent-write safety.
- Sponsor availability is surfaced separately from local reconciliation. Local arithmetic is never presented as Zetaris output.

The [product contract](docs/PRODUCT_CONTRACT.md), [research ledger](docs/RESEARCH_LEDGER.md), and [build plan](docs/BUILD_PLAN.md) record scope and remaining proof gates.

## Third-party code and license

The `meterless/vendor/` reference and conformance files come from [Meterless/Meterless](https://github.com/Meterless/Meterless) at commit `1742dec56a66e58eef9dda2d2b865823758ca8cd` and retain the [Apache 2.0 license](meterless/vendor/LICENSE). See [third-party attribution](THIRD_PARTY_NOTICES.md). A license for the Lens-authored source has not yet been selected.
