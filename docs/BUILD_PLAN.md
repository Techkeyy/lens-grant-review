# Lens build and submission plan (23 October 2026)

## Confirmed constraints

Primary candidate: Track 02, The Agent That Can Explain Why. The finished agent must investigate grant-report questions across timesheets, expense records, activity records, and the two draft reports, then present evidence-backed findings. The public rules require **Zetaris and Meterless in every submission and Cursor in development** (Rule 5.1). Do not call a mock, a local calculation, or a README mention an integration.

The build window is 22 October 2026 00:00 UTC to 27 October 2026 23:45 UTC. Any product code from before the window must be disclosed. This folder's first code was created during the build window, but verify its provenance when committing; disclose any imported pre-existing product component. Existing skills, research, open-source libraries, and the prior idea should be distinguished from newly built code.

## Phase 2 evidence already obtained

`lens_core.py` reconciles a **synthetic, labelled** two-grant case by stable source IDs. It identifies 8 claimed hours from a four-hour timesheet, accepts valid 2+2 hour and 70+50 USD splits, records a 10 versus 8 activity support gap, and refuses to guess between similar staff names. A rerun after changing the duplicated allocation to 2+2 clears that conflict. Period, unit/currency, and staff/vendor identity mismatches now produce review findings. `python -m unittest discover -s tests -v` passed 10 tests on 23 October 2026. This proves only the isolated deterministic logic and fixture, not a full app, agent, or sponsor integration.

## Next gates, in order

1. **Access and proof:** get the user's sponsor setup links/credentials through local secure configuration without printing secrets. Prove real Zetaris connection, registered Lens data, cross-source query, and returned rows. Prove actual Meterless World Model reference runtime write/read/restart against Lens review state. Establish a meaningful Cursor development action and keep truthful evidence of it. Docker CLI exists but its daemon was not usable in the current check; choose a reproducible alternate if needed.
2. **Normal-user vertical slice:** import the same CSVs through the interface, visibly map records to grants, run a check against actual loaded records, open each original row with arithmetic, correct or explain a finding, rerun, refresh, and reopen saved state. A new user must complete this without terminal help. Keep uncertain matches and unsupported claims clearly labelled. Use the relevant `design-skill` after workflow exists.
3. **Agent behavior:** let the agent decide which source to investigate next and gather cited records through real tools. Keep quantity arithmetic deterministic and the human decision authoritative. Capture a trace so judges can see why a finding was produced.
4. **Independent review:** apply `audit-skill`, `project-edge`, and `perfect-readme` to the working path. Run a fresh-user UAT. Fix any misleading clear status, missing source opening, failed refresh persistence, or sponsor claim without a real call.
5. **Submission artifacts:** record a 1–4 minute workflow video showing both integrations (Rule 6.1); create the required deck with problem/users, solution, architecture, stack, integrations, unique sponsor use, visuals, future work (Rule 6.2); publish all source and a tested setup/usage/dependency README to GitHub (Rule 6.3); fill the explanation of Zetaris, Meterless, Cursor, NVIDIA contribution, and sponsor uniqueness (Rule 6.4). Inspect the authenticated HackOS form for extra fields and requirements. Do not state NVIDIA use unless it really contributes.

## Stop conditions

- No stable source identity or original-record location: show `needs review`, never a conclusive calculation.
- No live Zetaris or Meterless proof: the mandatory integration is unfinished.
- No genuine Cursor use: the development requirement is unfinished.
- No successful new-user path with saved correction/rerun: product remains unfinished even if unit tests pass.
