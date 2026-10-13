create table public.team_radio_transcripts (
  session_path text not null,
  path text not null,
  transcript text not null,
  translation text,
  created_at timestamptz not null default now(),
  primary key (session_path, path)
);

alter table public.team_radio_transcripts enable row level security;
create policy "team radio transcripts are readable" on public.team_radio_transcripts
  for select to anon, authenticated using (true);
grant select on public.team_radio_transcripts to anon, authenticated;
grant select, insert, update on public.team_radio_transcripts to service_role;
