-- Only sanitized operational summaries are public; private audit errors stay private.
create table public.collection_health (
  kind text primary key check (kind in ('news', 'videos', 'radio')),
  event_slug text,
  status text not null check (status in ('succeeded', 'partial', 'failed', 'skipped')),
  finished_at timestamptz not null,
  last_success_at timestamptz,
  processed_count integer check (processed_count >= 0),
  failed_count integer not null default 0 check (failed_count >= 0),
  unavailable_count integer not null default 0 check (unavailable_count >= 0),
  translation_missing_count integer not null default 0 check (translation_missing_count >= 0),
  pending_count integer not null default 0 check (pending_count >= 0),
  metadata_unverified_count integer not null default 0 check (metadata_unverified_count >= 0)
);
alter table public.collection_health enable row level security;
revoke all on public.collection_health from anon, authenticated;
grant select on public.collection_health to anon, authenticated;
grant select, insert, update on public.collection_health to service_role;
create policy "public collection summaries are readable" on public.collection_health
  for select to anon, authenticated using (true);
create policy "service role writes collection summaries" on public.collection_health
  for all to service_role using (true) with check (true);
