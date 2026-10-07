alter table public.team_content
  add column korean_detail text;

alter table public.drivers
  add column previous_season_rank integer
  check (previous_season_rank is null or previous_season_rank > 0);

comment on column public.team_content.korean_detail is
  'Reviewed long-form Korean summary shown in the content detail modal.';

comment on column public.drivers.previous_season_rank is
  'Final drivers championship position from the season immediately before the event season.';

update public.teams
set sort_order = ranks.sort_order
from (values
  ('mclaren', 1),
  ('mercedes', 2),
  ('red-bull', 3),
  ('ferrari', 4),
  ('williams', 5),
  ('racing-bulls', 6),
  ('aston-martin', 7),
  ('haas', 8),
  ('audi', 9),
  ('alpine', 10),
  ('cadillac', 11)
) as ranks(code, sort_order)
where teams.code = ranks.code;

update public.drivers
set previous_season_rank = ranks.driver_rank
from (values
  ('NOR', 1),
  ('VER', 2),
  ('PIA', 3),
  ('RUS', 4),
  ('LEC', 5),
  ('HAM', 6),
  ('ANT', 7),
  ('ALB', 8),
  ('SAI', 9),
  ('ALO', 10),
  ('HUL', 11),
  ('HAD', 12),
  ('BEA', 13),
  ('LAW', 14),
  ('OCO', 15),
  ('STR', 16),
  ('GAS', 18),
  ('BOR', 19),
  ('COL', 20)
) as ranks(code, driver_rank)
where drivers.code = ranks.code;
