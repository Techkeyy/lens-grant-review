# Lens director task LENS-UX-01: guided evidence review

**Mode:** Redesign  
**Priority:** P0  
**Source:** Public Lens at `https://lens-grant-review.onrender.com`, branch `master`, baseline `afc239a`  
**Owner-approved scope:** Restructure and visually redesign the UI and UX before completing UAT. Use the owner's two design skills, inspect comparable products, use SVGs rather than emojis, and guide users to the next step after each action.

## Objective

A first-time charity reviewer should understand Lens within seconds, sign in, open a labelled sample or upload five files, run a check, inspect one question with its supporting rows, record a correction or explanation, rerun, and export without hunting through a long page.

## Approved behavior to preserve

- Google sign-in and per-account saved reviews, including returning to a review from another device.
- All current import, source-link, reconciliation, Meterless, Zetaris, correction, explanation, and export behavior.
- The evidence boundary: Lens raises questions, does not accuse anyone, approve a report, certify compliance, or submit to a funder.
- Source IDs, row locations, calculations, live/snapshot labels, and technical investigation records.
- Backend authentication and data isolation. No user-facing redesign may bypass them.

## Surface corrections

| Surface | Observed deficiency | Required correction | States to inspect |
| --- | --- | --- | --- |
| Arrival | Tall intro and multiple unrelated sections before a clear first action | Concise what/why/how, primary Google sign-in, small truthful sample preview | Signed out, loading, sign-in error; desktop/mobile |
| Signed-in home | Saved review picker and start panels compete | Show saved work and a dominant sample start, with upload as a clear second path | First visit, returning account, empty list, list error |
| Preparation | All mapping forms crowd the path to first value | Show imported summary, only unresolved links prominently, and a visible Check action | Sample import, uploaded files, validation error, uncertain source |
| Findings | Claim/source detail pushes correction below the viewport | Lead with the question and arithmetic; pair claim and source; keep exact rows one interaction away | Needs correction, needs evidence, needs review, clear |
| Resolution | Correction removes the finding, while rerun is above the user's scroll position | After correction, move focus to a visible Run check again action in the same viewport; after explanation, state that the note is saved and the question remains | Save success, validation error, pending rerun, rerun result |
| Completion | Export is an incidental link high above a long record list | Present the current review status and a clear export action after checking | Open questions, all-clear, export error |

## Product fit and visual direction

The primary user is a charity staff member reviewing a report before sending it. The main job is to locate unsupported or conflicting claims and decide what to correct or explain. First impression: "Lens checks what a draft report says against the records behind it." The magic moment is the shared timesheet discrepancy, eight claimed hours against four recorded, with the underlying rows. The primary sample action should reach that moment quickly. Use the Lens name and a document/evidence motif expressed through typography, spacing, measured lines, and purposeful SVGs. Create a more confident review workspace than the current long editorial page, but avoid a generic analytics dashboard. Type and color must make status, evidence, and actions easy to scan. Keep technical receipts secondary; keep arithmetic and source links visible. Motion, if any, should clarify stage changes and honor reduced motion.

## Interaction and content requirements

- Main path: welcome → sign in → choose review → import → confirm uncertain links as needed → check → inspect finding → correct/explain → rerun → export.
- One primary action per stage and an actual active-step indicator; no decorative progress labels.
- Every action communicates pending, success, error, and the next useful action. Preserve inputs on recoverable errors.
- Sign-in and review selection must not disclose another account's content; a saved review opens at its actual current stage.
- Use no emoji and no decorative arrow/plus/minus glyphs as icons. Use accessible inline SVGs where icons aid recognition.
- Plain, specific language; no invented metrics, invented live activity, compliance verdict, or claim of funder submission.
- Readable body type, keyboard access, visible focus, status announcements, mobile touch targets, no horizontal overflow.

## References translated to Lens

- [Dext getting started](https://help.dext.com/en/articles/416705-getting-started-with-dext-for-businesses): intake moves to human review before publishing. Lens should move from source import to the next review decision without leaving users to find it.
- [Submittable progress report revision](https://next.support.submittable.com/hc/en-us/articles/42852701242519-How-to-Revise-Resubmit-a-Progress-Report): a targeted field and comment make a requested change clear. Lens should target one finding and its corrective action.
- [Vanta automated test evidence](https://help.vanta.com/en/articles/11345529-automated-test-evidence): a result remains connected to itemized proof, with deeper technical detail available on demand. Lens should keep exact rows and investigation steps verifiable without making them the first screen.

These are workflow references, not branding or assets to copy.

## Acceptance evidence and release

Return before/after desktop and 390px mobile screenshots for signed-out, review home, findings, and correction pending rerun. Verify no overflow, keyboard focus, labels, contrast, loading/empty/success/error states, and reduced motion. Run the owner's `audit_ui_text.py`, JavaScript syntax check, relevant tests, and a production build or local serving check. Identify touched files and confirm protected backend/auth/storage behavior remains intact. Do not call the redesign complete until the owner can finish UAT on the deployed revision. Deploy after local review; record revision SHA, deploy ID, live URL, and rollback point.
