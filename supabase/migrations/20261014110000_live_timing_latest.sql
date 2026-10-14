create table public.live_timing_latest (
  event_slug text primary key,
  session_path text not null,
  captured_at timestamptz not null,
  state jsonb not null,
  updated_at timestamptz not null default now(),
  constraint live_timing_state_object check (jsonb_typeof(state) = 'object')
);

alter table public.live_timing_latest enable row level security;
revoke all on public.live_timing_latest from anon, authenticated;
create policy "live timing snapshots are readable" on public.live_timing_latest
  for select to anon, authenticated using (true);
grant select on public.live_timing_latest to anon, authenticated;
grant select, insert, update on public.live_timing_latest to service_role;
