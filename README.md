# Lens

**Check two draft grant reports against the records behind them before they go to funders.**

**[Live app](https://lens-grant-review.onrender.com)** · **[Three reproducible sample runs](examples/sample_runs.json)** · **[Public UAT record](docs/PUBLIC_UAT_2026-10-26.md)**

Lens is for the person at a small charity who prepares or reviews funder reports. Receipts, timesheets, activity notes, and draft claims can look reasonable separately. Lens brings linked records together, shows where the evidence fits or falls short, and leaves the decision with that person.

> “Do these reported hours, costs, and sessions have records to support them?”

Built for the Open Agent Hackathon 2026, Track 02: *The Agent That Can Explain Why*. Lens raises sourced questions; it does not accuse anyone of wrongdoing, certify compliance, or send a report.

## Why this exists

Two reports can each claim four hours from the same four-hour timesheet. Looking at either report alone misses the overlap. A legitimate two-hour split across the reports should also be recognized.

```text
Reading Futures draft       4 hours ─┐
                                      ├── Timesheet TS-101: 4 hours recorded
Community Learning draft    4 hours ─┘
                         8 claimed in total → check the split
```

The link to the original row matters as much as the calculation. Lens uses source IDs and row locations to show its basis. When a source identity is uncertain, it asks a reviewer to confirm it rather than treating a similar name as proof.

## What a reviewer does

1. **Starts a review.** Sign in with Google on the public app, create a saved review, then open the labelled synthetic example or upload the five supported CSVs.
2. **Checks the links.** Confirm uncertain report-to-source or activity links before relying on them.
3. **Runs the check.** Lens compares claims with timesheets, receipts, and linked activity records. It totals allocations that share a source across both grants.
4. **Reads a question.** Each finding leads with a plain-language comparison and next step. The exact imported rows and investigation history remain available.
5. **Makes a decision.** Change an allocation amount or save an explanation, then rerun. A note does not clear a gap by itself.
6. **Keeps the result.** Reopen the review after sign-in or download its JSON record, including current questions, corrections, explanations, and source references.

Corrections change the **Lens review**, not the uploaded CSV or the charity’s original funder report. The reviewer must update that report separately before sending it.

### Try the synthetic case

Open the [live app](https://lens-grant-review.onrender.com), sign in, choose **Open synthetic case**, then **Check both reports**. The invented case starts with three questions and two checks whose totals fit the supplied evidence:

| What Lens finds | What it means |
| --- | --- |
| Two reports claim 4 hours each against one 4-hour timesheet | Review the allocation; Lens cannot know which draft amount is wrong. |
| 10 sessions reported, 8 linked activity records | Two sessions lack supplied support; this does not prove they never happened. |
| One staff-time claim has two plausible timesheet matches | Confirm source identity before treating either match as evidence. |
| A shared 4-hour timesheet is split 2 + 2 | The linked total fits the recorded hours. |

Change the two 4-hour claims to 2 hours each and rerun. The shared-timesheet question moves to the checks that fit, while the 10-versus-8 activity gap remains. The [public UAT record](docs/PUBLIC_UAT_2026-10-26.md) documents Google sign-in, saved correction, rerun, explanation, JSON export, refresh, sign-out/in, and a phone check. That record covers one real account; a separate human two-account isolation test has not been recorded.

## Run locally

Use Python 3.11+ and Node.js 24. The local path has no pip or npm installation step: the Meterless reference runtime is included.

In PowerShell:

```powershell
git clone https://github.com/Techkeyy/lens-grant-review.git
cd lens-grant-review
python app.py
```

Open `http://127.0.0.1:8765` and choose **Open synthetic case**. The server binds to localhost by default. Local reviews and Meterless state are written under ignored `data/`. To bring your own records, use the five CSV slots shown in the app; [`examples/`](examples/) contains the required headers and invented records. Importing another case replaces the current case in that review, so export a copy first if needed.

For the public service, the server requires Supabase configuration and Google sign-in. The private service-role key belongs only in the server environment. See [public deployment](docs/PUBLIC_DEPLOYMENT.md) and the [database schema](docs/lens_reviews.sql).

## How the evidence is handled

Lens reconciles deterministically. It sums claims linked to the same source, checks units and reporting periods, counts distinct linked activity rows, and leaves missing or ambiguous evidence open. A bounded investigator can choose one allowlisted, read-only follow-up. It does not author arbitrary SQL or choose a person from a similar name.

The public sample and ordinary CSV uploads are checked from their imported snapshot. The review labels this path as having **no live Zetaris grant-data query for that review**. An owner-controlled Zetaris path reads five registered synthetic grant tables into a captured snapshot and requeries selected sources; it passed a fresh local HTTP import, check, correction, rerun and process-restart check on 27 October. Public Zetaris import is restricted to the configured demo owner. [Zetaris setup](zetaris/README.md) and the [sanitized live proof](docs/zetaris_live_http_proof_2026-10-27.json) document table counts, snapshot hashes, follow-up request IDs and results.

Lens records source, finding, and human-decision events using the included Meterless World Model reference runtime. In the public service, that history is saved with the account’s review. [Meterless implementation and proof](meterless/README.md) explains the reference integration and its limits.

Lens also has a bounded [Meterless Nightshift provider adapter](nightshift.py). When a runtime URL and real token are configured, it sends the codes and arithmetic of open findings to `meterless/auto` and accepts only a supported finding code as the next question to investigate. It records the returned model and request ID. Nightshift cannot change a source link, calculation, or finding status; if the runtime is absent or its response is invalid, Lens labels the model decision unavailable and uses a fixed follow-up order. [Nightshift setup and smoke test](docs/NIGHTSHIFT_SETUP.md) gives the remaining steps. **No live Nightshift request has been verified for this release, and the public Render service is not configured to reach a Nightshift hotspot.** This is an outstanding hackathon integration gate, not proof of sponsor compliance.

| Module | Job |
| --- | --- |
| `web/` | Guide import, review, correction, rerun, and export. |
| `app.py` | Serve the HTTP flow and preserve review state. |
| `accounts.py` | Verify public sessions and scope saved reviews to an owner. |
| `lens_core.py` | Reconcile claims and produce sourced findings. |
| `lens_investigator.py` | Select one bounded follow-up or abstain. |
| `zetaris/` | Read configured grant tables and preserve query receipts. |
| `meterless/` | Store linked source, finding, and human-decision events. |
| `nightshift.py` | Ask a configured Nightshift hotspot to prioritize an already-supported follow-up. |
| `examples/` | Show the supported CSV shape with invented records. |

## Checks and boundaries

Run the repository checks from its root:

```powershell
python -m unittest discover -s tests -v
python -m unittest zetaris.test_client zetaris.test_raw_evidence -v
cd meterless
npm test
npm run proof
```

The tests exercise over-allocation, valid proportional splits, missing activity support, ambiguous identity, changed-source abstention, invalid import recovery, account ownership checks, and a saved correction followed by rerun. The Meterless proof runs against its included reference runtime; it is not a hosted production service. See [`tests/`](tests/) and [`zetaris/`](zetaris/).

On 27 October 2026, these commands passed **35 application tests, 13 Zetaris tests, and 4 Meterless tests**. The Nightshift tests use a stubbed HTTP response; they do not substitute for a real hotspot request. The Meterless proof completed in the prior audit. The counts describe these commands, not a claim that every public user path has been tested.

| Input designed to trip the reviewer | Observed behavior |
| --- | --- |
| The same four staff hours claimed in full twice | An over-allocation question links both claims and the timesheet. |
| Two claims split the four hours 2 + 2 | Their linked total fits the source. |
| Two nearly matching staff names | Lens leaves source identity unconfirmed. |
| Ten claimed sessions with eight linked rows | The evidence gap stays open, even after a human note. |
| Malformed replacement import | The previous saved review is retained. |
| Zetaris source changes after import | Live confirmation abstains instead of rewriting the imported finding. |

**Unresolved evidence does not become a clear verdict.** Lens checks only records supplied or explicitly linked. It does not determine a funder’s policy, edit activity counts inside Lens, import PDFs, connect to an accounting system, or submit the finished report.

The public review uses Google sign-in and Supabase-backed saved state. Automated tests cover owner scoping and stale-write conflicts. A human cross-account isolation check and a real-organization records trial are outside the documented UAT coverage.

## Third-party code and license

The included Meterless reference and conformance code is from [Meterless/Meterless](https://github.com/Meterless/Meterless) and retains its [Apache 2.0 license](meterless/vendor/LICENSE). The results page fonts retain their SIL Open Font License notices. [Third-party notices](THIRD_PARTY_NOTICES.md) list their provenance. No license has been selected for Lens-authored source.
