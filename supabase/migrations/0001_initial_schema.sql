create extension if not exists pgcrypto;

create table public.events (
  id uuid primary key default gen_random_uuid(),
  season integer not null check (season >= 1950),
  round integer not null check (round > 0),
  slug text not null unique,
  official_name text not null,
  short_name text not null,
  country text not null,
  locality text,
  circuit_name text not null,
  track_map_url text,
  date_label text,
  start_at timestamptz not null,
  end_at timestamptz not null,
  timezone text not null default 'UTC',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (season, round)
);

create table public.sessions (
  id uuid primary key default gen_random_uuid(),
  event_id uuid not null references public.events(id) on delete cascade,
  session_type text not null,
  name text not null,
  short_name text not null,
  starts_at timestamptz not null,
  ends_at timestamptz,
  status text not null default 'upcoming' check (status in ('done', 'live', 'upcoming')),
  unique (event_id, name)
);

create table public.sources (
  id uuid primary key default gen_random_uuid(),
  code text not null unique,
  name text not null,
  base_url text,
  source_kind text not null,
  is_official boolean not null default false,
  created_at timestamptz not null default now()
);

create table public.videos (
  id uuid primary key default gen_random_uuid(),
  event_id uuid not null references public.events(id) on delete cascade,
  source_id uuid references public.sources(id) on delete set null,
  platform text not null check (platform in ('youtube', 'f1tv', 'web')),
  external_id text,
  category text not null,
  title text not null,
  channel_name text,
  source_url text not null,
  duration_seconds integer,
  duration_label text,
  participants text[] not null default '{}',
  published_at timestamptz,
  is_embeddable boolean not null default false,
  review_status text not null default 'pending' check (review_status in ('pending', 'approved', 'rejected')),
  collected_at timestamptz not null default now(),
  unique (platform, external_id)
);

create table public.interviews (
  id uuid primary key default gen_random_uuid(),
  event_id uuid not null references public.events(id) on delete cascade,
  source_id uuid references public.sources(id) on delete set null,
  category text not null,
  title text not null,
  source_url text not null,
  participants text[] not null default '{}',
  original_body text,
  korean_summary text,
  published_at timestamptz,
  review_status text not null default 'draft' check (review_status in ('draft', 'reviewed', 'published')),
  source_hash text,
  collected_at timestamptz not null default now()
);

create table public.interview_segments (
  id bigint generated always as identity primary key,
  interview_id uuid not null references public.interviews(id) on delete cascade,
  sequence integer not null,
  speaker text,
  start_seconds integer,
  original_text text,
  korean_text text,
  review_status text not null default 'draft' check (review_status in ('draft', 'reviewed')),
  unique (interview_id, sequence)
);

create table public.tyre_allocations (
  id uuid primary key default gen_random_uuid(),
  event_id uuid not null unique references public.events(id) on delete cascade,
  hard_compound text not null,
  medium_compound text not null,
  soft_compound text not null,
  source_url text,
  announced_at timestamptz,
  updated_at timestamptz not null default now()
);

create table public.race_state_snapshots (
  id bigint generated always as identity primary key,
  session_id uuid not null references public.sessions(id) on delete cascade,
  captured_at timestamptz not null,
  lap integer,
  state jsonb not null,
  unique (session_id, captured_at)
);

create index videos_event_published_idx on public.videos(event_id, published_at desc);
create index interviews_event_published_idx on public.interviews(event_id, published_at desc);
create index race_state_session_captured_idx on public.race_state_snapshots(session_id, captured_at desc);

alter table public.events enable row level security;
alter table public.sessions enable row level security;
alter table public.sources enable row level security;
alter table public.videos enable row level security;
alter table public.interviews enable row level security;
alter table public.interview_segments enable row level security;
alter table public.tyre_allocations enable row level security;
alter table public.race_state_snapshots enable row level security;

-- Public F1 material is readable, but browser/client writes remain blocked.
create policy "public events are readable" on public.events for select to anon, authenticated using (true);
create policy "public sessions are readable" on public.sessions for select to anon, authenticated using (true);
create policy "public sources are readable" on public.sources for select to anon, authenticated using (true);
create policy "approved videos are readable" on public.videos for select to anon, authenticated using (review_status = 'approved');
create policy "published interviews are readable" on public.interviews for select to anon, authenticated using (review_status = 'published');
create policy "published interview segments are readable" on public.interview_segments
  for select to anon, authenticated
  using (exists (select 1 from public.interviews where interviews.id = interview_segments.interview_id and interviews.review_status = 'published'));
create policy "tyre allocations are readable" on public.tyre_allocations for select to anon, authenticated using (true);
create policy "race snapshots are readable" on public.race_state_snapshots for select to anon, authenticated using (true);

grant usage on schema public to anon, authenticated;
grant select on all tables in schema public to anon, authenticated;
grant usage on schema public to service_role;
grant all on all tables in schema public to service_role;
grant all on all sequences in schema public to service_role;

with inserted_event as (
  insert into public.events (
    season, round, slug, official_name, short_name, country, locality,
    circuit_name, track_map_url, date_label, start_at, end_at, timezone
  ) values (
    2026, 17, '2026-singapore',
    'FORMULA 1 SINGAPORE AIRLINES SINGAPORE GRAND PRIX 2026',
    'Singapore Grand Prix', 'Singapore', 'Marina Bay', 'Marina Bay',
    'https://media.formula1.com/content/dam/fom-website/2018-redesign-assets/Track%20icons%204x3/Singapore%20carbon.png',
    '10월 9일 — 10월 11일 · KST', '2026-10-09T08:30:00Z', '2026-10-11T14:00:00Z', 'Asia/Singapore'
  ) returning id
)
insert into public.sessions (event_id, session_type, name, short_name, starts_at, ends_at)
select id, item.session_type, item.name, item.short_name, item.starts_at::timestamptz, item.ends_at::timestamptz
from inserted_event
cross join (values
  ('practice', 'Practice 1', 'FP1', '2026-10-09T08:30:00Z', '2026-10-09T09:30:00Z'),
  ('sprint_qualifying', 'Sprint Qualifying', 'SQ', '2026-10-09T12:30:00Z', '2026-10-09T13:14:00Z'),
  ('sprint', 'Sprint', 'S', '2026-10-10T09:00:00Z', '2026-10-10T10:00:00Z'),
  ('qualifying', 'Qualifying', 'Q', '2026-10-10T13:00:00Z', '2026-10-10T14:00:00Z'),
  ('race', 'Race', 'R', '2026-10-11T12:00:00Z', '2026-10-11T14:00:00Z')
) as item(session_type, name, short_name, starts_at, ends_at);

insert into public.sources (code, name, base_url, source_kind, is_official) values
  ('formula1-youtube', 'Formula 1 YouTube', 'https://www.youtube.com/@Formula1', 'video', true),
  ('fia', 'FIA', 'https://www.fia.com/news/formula-1', 'transcript', true),
  ('pirelli', 'Pirelli', 'https://press.pirelli.com/', 'tyre', true),
  ('openf1', 'OpenF1', 'https://openf1.org/', 'timing', false);

insert into public.videos (
  event_id, source_id, platform, external_id, category, title, channel_name,
  source_url, duration_label, participants, review_status
)
select events.id, sources.id, 'web', null, '공식 영상 채널',
  '싱가포르 GP 인터뷰·브리핑 영상', 'Formula 1',
  'https://www.youtube.com/@Formula1/search?query=Singapore%202026%20interview',
  '공개 후 자동 반영', array['Formula 1 official channel'], 'approved'
from public.events cross join public.sources
where events.slug = '2026-singapore' and sources.code = 'formula1-youtube';

insert into public.videos (
  event_id, source_id, platform, category, title, channel_name,
  source_url, duration_label, participants, review_status
)
select events.id, sources.id, 'web', '공식 기자회견 원문',
  'FIA 기자회견·인터뷰 자료', 'FIA', 'https://www.fia.com/news/formula-1',
  '공개 후 번역 대상', array['FIA Formula One World Championship'], 'approved'
from public.events cross join public.sources
where events.slug = '2026-singapore' and sources.code = 'fia';

insert into public.interviews (
  event_id, source_id, category, title, source_url, participants,
  korean_summary, review_status
)
select events.id, sources.id, '공식 기자회견 원문', 'FIA 기자회견·인터뷰 자료',
  'https://www.fia.com/news/formula-1', array['FIA Formula One World Championship'],
  '긴 피트레인 손실 때문에 원스톱과 트랙 포지션의 가치가 크다.\n야간 경기지만 높은 노면 온도와 후륜 과열이 주요 변수다.\n예선 트래픽과 세이프티카 확률이 전략 선택에 큰 영향을 준다.',
  'published'
from public.events cross join public.sources
where events.slug = '2026-singapore' and sources.code = 'fia';

insert into public.tyre_allocations (
  event_id, hard_compound, medium_compound, soft_compound, source_url, announced_at
)
select id, 'C3', 'C4', 'C5',
  'https://press.pirelli.com/tyre-compound-selections-for-baku-sepang-and-singapore/',
  '2026-08-27T09:53:00Z'
from public.events where slug = '2026-singapore';
