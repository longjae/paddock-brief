create table if not exists public.content_collection_runs (
  id uuid primary key default gen_random_uuid(),
  event_id uuid references public.events(id) on delete set null,
  event_slug text not null,
  started_at timestamptz not null default now(),
  finished_at timestamptz not null default now(),
  status text not null check (status in ('succeeded', 'partial', 'failed', 'skipped')),
  discovered_count integer not null default 0,
  relevant_count integer not null default 0,
  inserted_count integer not null default 0,
  skipped_count integer not null default 0,
  failed_count integer not null default 0,
  errors jsonb not null default '[]'::jsonb,
  dry_run boolean not null default false
);

create index if not exists content_collection_runs_started_idx
  on public.content_collection_runs(started_at desc);

alter table public.content_collection_runs enable row level security;

grant all on public.content_collection_runs to service_role;

comment on table public.content_collection_runs is
  'Server-only audit trail for scheduled Formula 1 content collection jobs.';
