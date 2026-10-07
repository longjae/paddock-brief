alter table public.videos
  add column if not exists korean_summary text,
  add column if not exists korean_detail text,
  add column if not exists transcript_language text,
  add column if not exists transcript_status text not null default 'pending'
    check (transcript_status in ('pending', 'ready', 'unavailable', 'failed')),
  add column if not exists summarized_at timestamptz;

comment on column public.videos.korean_summary is
  'Short Korean synopsis generated only from the published video captions.';
comment on column public.videos.korean_detail is
  'Long-form, sectioned Korean summary generated only from the published video captions.';
comment on column public.videos.transcript_status is
  'Whether captions were available and successfully summarized; raw captions are not stored.';
