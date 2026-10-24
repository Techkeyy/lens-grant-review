# Lens product contract (Phase 1, 22 October 2026)

## Product promise

Lens helps a small charity's grant manager review two draft funder reports against the underlying records before sending them. It spots unsupported claims and overallocated work or expenses, shows the exact source records and arithmetic, then lets the manager correct or explain a finding and rerun the check.

This is a review aid, not a fraud detector, auditor, legal opinion, or compliance certification. Findings are questions for a person. Lens must never imply that an overlap alone proves wrongdoing. A shared cost can be allocated across grants when the total and the allocation basis are supported.

## Primary user and moment

The primary user is the person at a small charity who prepares or reviews funder reports. Their job is to ensure reported costs and activities can be traced to receipts, timesheets, and activity records. Lens intervenes immediately before the report goes to a funder.

The memorable moment: each draft looks plausible by itself, but Lens shows that the same four staff hours were charged in full to both grants while the source timesheet records only four hours in total. The manager can see both claims and the timesheet together. A second example must show a valid 50/50 allocation of those four hours that Lens accepts.

## Real user journey and acceptance test

1. A new user opens Lens and sees what to provide and why. An explicitly labelled sample case may be offered.
2. The user adds two draft grant reports and supporting records through the app. Inputs and status remain visible; a failed import does not silently disappear.
3. The user starts a check. Lens reads the records, reconciles line items and activities, and shows progress and any inability to assess.
4. Lens displays a review list. Every finding identifies the two affected claims, canonical source, calculated total, and exact source location. A missing record is labelled as missing support rather than a proven error.
5. The user corrects an allocation or records a human explanation. Lens retains the user's choice and the source version that was reviewed.
6. The user reruns the check and sees the updated result. The resolved finding changes state for a demonstrable reason. The user can reopen the saved review after refresh.
7. The user exports or saves the reviewed result for internal use. Sending a report to a funder is outside the first scope unless a later approved integration is built and verified.

**Core outcome proof:** an intended user completes this journey through the normal deployed interface, using real application logic and durable state, without terminal calls or developer repair. The app must show a true positive, valid proportional allocation, missing support, and a corrected rerun. Until that happens, the product is still building.

## Core rules and trust boundaries

- A canonical source record has a stable ID, date, person/vendor/activity, quantity or amount, and a retrievable source location.
- Claim allocations with the same canonical source ID are summed across both reports. A total above the recorded amount or hours is a candidate finding. A total equal to or below the source amount is not automatically a finding.
- Legitimate split allocation needs a recorded basis where the funder's rules require one. Missing basis means `needs evidence`, not `invalid`.
- Records with similar descriptions but no reliable identity match are `needs review`, not merged or condemned.
- Currency, unit, date range, and staff identity must match before arithmetic is presented as conclusive.
- The deterministic layer calculates totals and rule outcomes. If a model extracts fields or writes prose, each extracted field must retain the document location and uncertainty; model text cannot override arithmetic or human decisions.
- No automatic submission to funders, accusation of fraud, or unqualified 'compliant' status.
- Grant records may contain personal and financial data. Authentication, scoped access, retention, and redaction requirements must be resolved before a public deployment receives real charity records.

## Minimum causal loop

Input reports and records -> identify canonical evidence -> reconcile each report and cross-grant totals -> show sourced questions -> human resolution -> rerun and persist outcome.

## Technical pipeline to test before interface polish

1. Import and parse the supported file formats, preserving source locations.
2. Normalize people, dates, activities, cost lines, and source IDs; surface uncertainty.
3. Reconcile report assertions against evidence and sum shared-source allocations deterministically.
4. Generate a human-readable finding with evidence references and arithmetic.
5. Store source versions, decisions, explanations, and rerun results.

The load-bearing risk is identity resolution: can Lens reliably connect a claim to the correct canonical timesheet or receipt without inventing a match? Prove this with a small realistic corpus containing near duplicates and legitimate splits before building a large UI. Sponsor integrations must also be proved with live calls before any corresponding claim is made.

## Scope

**NOW:** two grants; one reporting period; staff-time and one expense type; supported activity count; one realistic sample set; source-linked findings; human correction/explanation; rerun; durable review; one deployable normal-user path. Use authentic sample formats and clearly label synthetic demo data.

**NEXT:** more import formats, additional grant restrictions, reviewer collaboration, richer exports, recurring report cycles.

**LATER:** accounting-system connections, funder-specific policy libraries, automated report drafting, enterprise controls.

## First build gate

Before product implementation, confirm the official track and submission requirements, inspect the actual sample source formats, and prove the riskiest evidence-matching path. If using Zetaris, run its documented connection smoke test and a real query across two Lens evidence sources. If using Meterless, prove persistent state in an actual runtime. A package import, schema sketch, or mock response is not integration proof.
