# Public Lens demo: free-plan deployment plan

This is the original deployment plan, retained as a setup reference. The [public Lens app](https://lens-grant-review.onrender.com) is live with Google sign-in and saved reviews; the [public UAT record](PUBLIC_UAT_2026-10-26.md) covers one account and a phone check. A separate human two-account isolation test remains outstanding. The current local SQLite database and Meterless files cannot serve as durable storage on a free web host.

## Services and cost boundary

| Service | Select | Purpose | Free-plan constraint |
| --- | --- | --- | --- |
| Render | Free **web service**, Docker runtime, no payment method | Serve Lens at an `onrender.com` HTTPS URL; run Python and Node together | Sleeps after 15 minutes idle; first request can take about a minute. Files, including SQLite and Meterless state, disappear on sleep, restart, and deploy. Free plan provides 0.1 CPU, 512 MB RAM, and 750 running hours per month. Render may suspend a free service with unusually high outbound traffic. |
| Supabase | Free project | Google Auth and durable per-user review rows | Two active free projects, 500 MB database quota per project, 50,000 monthly active users, 5 GB egress. Inactive free projects may pause after about seven days and need the owner to resume them. Do not treat the free plan as a backup service. |
| Google Auth Platform | External OAuth web client, basic `openid email profile` scopes | Google sign-in through Supabase | Configure the Supabase callback URI exactly. For a public app, set the OAuth audience appropriately. Google's testing and publishing rules differ; check the consent screen before announcing open access. |

Render Free plus Supabase Free avoids a **new paid hosting plan**. It does not remove the existing AWS costs of the user's Zetaris network and cluster. A public Zetaris import using the owner's shared credentials could drive AWS usage; keep that endpoint unavailable to ordinary public accounts or constrain it to the owner and synthetic case. To avoid Render overage charges, do not add a payment method to the Render workspace. If free limits are exhausted, availability may stop rather than silently scaling.

The backend caps saved reviews at five per account, limits the five imported CSVs to 100 KB combined and 200 rows per file, caps each saved state plus Meterless history at 750 KB, and bounds expensive actions per account and globally on a single process. Meterless and Zetaris calls run one at a time. Before opening the URL to anyone, verify these limits on the deployed service. Public visitors should use synthetic records until the access controls, retention policy, and handling of uploaded charity records have been reviewed. Google sign-in identifies an account; it does not by itself make a shared API or shared Zetaris credential safe.

Do not use Render Free Postgres for the saved-review requirement: its free database expires after 30 days. Do not keep review state only in Render's local SQLite or `data/meterless` folder. Lens's public schema is [`docs/lens_reviews.sql`](lens_reviews.sql): `public.lens_reviews` stores a review's JSON state and Meterless event JSON, with a unique review ID and verified owner ID. The server must restore both on reopen. An authenticated user's server-verified ID must choose the row; never accept an owner ID from the browser. The schema revokes direct table access from browser roles and has no browser Row Level Security policies. The server's service-role connection is the only data path; test that a second signed-in account cannot read, edit, or export the first account's review, and that direct PostgREST browser calls cannot access the table.

## Setup sequence after the code passes local tests

1. Create a dedicated Supabase **Free** project. In its SQL Editor, apply [`docs/lens_reviews.sql`](lens_reviews.sql) after reviewing the table and browser-access revocations. Enable Google under Authentication > Providers; copy the Supabase callback URL shown there.
2. In Google Auth Platform, create a Web application OAuth client. Add the exact Supabase callback URI as an authorized redirect URI. Use only basic identity scopes, then configure the intended public audience/consent screen. Enter the Google Client ID and Client Secret into Supabase's Google provider form. Do not put either in Lens source control.
3. In Supabase Authentication > URL Configuration, set the final Render HTTPS URL as Site URL and add the app's exact login return URL to Redirect URLs. For local testing, add the local URL separately.
4. Connect the reviewed Lens GitHub repository to Render. Create a **Web Service**, choose **Docker** runtime and **Free** compute. The service must bind to `0.0.0.0` and Render's `PORT` environment variable (usually `10000`). The Docker image needs Python 3.11 or newer and Node 24 for the Meterless TypeScript bridge. Check that the final image runs within 512 MB RAM.
5. Set `SUPABASE_URL`, `SUPABASE_ANON_KEY`, and `SUPABASE_SERVICE_ROLE_KEY` in Render's Environment pane, not in Git. The legacy anon key is publishable to the browser for auth; the service-role key stays server-only. Set Zetaris values only if owner-only import is explicitly enabled. Never upload `.env.local`, `env.local.txt`, `data/`, private grant records, or screenshots containing credentials. The Supabase service-role key bypasses Row Level Security and must never be returned to the browser.
6. After the Render URL responds, run the normal user acceptance flow with two separate Google accounts: each signs in, loads/edits a synthetic case, checks it, refreshes, signs out/in, and reopens the saved review. Confirm each account cannot access the other's data even by calling API endpoints directly. Repeat after a Render redeploy or idle sleep to verify durable restore. Check denied requests, oversized uploads, Zetaris unavailability, and a paused Supabase project show understandable errors.
7. Record the tested public URL, date, account isolation result, persistence result, cold-start behavior, and known limits in the submission README. Monitor Render and Supabase usage dashboards while the link is public. Retain a private export/backup if saved reviews matter after the hackathon.

## When the public demo ends

Export any reviews the owner wants to keep before removing the service or database. Disable or delete the Render web service to take down the public URL, then remove its environment secrets and revoke its access to the GitHub repository. Disable the Google OAuth client and delete the Supabase project only after confirming the exports and the desired retention period; deleting the project removes every account's saved reviews. In the separate AWS account, suspend or delete the Zetaris compute and remove the Zetaris Quickstart CloudFormation stack when the owner is finished with it. The AWS network gateway can continue to accrue charges even while the compute is suspended. Review the AWS resource list and billing first, because storage resources can survive cluster or stack deletion.

## Source notes (checked 24 October 2026)

- [Render free instance behavior and limits](https://render.com/docs/free)
- [Render web service binding, Docker runtime, and public URL](https://render.com/docs/web-services)
- [Render environment variables and secret handling](https://render.com/docs/configure-environment-variables)
- [Supabase Free plan limits](https://supabase.com/docs/guides/platform/billing-on-supabase)
- [Supabase Free project pausing](https://supabase.com/docs/guides/platform/free-project-pausing)
- [Supabase Google provider configuration](https://supabase.com/docs/guides/auth/social-sign-in/auth-google)
- [Supabase Auth redirect URL configuration](https://supabase.com/docs/guides/auth/redirect-urls)
- [Supabase API key security](https://supabase.com/docs/guides/getting-started/api-keys)
- [Google OAuth publishing states](https://developers.google.com/identity/protocols/oauth2/production-readiness/overview)
