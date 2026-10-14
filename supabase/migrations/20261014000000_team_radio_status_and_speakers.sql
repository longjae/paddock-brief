alter table public.team_radio_transcripts
  add column status text not null default 'ready'
    check (status in ('ready', 'unavailable')),
  add column segments jsonb not null default '[]'::jsonb
    check (jsonb_typeof(segments) = 'array');

comment on column public.team_radio_transcripts.status is 'ready when speech was transcribed; unavailable when the audio contained no usable speech';
comment on column public.team_radio_transcripts.segments is 'Timestamped speaker A/B segments from diarized transcription; no driver identity is inferred';
