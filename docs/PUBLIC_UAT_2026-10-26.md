# Public Lens UAT record — 26 October 2026

Deployment: `https://lens-grant-review.onrender.com` on Render Free, Frankfurt. Source commit at start of UAT: `afc239a`; guided UI revision: `4aa2db0`, Render deploy `dep-dbfo1sm417fc73dcse9g`. Test data: the labelled synthetic sample only. No credentials are recorded here.

## Observed so far

| Check | Result | Evidence |
| --- | --- | --- |
| Render deploy | Pass | Render reported the Docker deployment live after Supabase environment setup. |
| Public configuration | Pass | Homepage and bundled sign-in script returned HTTP 200; `/api/config` reported Supabase mode and a base project URL. |
| Signed-out API gate | Pass | `/api/session`, `/api/reviews`, and `/api/state` each returned HTTP 401 without a user token. |
| Google sign-in | Pass | A real user signed in on the public URL and saw their account and New review control; Render logged authenticated session and review-list HTTP 200 responses. |
| Create and load synthetic review | Pass | User created a saved review and opened the labelled synthetic sample; Render logged review creation HTTP 201 and sample import HTTP 200. |
| First reconciliation | Pass | User ran the check; Render logged HTTP 200. The page showed 8 claimed hours against 4 timesheet hours with both draft rows and the timesheet row, a 10-versus-8 activity support gap, a separate valid 4-of-4 split, and live Meterless review history. |

## Remaining coverage

- A separate real Google account has not tried to list, open, edit, or export the owner's review. Automated HTTP tests cover account separation and stale-write conflicts in `tests/test_accounts.py`.
- A real user has not completed the flow on a phone or by keyboard alone. The signed-out and findings screens were rendered at 390px with no horizontal overflow, and the local correction-to-rerun transition was exercised in a browser.
- An invalid CSV submission and recovery after Render sleep were not exercised by the owner on the public service. Automated tests cover invalid import without replacing saved work.
- Owner-only Zetaris import and live follow-up are not enabled on the public service. They were tested previously in the local owner-controlled environment.

The public sample's main user journey passed. The remaining items above limit claims about every account, device, and import path.

## Guided UI release

The owner paused the initial UAT after getting lost while trying to resolve the shared-timesheet finding. The deployed revision separates welcome, review home, preparation, findings, saved-change rerun, and export stages. It takes the reviewer to the next action after a correction while retaining exact source rows.

## Public guided-flow observations on revision `4aa2db0`

The owner signed in and saw the redesigned start screen. A new blank review followed by **Open synthetic case** led to the preparation screen with **Check both reports**. The first check opened the shared-timesheet finding with 8 claimed hours against 4 recorded and a correction form. Changing Reading Futures `A-TIME-1` from 4 to 2 hours led directly to **Change saved** and **Run check again**. The rerun showed 6 claimed hours against 4 recorded, with the corrected current claim displayed as 2 hours and the other claim still at 4. The original imported row remained visible for provenance.

The owner then changed Community Learning `B-TIME-1` from 4 to 2 and reran. The page moved the shared timesheet into the clear group: current allocations 2 + 2 = 4 of 4 recorded hours. The separate 10-session claim still had only 8 linked activity rows and stayed open. The source-identity question also stayed open. The owner saved an explanation on the activity question; Lens displayed the note with its source revision and kept the **Needs evidence** status. The owner reached the export stage, saw its review-only warning, and confirmed `lens-review.json` downloaded. Refreshing and signing out/in reopened the same saved review with the corrected 4-of-4 allocation, 10-versus-8 activity gap, and explanation.
