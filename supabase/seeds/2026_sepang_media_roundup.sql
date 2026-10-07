insert into public.sources (code, name, base_url, source_kind, is_official) values
  ('motorsport', 'Motorsport.com', 'https://www.motorsport.com/f1/', 'media', false),
  ('autosport', 'Autosport', 'https://www.autosport.com/f1/', 'media', false),
  ('the-race', 'The Race', 'https://www.the-race.com/formula-1/', 'media', false),
  ('planet-f1', 'PlanetF1', 'https://www.planetf1.com/', 'media', false),
  ('racingnews365', 'RacingNews365', 'https://racingnews365.com/', 'media', false),
  ('crash', 'Crash.net', 'https://www.crash.net/f1', 'media', false)
on conflict (code) do update set name = excluded.name, base_url = excluded.base_url, source_kind = excluded.source_kind;

insert into public.event_news (
  event_id, source_id, category, title, source_url, korean_summary,
  author, tags, team_codes, published_at, is_paywalled, review_status
)
select events.id, sources.id, item.category, item.title, item.source_url,
  item.summary, item.author, item.tags, item.team_codes,
  item.published_at::timestamptz, item.is_paywalled, 'approved'
from public.events
cross join (values
  ('formula1-editorial', 'analysis', '말레이시아 레이스 후 팀별 공식 코멘트', 'https://www.formula1.com/en/latest/article/what-the-teams-said-race-day-in-bahrain-2026.4kwHL7ygJLqVlSMHhAj6ce', '11개 팀의 드라이버와 팀 대표가 젖은 노면의 타이어 선택, 세이프티카, 경기 결과를 직접 평가한다.', 'Formula 1', array['팀 코멘트','인터뷰','전략'], array['red-bull','mercedes','ferrari','mclaren','racing-bulls','aston-martin','audi','alpine','haas','williams','cadillac'], '2026-10-04T14:11:00Z', false),
  ('sky-sports-f1', 'race-report', '베르스타펜, 비 내린 세팡에서 시즌 첫 승', 'https://www.skysports.com/f1/news/13594860/bahrain-gp-in-malaysia-max-verstappen-wins-first-race-of-2026-f1-season-in-wild-rain-hit-grand-prix-as-lewis-hamilton-surges-back', '두 차례 출발 지연과 세이프티카가 나온 혼란 속에서 베르스타펜이 우승했고 안토넬리와 해밀턴이 포디엄을 완성한 과정을 정리했다.', 'Sky Sports F1', array['레이스','우천','결과'], array['red-bull','mercedes','ferrari'], '2026-10-04T11:42:00Z', false),
  ('motorsport', 'race-report', '베르스타펜 우승과 러셀 리타이어로 끝난 혼전', 'https://www.motorsport.com/f1/news/f1-bahrain-gp-in-malaysia-report/10861843/', '젖은 노면에서 발생한 2026 파워유닛 소프트웨어 문제, 길어진 출발 절차, 베르스타펜과 메르세데스의 선두 싸움을 기술적으로 정리했다.', 'Ben Vinel', array['레이스','파워유닛','기술'], array['red-bull','mercedes'], '2026-10-04T10:31:00Z', false),
  ('motorsport', 'analysis', '세팡 레이스에서 확인된 다섯 가지 핵심', 'https://www.motorsport.com/f1/news/five-quick-takeaways-from-bahrain-gp-in-malaysia/10861841/', '레드불의 시즌 첫 승, 애스턴 마틴의 회복, 2026 파워유닛 문제 등 레이스 이후 주목할 흐름 다섯 가지를 분석한다.', 'Motorsport.com', array['분석','핵심 장면','기술'], array['red-bull','aston-martin','mercedes'], '2026-10-04T10:24:00Z', false),
  ('autosport', 'feature', '바레인 GP 패독은 어떻게 말레이시아로 이동했나', 'https://www.autosport.com/f1/news/how-bahrain-transplanted-its-f1-paddock-onto-malaysia/10861485/', '두 달이라는 짧은 기간에 바레인 조직위와 세팡이 운영 인력, 브랜딩과 시설을 함께 준비한 과정을 현장 인터뷰로 다룬다.', 'Filip Cleeren', array['운영','비즈니스','세팡'], array[]::text[], '2026-10-03T11:01:00Z', false),
  ('the-race', 'analysis', '드라이버들이 비판한 세팡 출발 지연', 'https://www.the-race.com/formula-1/f1-drivers-blast-horrible-malaysia-formation-lap/', '러셀, 베르스타펜, 해밀턴이 긴 출발 지연과 포메이션 랩의 기술적 혼란을 평가하고 개선을 요구한 내용을 모았다.', 'Josh Suttill', array['드라이버 반응','출발 절차','우천'], array['mercedes','red-bull','ferrari'], '2026-10-04T13:00:00Z', false),
  ('the-race', 'analysis', '업그레이드된 메르세데스의 첫 기술 평가', 'https://www.the-race.com/formula-1/first-clues-major-mercedes-f1-upgrade-at-sepang/', '게리 앤더슨이 세팡에 투입된 W17 대규모 업그레이드의 공력 구성과 기대 효과를 기술 관점에서 분석한다.', 'Gary Anderson', array['기술','업그레이드','공력'], array['mercedes'], '2026-10-01T12:00:00Z', false),
  ('planet-f1', 'results', '세팡 결승 전체 결과와 주요 리타이어', 'https://www.planetf1.com/news/f1-results-bahrain-grand-prix-malaysia-2026-race', '베르스타펜부터 최종 완주자까지 공식 결승 순위와 격차, 러셀·알본·보타스의 리타이어를 한눈에 정리했다.', 'Oliver Harden', array['결과','순위','결승'], array[]::text[], '2026-10-05T00:00:00Z', false),
  ('racingnews365', 'results', '2026 바레인 GP 인 말레이시아 결과', 'https://racingnews365.com/2026-f1-bahrain-grand-prix-in-malaysia-results-sepang-international-circuit', '비와 기술 문제로 혼란스러웠던 세팡 레이스의 결과와 챔피언십에 미친 영향을 요약한다.', 'Samuel Coop', array['결과','챔피언십'], array['red-bull','mercedes','ferrari'], '2026-10-05T01:20:00Z', false),
  ('crash', 'analysis', '세팡에서 팀들이 마주한 가장 큰 과제', 'https://www.crash.net/f1/news/1106120/1/biggest-challenge-facing-f1-teams-bahrain-gp-malaysia', '거친 노면이 만든 높은 타이어 열화와 변화하기 쉬운 날씨가 셋업 및 레이스 전략에 어떤 부담을 줬는지 드라이버 코멘트로 설명한다.', 'Crash.net', array['타이어','전략','노면'], array['ferrari','williams','cadillac','racing-bulls'], '2026-10-03T08:00:00Z', false)
) as item(source_code, category, title, source_url, summary, author, tags, team_codes, published_at, is_paywalled)
join public.sources on sources.code = item.source_code
where events.slug = '2026-bahrain'
on conflict (event_id, source_url) do update set
  source_id = excluded.source_id,
  category = excluded.category,
  title = excluded.title,
  korean_summary = excluded.korean_summary,
  author = excluded.author,
  tags = excluded.tags,
  team_codes = excluded.team_codes,
  published_at = excluded.published_at,
  is_paywalled = excluded.is_paywalled,
  review_status = excluded.review_status;
