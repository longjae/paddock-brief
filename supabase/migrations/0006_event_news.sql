create table public.event_news (
  id uuid primary key default gen_random_uuid(),
  event_id uuid not null references public.events(id) on delete cascade,
  source_id uuid not null references public.sources(id) on delete restrict,
  category text not null check (category in ('race-report', 'analysis', 'interview', 'feature', 'preview', 'results')),
  title text not null,
  source_url text not null,
  korean_summary text not null,
  author text,
  tags text[] not null default '{}',
  team_codes text[] not null default '{}',
  published_at timestamptz,
  is_paywalled boolean not null default false,
  review_status text not null default 'pending' check (review_status in ('pending', 'approved', 'rejected')),
  collected_at timestamptz not null default now(),
  unique (event_id, source_url)
);

create index event_news_event_published_idx on public.event_news(event_id, published_at desc);
create index event_news_source_idx on public.event_news(source_id);
create index event_news_team_codes_idx on public.event_news using gin(team_codes);

alter table public.event_news enable row level security;
create policy "approved event news is readable" on public.event_news
  for select to anon, authenticated using (review_status = 'approved');

grant select on public.event_news to anon, authenticated;
grant all on public.event_news to service_role;
