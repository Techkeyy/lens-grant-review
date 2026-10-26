# Lens public user acceptance test

This is the release gate for the public link. Run it through the deployed website as a normal visitor, using the visible controls. API tests and a local demonstration do not replace it. Record the date, deployed URL, app commit, browser, account names (never tokens), and observed result for each step.

## First account: full review

1. Open the public link in a private browser window. Sign in with Google. Confirm the page identifies the correct account and offers a new saved review. Sign out, reopen the link, and confirm the review is not visible until sign-in.
2. Start a new review with the clearly labelled synthetic sample. Confirm the review appears in the saved-review list. Confirm the two draft reports, timesheet, receipt and activity sources are identified without implying these are real charity records.
3. Run the check. Inspect the leading shared-timesheet question: the two report claims total eight hours while the captured timesheet row records four. Open the original claim and source locations and the calculation. Inspect the valid two-plus-two split separately; Lens should not flag it as an over-allocation.
4. Save a human explanation on a question. Confirm it is labelled as a note and does not automatically clear the finding. Correct one duplicated four-hour allocation to two hours; if needed, correct the other to two hours. Rerun the check. The shared total should now fit four hours; the workshop evidence gap should remain a question if its records are still missing.
5. Refresh, sign out, sign in again, and reopen this review. The correction, explanation, current findings, and source references should still be present. Open the same account on another device or browser and confirm the saved review is available there.
6. Export the review through the interface. Confirm the downloaded artifact reflects the visible current revision, finding statuses, source references, and investigation steps. Do not treat the export as a compliance certificate.

## Second account: isolation and concurrent work

1. Sign in as a different Google account in a separate private browser window. Confirm the first account's review is absent from the saved-review list. Start and save a different review.
2. Return to the first account. Confirm its review has not changed. Attempt to open the other account's review through a copied review URL or ID, if the interface exposes one. It should show an access error without the other account's data.
3. Open one review in two sessions for the same account. Make a correction in one session and then attempt a stale edit in the other. Lens should make the conflict visible or prevent silent loss of the first edit.

## Failures and recovery

1. Try an import with a required CSV missing, then an invalid CSV. The interface should identify the problem and keep the prior saved review intact.
2. Retry after a transient network failure. A duplicate click or page refresh during a pending check must not create contradictory revisions or expose another user's records.
3. With a fresh Zetaris-backed review, confirm the five registered synthetic tables, their row counts, snapshot hashes and request IDs appear under the evidence details. The selected live follow-up must show the source rows it reread and distinguish a matched snapshot from an unavailable or changed source. If the shared Zetaris import is disabled for the public service, record that limitation and test it on the owner-controlled environment.
4. Test at desktop and narrow phone widths. The start action, finding, calculation, source records, correction, rerun and export controls must be readable without horizontal clipping. Use keyboard navigation and verify visible focus, labels and status messages.

The owner records any failure, directs a fix, and repeats the failed normal-user step. Do not call the public product finished while a critical step is unproven.
