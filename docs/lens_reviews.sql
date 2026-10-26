-- Run in the Supabase SQL editor for the public Lens deployment.
-- Browser clients must not access this table directly. The Lens server checks
-- each access token with Supabase Auth and scopes all service-role queries.
create table if not exists public.lens_reviews (
  id uuid primary key,
  owner_id uuid not null references auth.users(id) on delete cascade,
  title text not null check (char_length(title) between 1 and 120),
  state jsonb not null default '{"phase":"empty","revision":0}'::jsonb,
  meterless_data jsonb,
  row_version integer not null default 0 check (row_version >= 0),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists lens_reviews_owner_updated_idx
  on public.lens_reviews(owner_id, updated_at desc);

alter table public.lens_reviews enable row level security;

-- Revoke browser access, including policies from an earlier version of this
-- schema. A signed-in browser must not be able to replace state,
-- meterless_data, or row_version outside Lens's checks and CAS transaction.
drop policy if exists "Owners can read their reviews" on public.lens_reviews;
drop policy if exists "Owners can create their reviews" on public.lens_reviews;
drop policy if exists "Owners can update their reviews" on public.lens_reviews;
revoke all on table public.lens_reviews from anon, authenticated;
grant select, insert, update on table public.lens_reviews to service_role;

-- There are intentionally no anon/authenticated RLS policies. The server's
-- service-role client bypasses RLS and must apply the verified owner filter.

-- Review deletion is intentionally unavailable in the first public version.
