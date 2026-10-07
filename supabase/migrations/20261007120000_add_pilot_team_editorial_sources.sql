insert into public.sources (code, name, base_url, source_kind, is_official) values
  ('mclaren-racing', 'McLaren Racing', 'https://www.mclaren.com', 'team-media', true),
  ('mercedes-amg-f1', 'Mercedes-AMG PETRONAS F1 Team', 'https://www.mercedesamgf1.com', 'team-media', true)
on conflict (code) do update set
  name = excluded.name,
  base_url = excluded.base_url,
  source_kind = excluded.source_kind,
  is_official = excluded.is_official;
