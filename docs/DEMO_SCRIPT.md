# Lens demo video: recording draft

**Target length:** 2:35–3:05, within the official 1–4 minute limit. **Status:** updated 24 October 2026; not yet recorded. A live Zetaris import of all five registered synthetic grant tables returned 4 timesheets, 1 receipt, 8 activity rows, and 4 rows from each draft report. The default Lens app held 13 source rows, 8 claims, and 5 findings, including an `OVERALLOCATED_SOURCE` finding linked to `LENS_DEMO_FILES.timesheets` with a source key, snapshot hash, and Meterless finding ID. After `python app.py` restarted, the review remained `checked` with five findings and a fresh Meterless audit returned 39 events. The final filmed workflow still needs proof. Follow the gate below before recording.

## The story

Two grant reports look reasonable separately. Together they claim eight hours from a four-hour timesheet. Lens opens both claims and the original row, lets a reviewer correct the allocation, and checks again. It also accepts a valid shared expense and treats missing activity records as missing support, not proof that an event never happened.

**Track:** 02, The Agent That Can Explain Why. **Audience:** a grant manager at a small charity preparing two funder reports.

## Pre-recording proof gate

1. Complete a fresh-user walkthrough through the actual interface: sample load or five-file import → check → inspect source rows → correct → rerun → refresh → export. Record the actual URL, labels, output, and timing. Fix this script if any label or result changes.
2. Open **Inspect the investigation steps** and verify the saved run shows five actual Zetaris table query receipts, current source links, the deterministic rule check, and Meterless finding IDs. This is an execution trace of the workflow; an autonomous or model-driven investigation is not proved and must not be narrated as one.
3. Reproduce the verified **Zetaris** integration on camera by clicking **Import registered Zetaris tables** in Lens, checking all five live table snapshots, and showing the finding's source key and snapshot hash. The 24 October live import passed; a filmed take is still needed.
4. Reproduce the verified **Meterless** restart check on camera: show the finding ID from the filmed workflow, restart Lens, then read the saved review and Meterless audit. The 24 October local run persisted a checked review with five findings and a Meterless audit of 39 events. State that this is a local reference runtime.
5. Keep the **Cursor** Agent's change summary and development evidence for submission: it added the Zetaris evidence snapshot panel in `web/index.html`, `web/app.js`, and `web/style.css`. Cursor use is not a product screen.
6. Confirm the HackOS submission form and final official rules, including what to say about NVIDIA. This storyboard does not assume NVIDIA is used.

**Do not record a final submission video while gates 2 or 3 are open.** The rules require the video to show the main workflow, agent behavior, and Zetaris and Meterless integration. A staged local walkthrough alone would misrepresent the present sponsor status.

## Staging table

| View | Pre-state | Must be visible |
| --- | --- | --- |
| Lens at `http://127.0.0.1:8765` | Server running; browser at top; five registered synthetic Zetaris tables reachable | `Import registered Zetaris tables`, synthetic sample label, five table snapshots after import |
| Investigation | Sample loaded, not yet checked | `Check both reports`, source files and locations |
| Findings | Check completed | Overallocated `TS-101` finding, both report rows, timesheet row, arithmetic |
| Correction | Finding open | Claim selector, new quantity field, `Save correction`, then `Rerun check` |
| Sponsor evidence | The same imported review remains open | Five Zetaris table counts, finding's Zetaris source key/hash, Meterless finding ID and inspectable persisted state |

Avoid cutting from a terminal result into a claim about the browser. If the required integration is not reachable from the normal user flow, show it accurately as a separately verified component and disclose the gap.

## Linear storyboard and narration

### Scene 1 · 0:00–0:18 · The problem

**On screen:** Two labelled sample draft report files or a simple opening visual showing the two funders. No architecture slide.

**Say:** “A small charity is about to send reports to two funders. Each report looks plausible on its own. But the same staff shift may have been counted in both, and the person signing off needs to know before either report leaves.”

### Scene 2 · 0:18–0:42 · Bring the evidence together

**On screen:** Lens landing page. Select **Import registered Zetaris tables**. Pause on the synthetic data label and the Zetaris evidence snapshot panel with five table counts, hash prefixes, request ID count, and caveat. The five CSVs were uploaded and registered in Zetaris before recording.

**Say:** “This is Lens. It queries five synthetic grant tables in Zetaris: two draft reports, timesheets, receipts, and activity records. The reviewer can inspect the returned source rows before accepting a match.”

### Scene 3 · 0:42–1:12 · Investigate

**On screen:** Click **Check both reports**. Show the result list and open the main finding. Hold the screen still on both report claims and source row.

**Say:** “Lens links each report claim to its source ID, then checks totals across both grants. Here, Reading Futures claims four hours, and Community Learning claims the same four hours. Both point to timesheet TS-101. The source records four hours altogether.”

### Scene 4 · 1:12–1:46 · The explanation, not an accusation

**On screen:** Keep the `TS-101` card still. Show the `Claims total 8 hours; the linked source records 4 hours` arithmetic and both original CSV row locations.

**Say:** “The question is precise: eight hours were allocated from a four-hour record. You can see both report rows and the timesheet beside the calculation. Lens asks a person to review the allocation. It does not call this fraud or decide what either funder allows.”

### Scene 5 · 1:46–2:13 · Correct and verify

**On screen:** Choose the Community Learning `B-TIME-1` claim, enter `0` **only if that is the defensible correction for the sample**; otherwise use a tested valid allocation. Click **Save correction**, then **Rerun check**. Show the overallocated finding clearing. Refresh and show the saved revision. Do not imply the original CSV files were rewritten; the app currently saves an internal correction.

**Say:** “The reviewer corrects the report allocation and runs the check again. Now the total fits the source, and the updated review remains after refresh. The change is recorded for this internal review; a person still updates and submits the final funder document.”

### Scene 6 · 2:13–2:35 · Show judgment in the edge cases

**On screen:** Quickly show one valid shared expense and the activity evidence gap. Keep their source rows visible long enough to read.

**Say:** “Lens does not flag every shared record. This 120-dollar receipt is split seventy and fifty across two grants, so the total fits. Another report lists ten sessions but links to only eight supplied activity records. Lens asks for two missing records or an explanation; it does not claim those sessions never happened.”

### Scene 7 · 2:35–3:00 · Sponsor and trust proof, conditional

**On screen:** Show the import's five Zetaris table counts, the finding's `LENS_DEMO_FILES.timesheets` source key and snapshot hash, then the Meterless finding ID and saved review history from this filmed run. Use no screenshot substitute. If a sponsor element cannot be shown in this span, shorten earlier scenes rather than omit a required integration.

**Say:** “Those rows came from five Zetaris tables. Lens keeps the source key and a snapshot hash beside its finding. Meterless records the finding and reviewer history locally, so this decision can be reopened. A person makes the final call before either report goes out.”

**Stop on the result.** No outro card.

## Claim-to-proof checklist for the final take

| Spoken claim | Proof required before recording | Current status |
| --- | --- | --- |
| Two reports claim 8h from a 4h `TS-101` source | Same IDs and quantities in current UI and source rows | Local sample/core support; final UI take pending |
| A corrected rerun clears the finding and persists | Browser correction, rerun, refresh | Implemented locally; fresh-user recording pending |
| $120 receipt is a valid 70/50 split | Current result card and original receipt | Local sample/core support; final UI take pending |
| Ten sessions have eight linked records | Current result card and eight locations | Local sample/core support; final UI take pending |
| Inspectable investigation workflow | Executed Zetaris query receipts, current source-link basis, rule-check results, cited rows and Meterless IDs in a saved timeline | **Implemented locally; filmed take pending. Does not prove autonomous/model reasoning** |
| Zetaris supplies the shown evidence query | Five live table results and `OVERALLOCATED_SOURCE` linked to `LENS_DEMO_FILES.timesheets` key/hash | **Verified in local live run 24 October; filmed take pending** |
| Meterless records/reopens review history | Same imported review remained checked after app restart; fresh audit returned 39 events | **Verified in local live run 24 October; filmed take pending** |
| Cursor was used in development | User-reported Cursor Agent change to the three `web/` files; code and Agent test summary inspected | **Development use reported and matching code verified; keep the Agent transcript or screenshot for submission** |

## Language guardrails

Say **“possible allocation conflict”**, **“missing supplied evidence”**, and **“local reference runtime”** where those are accurate. Do not say Lens certifies compliance, detects fraud, submits reports, imports arbitrary PDFs, or automatically reconciles all grant rules. Do not call the synthetic case a real charity case. The five-table import is a verified live Zetaris grant-data query. The investigation timeline records executed workflow steps; do not call it model-driven or autonomous reasoning. Re-check the exact current UI before recording because implementation is changing during the hackathon.
