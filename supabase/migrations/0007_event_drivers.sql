create table public.drivers (
  id uuid primary key default gen_random_uuid(),
  code text not null unique,
  full_name text not null unique,
  permanent_number integer not null,
  nationality text not null,
  profile_url text,
  created_at timestamptz not null default now()
);

create table public.event_drivers (
  id uuid primary key default gen_random_uuid(),
  event_id uuid not null references public.events(id) on delete cascade,
  driver_id uuid not null references public.drivers(id) on delete cascade,
  team_id uuid not null references public.teams(id) on delete restrict,
  grid_position integer,
  result_position integer,
  result_status text not null default 'entered',
  points numeric(5,2) not null default 0,
  unique (event_id, driver_id)
);

alter table public.event_news add column driver_codes text[] not null default '{}';

create index event_drivers_event_idx on public.event_drivers(event_id);
create index event_drivers_driver_idx on public.event_drivers(driver_id);
create index event_drivers_team_idx on public.event_drivers(team_id);
create index event_news_driver_codes_idx on public.event_news using gin(driver_codes);

alter table public.drivers enable row level security;
alter table public.event_drivers enable row level security;

create policy "drivers are readable" on public.drivers for select to anon, authenticated using (true);
create policy "event drivers are readable" on public.event_drivers for select to anon, authenticated using (true);

grant select on public.drivers, public.event_drivers to anon, authenticated;
grant all on public.drivers, public.event_drivers to service_role;
