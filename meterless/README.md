# Lens × Meterless World Model

This directory contains a **running local integration**, not a hosted Meterless account or a claim that the full World Model product is production ready. `lens-world.ts` calls the official Meterless World Model reference `WorldModel` class in `vendor/src/index.ts`. That runtime writes an event log and audit log to `<state-directory>/.world/<namespace>.json` and rebuilds its graph on construction.

Lens maps source rows to `source` entities with stable external IDs and exact `file.csv#row=N` provenance. A reconciliation finding is an entity linked to its sources. A human explanation is a separate `correction` entity linked to the finding, retaining actor and timestamp. Source ingest uses the reference pipeline's checksum-based idempotence. Repeated identical findings and corrections are guarded in the Lens adapter; a correction ID cannot be reused for different content. The correction records a human action; the reconciliation engine must rerun and update the finding status separately.

Each finding also stores SHA-256 fingerprints of the source content and location it reviewed. A changed source yields a new finding event on rerun even when the finding's wording remains the same. The fingerprints identify versions; they are not a cryptographic authenticity guarantee for the original files.

## Provenance and license

- Upstream: [Meterless/Meterless](https://github.com/Meterless/Meterless), `engines/world-model/reference` and `engines/world-model/conformance`.
- Git commit copied: `1742dec56a66e58eef9dda2d2b865823758ca8cd` (23 October 2026).
- License: Apache-2.0; upstream license is in `vendor/LICENSE`.
- `vendor/src`, `vendor/conformance/runner.ts`, and the two copied upstream guides are unmodified Meterless files. Lens-specific code is `lens-world.ts`, `bridge.ts`, `proof.ts`, and `test/`.
- The standalone [Meterless/World-Model](https://github.com/Meterless/World-Model) repo describes architecture and is **not** the runnable reference used here.

## Run

From this directory, with Node.js 24 (the installed runtime verified here):

```powershell
npm test
npm run proof
$env:WORLD_MODEL_IMPL=(Resolve-Path .\vendor\src\index.ts).Path
node --experimental-transform-types .\vendor\conformance\runner.ts
```

The proof script prints a synthetic three-source case, the empty diff on replay, a sourced finding, a human correction, and the state recovered by a second `WorldModel` instance. The tests include **independent child processes** that write and read the saved state. As run on 23 October 2026, Lens tests passed 4/4 and upstream conformance passed 8/8. See `proof.ts` for the exact data; do not represent it as real charity data.

## JSON bridge for the Lens app

Run with `cwd` set to this directory:

```text
node --experimental-transform-types bridge.ts <state-directory> <namespace> <action>
```

Send one JSON object on stdin. The bridge returns one JSON object on stdout: `{ "ok": true, "result": ... }` or `{ "ok": false, "error": ... }` with exit code 1. Actions:

| Action | Input |
| --- | --- |
| `ingest` | `{ "sources": [{ "id": "time-17", "kind": "timesheet", "title": "Entry", "text": "...", "observedAt": "2026-10-23T09:00:00.000Z", "location": "timesheets.csv#row=2" }] }` |
| `finding` | `{ "id": "overlap-17", "sourceIds": ["time-17"], "status": "needs_review", "summary": "...", "calculation": "4 + 4 = 8 > 4 hours", "observedAt": "..." }` |
| `correction` | `{ "id": "review-1", "findingId": "overlap-17", "actor": "grant-manager", "explanation": "...", "observedAt": "..." }` |
| `read` | `{ "findingId": "overlap-17" }` returns finding, linked sources, corrections, audit, event count |
| `audit` | `{}` returns audit and event count |

Use a persistent app data directory in the final app. Never place real charity records in the repo or in a publicly served folder. The reference runtime uses a single JSON file per namespace and no authentication or multi-process write coordination; it is suitable for a local hackathon demonstration, not a shared production service. The app must not silently fall back to a mock if this bridge fails.

The Node type-transform flag is experimental and prints a warning to stderr on Node 24. The bridge's JSON result is on stdout. This runtime path avoids `tsx`'s Windows dependency on `os.userInfo()`, which fails in the current Codex sandbox. Node 20/22 users would need a separate TypeScript build step.
