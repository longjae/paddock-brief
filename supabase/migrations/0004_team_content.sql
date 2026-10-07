create table public.teams (
  id uuid primary key default gen_random_uuid(),
  code text not null unique,
  name text not null unique,
  colour text not null,
  sort_order integer not null default 0
);

create table public.team_content (
  id uuid primary key default gen_random_uuid(),
  event_id uuid not null references public.events(id) on delete cascade,
  team_id uuid not null references public.teams(id) on delete cascade,
  source_id uuid references public.sources(id) on delete set null,
  platform text not null check (platform in ('web', 'youtube', 'x')),
  content_kind text not null check (content_kind in ('interview', 'team-report', 'video', 'social')),
  external_id text,
  title text not null,
  source_url text not null,
  participants text[] not null default '{}',
  korean_summary text not null,
  published_at timestamptz,
  is_embeddable boolean not null default false,
  review_status text not null default 'pending' check (review_status in ('pending', 'approved', 'rejected')),
  collected_at timestamptz not null default now(),
  unique (event_id, team_id, source_url)
);

create index team_content_event_published_idx on public.team_content(event_id, published_at desc);
create index team_content_team_published_idx on public.team_content(team_id, published_at desc);

alter table public.teams enable row level security;
alter table public.team_content enable row level security;

create policy "teams are readable" on public.teams for select to anon, authenticated using (true);
create policy "approved team content is readable" on public.team_content
  for select to anon, authenticated using (review_status = 'approved');

grant select on public.teams, public.team_content to anon, authenticated;
grant all on public.teams, public.team_content to service_role;
