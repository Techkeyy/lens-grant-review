# Lens director task LENS-UX-02: clear first visit and image-led hero

**Mode:** Redesign  
**Priority:** P0  
**Relevant source:** `master` after `c342e0f`; public app at `https://lens-grant-review.onrender.com`  
**Owner-approved scope:** Make the app understandable immediately, use the most recently downloaded magnifying-glass image as a full-bleed hero, and draw structural inspiration from `https://ballroom-eight.vercel.app/`.

## Objective

A first-time charity staff member should understand in five seconds that Lens checks a draft grant report against the records behind it, see why that matters, and know to sign in to try it. After sign-in, starting or resuming a review should be clear.

## Approved behavior to preserve

- Google sign-in, saved per-account reviews, sample and five-CSV imports, correction, explanation, rerun, evidence, and export.
- The public UAT result on desktop and phone, including the 8-versus-4 sample and correction-to-rerun path.
- The evidence boundary: Lens asks for human review and does not approve or send a report.
- Backend authorization, storage, Meterless, Zetaris, and all source provenance.

## Surface corrections

| Surface | Current deficiency | Required correction | Check |
| --- | --- | --- | --- |
| Signed-out arrival | “Know what your report can prove” is abstract | Say plainly: “Check your grant report before you send it.” Name the records and the human next action near the headline | Five-second read, desktop and phone |
| Hero image | Old proof card feels like a separate component | Use the owner’s latest downloaded hand-and-magnifier image as a large, full-bleed visual on a dark canvas; preserve its vintage ink character | Image fills the viewport composition without hiding copy or cropping the hand unintentionally |
| Hero action | Google sign-in follows a long paragraph | Put a high-contrast sign-in button directly after concise copy; secondary link scrolls to the explanation | Visible without scrolling at desktop and phone widths |
| Example proof | Valuable 8-versus-4 case is buried in a card | Show a compact, clearly labelled synthetic evidence comparison inside the hero | No claim that sample is live customer data |
| Signed-in home | “Start where the evidence is” is abstract; saved work is low | Say “Choose how to start your review,” and put the saved review picker before new-start options | Returning review can be found immediately |

## Reference translated to Lens

The Ballroom reference uses a full-viewport dark image, bold left-aligned title, short supporting sentence, and distinct primary and secondary actions. Lens will adopt that composition and pace while keeping its own name, magnifier image, colors, copy, and evidence-review purpose. No reference assets or text are copied.

## Visual direction

Use a charcoal-green full-bleed hero whose oversized vintage magnifier extends toward the right and lower edges. Keep the left text area dark enough for bright ivory copy. Use a strong condensed display treatment for the headline, with warm brass accent on “grant report”; ordinary explanation remains in a readable sans serif. The image is a visual metaphor for checking records, not a substitute for an explanation. Put the synthetic 8-hours-claimed, 4-hours-recorded example in a restrained band at the bottom of the hero. Below the hero, return to the calmer cream workspace and clear three-step explanation. Avoid audio, autoplay, carousel, or ornamental motion; honor reduced motion.

## Copy and interaction

- Hero eyebrow: “FOR CHARITIES REPORTING TO FUNDERS”.
- Hero headline: “Check your grant report before you send it.”
- Hero explanation: “Lens compares draft reports with timesheets, receipts, and activity records. It points out claims with missing or conflicting support and shows the exact rows so you can correct or explain them.”
- Primary action: “Sign in with Google”. Helper: “Then try the sample in about a minute. Your reviews are saved.”
- Secondary action: “See how it works”.
- Truthful boundary: “You make the final decision. Lens does not approve or send your report.”
- Signed-in home heading: “Choose how to start your review.”
- Do not imply support for PDFs or arbitrary files; user uploads require five CSV files.

## Acceptance evidence

Inspect signed-out and signed-in home at desktop and a true 390px viewport. Verify headline, explanation, Google action, and synthetic proof are readable; no horizontal overflow; keyboard focus and contrast; actual image loads from the app, not a local-only path. Check the saved-review selector stays functional. Run the UI text audit, JavaScript syntax check, and relevant application tests. Preserve the current public UAT result and deploy the reviewed version to the existing Free Render service.
