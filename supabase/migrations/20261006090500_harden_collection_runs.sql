create index if not exists content_collection_runs_event_idx
  on public.content_collection_runs(event_id);

create policy "service role manages collection runs"
  on public.content_collection_runs
  for all
  to service_role
  using (true)
  with check (true);
