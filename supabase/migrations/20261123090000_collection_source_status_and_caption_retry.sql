alter table public.collection_health add column if not exists source_status jsonb not null default '[]'::jsonb;
alter table public.videos add column if not exists transcript_retry_after timestamptz;
comment on column public.collection_health.source_status is 'Sanitized public official-source availability, not credentials or raw error bodies';
comment on column public.videos.transcript_retry_after is 'Earliest retry after an explicit public caption access block';
