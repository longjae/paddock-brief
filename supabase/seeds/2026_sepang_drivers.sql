insert into public.drivers (code, full_name, permanent_number, nationality, profile_url) values
  ('NOR', 'Lando Norris', 1, 'Great Britain', 'https://www.formula1.com/en/drivers/lando-norris'),
  ('PIA', 'Oscar Piastri', 81, 'Australia', 'https://www.formula1.com/en/drivers/oscar-piastri'),
  ('RUS', 'George Russell', 63, 'Great Britain', 'https://www.formula1.com/en/drivers/george-russell'),
  ('ANT', 'Kimi Antonelli', 12, 'Italy', 'https://www.formula1.com/en/drivers/kimi-antonelli'),
  ('VER', 'Max Verstappen', 3, 'Netherlands', 'https://www.formula1.com/en/drivers/max-verstappen'),
  ('HAD', 'Isack Hadjar', 6, 'France', 'https://www.formula1.com/en/drivers/isack-hadjar'),
  ('HAM', 'Lewis Hamilton', 44, 'Great Britain', 'https://www.formula1.com/en/drivers/lewis-hamilton'),
  ('LEC', 'Charles Leclerc', 16, 'Monaco', 'https://www.formula1.com/en/drivers/charles-leclerc'),
  ('SAI', 'Carlos Sainz', 55, 'Spain', 'https://www.formula1.com/en/drivers/carlos-sainz'),
  ('ALB', 'Alexander Albon', 23, 'Thailand', 'https://www.formula1.com/en/drivers/alexander-albon'),
  ('LAW', 'Liam Lawson', 30, 'New Zealand', 'https://www.formula1.com/en/drivers/liam-lawson'),
  ('LIN', 'Arvid Lindblad', 41, 'Great Britain', 'https://www.formula1.com/en/drivers/arvid-lindblad'),
  ('ALO', 'Fernando Alonso', 14, 'Spain', 'https://www.formula1.com/en/drivers/fernando-alonso'),
  ('STR', 'Lance Stroll', 18, 'Canada', 'https://www.formula1.com/en/drivers/lance-stroll'),
  ('BEA', 'Oliver Bearman', 87, 'Great Britain', 'https://www.formula1.com/en/drivers/oliver-bearman'),
  ('OCO', 'Esteban Ocon', 31, 'France', 'https://www.formula1.com/en/drivers/esteban-ocon'),
  ('HUL', 'Nico Hulkenberg', 27, 'Germany', 'https://www.formula1.com/en/drivers/nico-hulkenberg'),
  ('BOR', 'Gabriel Bortoleto', 5, 'Brazil', 'https://www.formula1.com/en/drivers/gabriel-bortoleto'),
  ('GAS', 'Pierre Gasly', 10, 'France', 'https://www.formula1.com/en/drivers/pierre-gasly'),
  ('COL', 'Franco Colapinto', 43, 'Argentina', 'https://www.formula1.com/en/drivers/franco-colapinto'),
  ('PER', 'Sergio Perez', 11, 'Mexico', 'https://www.formula1.com/en/drivers/sergio-perez'),
  ('BOT', 'Valtteri Bottas', 77, 'Finland', 'https://www.formula1.com/en/drivers/valtteri-bottas')
on conflict (code) do update set
  full_name = excluded.full_name,
  permanent_number = excluded.permanent_number,
  nationality = excluded.nationality,
  profile_url = excluded.profile_url;

insert into public.event_drivers (
  event_id, driver_id, team_id, result_position, result_status, points
)
select events.id, drivers.id, teams.id, item.position, item.status, item.points
from public.events
cross join (values
  ('VER', 'red-bull', 1, 'classified', 25.0), ('ANT', 'mercedes', 2, 'classified', 18.0),
  ('HAM', 'ferrari', 3, 'classified', 15.0), ('LEC', 'ferrari', 4, 'classified', 12.0),
  ('HAD', 'red-bull', 5, 'classified', 10.0), ('PIA', 'mclaren', 6, 'classified', 8.0),
  ('LAW', 'racing-bulls', 7, 'classified', 6.0), ('ALO', 'aston-martin', 8, 'classified', 4.0),
  ('NOR', 'mclaren', 9, 'classified', 2.0), ('LIN', 'racing-bulls', 10, 'classified', 1.0),
  ('HUL', 'audi', 11, 'classified', 0.0), ('STR', 'aston-martin', 12, 'classified', 0.0),
  ('COL', 'alpine', 13, 'classified', 0.0), ('BEA', 'haas', 14, 'classified', 0.0),
  ('OCO', 'haas', 15, 'classified', 0.0), ('GAS', 'alpine', 16, 'classified', 0.0),
  ('SAI', 'williams', 17, 'classified', 0.0), ('BOR', 'audi', 18, 'classified', 0.0),
  ('PER', 'cadillac', 19, 'classified', 0.0), ('RUS', 'mercedes', 20, 'retired', 0.0),
  ('ALB', 'williams', 21, 'retired', 0.0), ('BOT', 'cadillac', 22, 'retired', 0.0)
) as item(driver_code, team_code, position, status, points)
join public.drivers on drivers.code = item.driver_code
join public.teams on teams.code = item.team_code
where events.slug = '2026-bahrain'
on conflict (event_id, driver_id) do update set
  team_id = excluded.team_id,
  result_position = excluded.result_position,
  result_status = excluded.result_status,
  points = excluded.points;

update public.event_news set driver_codes = array['VER','ANT','HAM','RUS']
where source_url in (
  'https://www.skysports.com/f1/news/13594860/bahrain-gp-in-malaysia-max-verstappen-wins-first-race-of-2026-f1-season-in-wild-rain-hit-grand-prix-as-lewis-hamilton-surges-back',
  'https://www.motorsport.com/f1/news/f1-bahrain-gp-in-malaysia-report/10861843/'
);
update public.event_news set driver_codes = array['RUS','VER','HAM']
where source_url = 'https://www.the-race.com/formula-1/f1-drivers-blast-horrible-malaysia-formation-lap/';
update public.event_news set driver_codes = array['ANT','RUS','HAM','LEC','HAD','PIA','LAW','ALO','NOR','LIN']
where category = 'results' and event_id = (select id from public.events where slug = '2026-bahrain');
update public.event_news set driver_codes = array['RUS','ANT']
where source_url = 'https://www.the-race.com/formula-1/first-clues-major-mercedes-f1-upgrade-at-sepang/';

insert into public.event_news (
  event_id, source_id, category, title, source_url, korean_summary,
  author, tags, team_codes, driver_codes, published_at, review_status
)
select events.id, sources.id, item.category, item.title, item.source_url,
  item.summary, 'Formula 1', item.tags, item.team_codes, item.driver_codes,
  item.published_at::timestamptz, 'approved'
from public.events
join public.sources on sources.code = 'formula1-editorial'
cross join (values
  ('interview', '러셀: 반복된 리타이어가 너무 가혹하다', 'https://www.formula1.com/en/latest/article/its-happened-too-many-times-russell-reacts-to-bahrain-gp-retirement-after-relentless-run.1B0R4wN2ZtsIKYZ8covCZa', '러셀은 포디엄이 유력했던 상황에서 파워유닛 문제로 멈춘 뒤 반복되는 불운이 가혹하지만 계속 싸우겠다고 말했다.', array['선수 인터뷰','리타이어'], array['mercedes'], array['RUS'], '2026-10-04T12:32:00Z'),
  ('interview', '노리스: 세이프티카 뒤 코스 이탈 상황', 'https://www.formula1.com/en/latest/article/i-swore-a-lot-norris-explains-off-track-moment-behind-safety-car-in-malaysia-after-p9-finish.65txlrZKsVDzVDMjhZiQ8m', '노리스는 늦은 세이프티카 상황에서 앞차들이 급격히 뭉치며 코스를 벗어났고 그 실수로 순위를 잃었다고 설명했다.', array['선수 인터뷰','세이프티카'], array['mclaren'], array['NOR'], '2026-10-04T14:01:00Z'),
  ('interview', '노리스: 맥라렌은 예선 페이스에서 크게 뒤처졌다', 'https://www.formula1.com/en/latest/article/norris-admits-mclaren-a-long-way-off-the-pace-after-tough-qualifying-in-malaysia.s821hQJMmeebtQF8Bn5vC', '노리스는 처음 달린 세팡에서 점진적으로 적응했지만 맥라렌이 레드불과 경쟁 팀의 예선 페이스에 미치지 못했다고 평가했다.', array['선수 인터뷰','예선'], array['mclaren'], array['NOR'], '2026-10-03T11:52:00Z')
) as item(category, title, source_url, summary, tags, team_codes, driver_codes, published_at)
where events.slug = '2026-bahrain'
on conflict (event_id, source_url) do update set
  korean_summary = excluded.korean_summary,
  driver_codes = excluded.driver_codes,
  review_status = excluded.review_status;
