create table public.general_news (
  id uuid primary key default gen_random_uuid(),
  source_id uuid not null references public.sources(id) on delete restrict,
  source_url text not null unique,
  category text not null check (category in ('race-report', 'analysis', 'interview', 'feature', 'preview', 'results')),
  title text not null,
  korean_summary text not null,
  korean_detail text not null,
  author text,
  tags text[] not null default '{}',
  team_codes text[] not null default '{}',
  driver_codes text[] not null default '{}',
  published_at timestamptz not null,
  review_status text not null default 'approved' check (review_status in ('pending', 'approved', 'rejected')),
  collected_at timestamptz not null default now()
);

create index general_news_published_idx on public.general_news(published_at desc);
alter table public.general_news enable row level security;
revoke all on public.general_news from anon, authenticated;
grant select on public.general_news to anon, authenticated;
grant all on public.general_news to service_role;
create policy "approved general news is readable" on public.general_news
  for select to anon, authenticated using (review_status = 'approved');
