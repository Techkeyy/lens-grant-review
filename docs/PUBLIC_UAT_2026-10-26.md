# Public Lens UAT record — 26 October 2026

Deployment: `https://lens-grant-review.onrender.com` on Render Free, Frankfurt. Source commit at start of UAT: `afc239a`. Test data: the labelled synthetic sample only. No credentials are recorded here.

## Observed so far

| Check | Result | Evidence |
| --- | --- | --- |
| Render deploy | Pass | Render reported the Docker deployment live after Supabase environment setup. |
| Public configuration | Pass | Homepage and bundled sign-in script returned HTTP 200; `/api/config` reported Supabase mode and a base project URL. |
| Signed-out API gate | Pass | `/api/session`, `/api/reviews`, and `/api/state` each returned HTTP 401 without a user token. |
| Google sign-in | Pass | A real user signed in on the public URL and saw their account and New review control; Render logged authenticated session and review-list HTTP 200 responses. |
| Create and load synthetic review | Pass | User created a saved review and opened the labelled synthetic sample; Render logged review creation HTTP 201 and sample import HTTP 200. |
| First reconciliation | Pass | User ran the check; Render logged HTTP 200. The page showed 8 claimed hours against 4 timesheet hours with both draft rows and the timesheet row, a 10-versus-8 activity support gap, a separate valid 4-of-4 split, and live Meterless review history. |

## Still to test

- Save a human explanation, correct both linked allocations to 2 hours, rerun, and verify the over-allocation clears while the activity gap remains.
- Refresh and sign out/in; verify the review, correction, explanation, findings, source references, and export persist.
- A second Google account must be unable to list, open, edit, or export the first account's review. Test a stale same-account tab for a visible conflict.
- Check invalid CSV handling, mobile layout, keyboard navigation, and behavior after Render sleep or redeploy.
- Owner-only Zetaris import and its live follow-up are not enabled on the public service. They were tested previously in the local owner-controlled environment.

This is a partial UAT record. Do not claim the public flow is complete until the pending checks have been observed.

## Guided UI revision in progress

The owner paused UAT after getting lost while trying to resolve the shared-timesheet finding. The redesigned interface now has separate welcome, review home, preparation, findings, saved-change rerun, and export stages. A local browser run saved a 4-to-2-hour correction and moved directly to a visible **Run check again** action. This local observation does not close the public UAT items above. Repeat the resolution and persistence checks on the deployed revision with the owner.
