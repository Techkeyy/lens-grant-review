# Lens hackathon slide deck outline

**Working outline · updated 24 October 2026.** Prepare the final deck from verified build evidence. The official submission rule requires problem and users, solution, agent workflow or architecture, stack, Zetaris and Meterless use, uniqueness of those uses, product visuals, and future enhancements. Live Zetaris import, two conditional follow-up branches, Meterless persistence, and Cursor development use have been verified. The final filmed interface take and GitHub submission remain open. Describe the investigator as bounded and deterministic, without claiming model reasoning.

## Deck story: seven slides

### 1. Two reports, one underlying record

**Headline:** “A grant report can look right alone and still conflict with another.”

**Visual:** Two simple draft-report cards, each claiming four hours from one timesheet source `TS-101`; center card shows four hours recorded. Mark all data **synthetic**.

**Speaker point:** A small charity's grant manager must send funders supported financial and activity claims. The check happens before submission, when a human can still repair the report or explain a gap. Avoid unsupported market-size statistics.

### 2. Lens: a second pair of eyes before submission

**Headline:** “Lens connects report claims to original records and shows what needs review.”

**Visual:** Three steps: import two draft reports plus evidence → inspect a cited question → correct or explain and rerun.

**Screen proof:** Capture the actual import interface and a finding. Present Lens as a review workspace, not a fraud detector, auditor, compliance certificate, or automatic funder submission tool.

### 3. The complete user journey

**Headline:** “A manager can reach a review outcome through the product.”

**Visual:** Six screenshots or one annotated strip: load labelled sample or five CSVs; confirm links; check; open both report rows and original source; save correction; rerun, refresh, and download review JSON.

**Evidence:** Use the actual working UI. Include one supported 70/50 split of a $120 receipt and one 10-versus-8 activity evidence gap to show the app does not equate overlap with wrongdoing. If a step is not yet working through the interface, do not put it in the completed flow.

### 4. How the investigation reaches its answer

**Headline:** “Evidence is linked first; arithmetic and decisions have separate owners.”

**Visual:**

```text
Two report claims + timesheet/receipt/activity rows
            ↓ stable source IDs or human-confirmed links
Cross-source retrieval (Zetaris, verified live)
            ↓
Bounded conditional evidence probe (verified live)
            ↓
Deterministic reconciliation in lens_core.py
            ↓ exact claim/source rows and calculation
Manager correction or explanation
            ↓
Saved review in SQLite + Meterless reference-runtime history
```

**Boundary:** The current planner selects from fixed read-only queries based on the checked finding. It does not use a language model, invent a source match, override the calculation, or clear an unsupported claim. Live Zetaris reads, conditional probe choices, and Meterless reference-runtime events are verified; the filmed interface demonstration remains to be done.

### 5. What each sponsor actually contributes

**Headline:** “Each sponsor must have a visible job in the workflow.”

**Visual:** One annotated trace with inputs and returned outputs, not sponsor logos alone.

| Technology | Intended Lens role | Proof needed for final deck |
| --- | --- | --- |
| **Zetaris** | Query registered claim and evidence sources across data boundaries. | Real provisioned instance, real Lens tables, query text, returned rows, and linkage to the shown review. Adapter tests or `SELECT 1` do not suffice. |
| **Meterless** | Preserve source, finding, and human correction events in the World Model reference runtime. | Demonstrate write, read after process restart, and a trace tied to the filmed review. Name the local reference runtime accurately. |
| **Cursor** | Required development tool, rather than an end-user product feature. | A genuine Cursor development action and reproducible evidence for the submission explanation. |
| **NVIDIA** | Include only if it makes a measured contribution. | Name the actual technology, role, and result, or state that it was not used if the form allows. |

**Uniqueness claim:** Lens attempts a pre-send check of *already drafted reports* against canonical evidence across grants, instead of simply generating another report. This is a narrow workflow distinction, not a claim that no competitor handles allocations.

### 6. Technical proof and reliability

**Headline:** “The most important finding is inspectable and reversible.”

**Visual:** Enlarged `TS-101` finding: claims from both report CSV rows, source timesheet row, `8 hours > 4 hours`, correction, and rerun result. Add a small valid 2+2 split example and a missing-support example.

**Evidence to capture:** test count from a fresh run; UI fresh-user walkthrough; persistence after refresh; integration traces; source identity ambiguity behavior. Do not reuse a count from an older README if the suite changes. State that synthetic data is used for the demo. Explain that real charity records require access controls and privacy work absent from the local preview.

### 7. Where Lens goes next

**Headline:** “From a proven review loop to the formats charities already use.”

**Visual:** Two-column roadmap: **built and proved** versus **future**, with dates or labels only if accurate.

**Future candidates:** Funders' DOCX/PDF templates, accounting and payroll connectors, user accounts with scoped permissions, grant-specific reporting terms, recurring reporting cycles, and richer exports. Keep these off the implemented architecture diagram until shipped.

**Close:** “Before the report leaves, the reviewer can see what supports each claim and where the evidence still needs work.”

## Final assembly checklist

- Capture every product screenshot from the same release used in the video; keep the synthetic-data label visible.
- Replace all “proof needed” cells with verified traces or disclose incomplete work plainly.
- Show returned Zetaris rows and inspectable Meterless state if claiming either integration in the finished solution.
- Provide a source/third-party attribution footer where relevant, including Meterless reference code provenance.
- Put the project GitHub repository and demo URL on the final deck only after they exist and work. The repo must contain all source and a README with setup, usage, and dependencies under official Rule 6.3.
- Confirm the final Track 02 selection, HackOS form fields, and submission deadline in the registered event workspace.
