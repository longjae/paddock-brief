insert into public.teams (code, name, colour, sort_order) values
  ('red-bull', 'Red Bull Racing', '#4781D7', 3),
  ('mercedes', 'Mercedes', '#00D7B6', 2),
  ('ferrari', 'Ferrari', '#ED1131', 4),
  ('mclaren', 'McLaren', '#F47600', 1),
  ('racing-bulls', 'Racing Bulls', '#6C98FF', 6),
  ('aston-martin', 'Aston Martin', '#229971', 7),
  ('audi', 'Audi', '#F50537', 9),
  ('alpine', 'Alpine', '#00A1E8', 10),
  ('haas', 'Haas', '#B6BABD', 8),
  ('williams', 'Williams', '#1868DB', 5),
  ('cadillac', 'Cadillac', '#D1D1D1', 11)
on conflict (code) do update set name = excluded.name, colour = excluded.colour, sort_order = excluded.sort_order;

insert into public.sources (code, name, base_url, source_kind, is_official) values
  ('formula1-editorial', 'Formula 1', 'https://www.formula1.com/en/latest', 'editorial', true),
  ('sky-sports-f1', 'Sky Sports F1', 'https://www.skysports.com/f1', 'media', false),
  ('redbull-racing', 'Oracle Red Bull Racing', 'https://www.redbullracing.com/', 'team-media', true),
  ('x', 'X', 'https://x.com/', 'social', false)
on conflict (code) do update set name = excluded.name, base_url = excluded.base_url, source_kind = excluded.source_kind, is_official = excluded.is_official;

with race_report as (
  select
    events.id as event_id,
    teams.id as team_id,
    sources.id as source_id,
    item.title,
    item.summary,
    item.participants
  from public.events
  join public.sources on sources.code = 'formula1-editorial'
  cross join (values
    ('red-bull', '레드불 레이스 코멘트', '베르스타펜은 변화하는 노면에서 타이어 판단과 세이프티카 재시작을 완벽히 처리해 시즌 첫 승과 레드불 포드 파워트레인의 첫 승을 만들었다. 하자르는 막판 언더스티어와 출력 문제로 5위에 만족해야 했다.', array['Max Verstappen','Isack Hadjar','Laurent Mekies']),
    ('mercedes', '메르세데스 레이스 코멘트', '안토넬리는 인터미디어트 출발로 선두에 올랐고 최종 2위를 지켰다. 러셀은 포디엄이 유력했지만 종료 직전 파워유닛 문제로 리타이어해 팀은 속도와 신뢰성 모두를 재점검하게 됐다.', array['Kimi Antonelli','George Russell','Toto Wolff']),
    ('ferrari', '페라리 레이스 코멘트', '두 차 모두 슬릭으로 출발해 초반 크게 밀렸지만 해밀턴은 3위, 르클레르는 4위까지 회복했다. 팀은 초기 타이어 판단은 틀렸지만 이후 전략과 실행은 침착했다고 평가했다.', array['Lewis Hamilton','Charles Leclerc','Fred Vasseur']),
    ('mclaren', '맥라렌 레이스 코멘트', '슬릭 출발 선택으로 두 드라이버가 손해를 봤다. 피아스트리와 노리스는 이후 서로 다른 하드·소프트 전략으로 회복했지만 경쟁 팀의 발전에 대응할 성능 개선이 필요하다고 정리했다.', array['Lando Norris','Oscar Piastri']),
    ('racing-bulls', '레이싱 불스 레이스 코멘트', '인터미디어트 출발이 적중했고 로슨과 린드블라드가 모두 포인트를 기록했다. 린드블라드는 마지막 랩 추월로 10위를 확보했고 팀은 전략 실행을 가장 큰 성과로 꼽았다.', array['Liam Lawson','Arvid Lindblad']),
    ('aston-martin', '애스턴 마틴 레이스 코멘트', '알론소가 하드 타이어의 페이스를 살려 8위로 시즌 두 번째 포인트 피니시를 만들었다. 스트롤도 12위까지 올라 팀의 시즌 최고 결과에 힘을 보탰다.', array['Fernando Alonso','Lance Stroll','Mike Krack']),
    ('audi', '아우디 레이스 코멘트', '두 차 모두 일찍 인터미디어트로 전환해 회복했지만 보르톨레토의 페널티와 훌켄베르크의 마지막 랩 순위 하락으로 아쉽게 포인트를 놓쳤다.', array['Nico Hulkenberg','Gabriel Bortoleto']),
    ('alpine', '알핀 레이스 코멘트', '변화하는 노면과 세이프티카 타이밍 속에서 전략 기회를 찾았지만 포인트권까지 이어지지는 못했다. 팀은 싱가포르를 앞두고 타이어 운용 데이터를 재검토한다.', array['Pierre Gasly','Franco Colapinto']),
    ('haas', '하스 레이스 코멘트', '엇갈린 출발 타이어 선택 뒤 오콘의 초반 페이스는 좋았지만 피트 진입과 타이어 관리에서 손해를 봤다. 팀은 의사결정과 실행 모두 개선 여지가 있다고 평가했다.', array['Esteban Ocon','Oliver Bearman','Ayao Komatsu']),
    ('williams', '윌리엄스 레이스 코멘트', '인터미디어트 출발로 두 차 모두 한때 톱10에 진입했지만 더블 스택과 세이프티카, 알본의 기어박스 문제로 결과를 지키지 못했다.', array['Carlos Sainz','Alex Albon','James Vowles']),
    ('cadillac', '캐딜락 레이스 코멘트', '첫 본격 웨트 레이스에서 두 차 모두 슬릭 출발을 택했다. 보타스는 젖은 노면에서 스핀해 리타이어했고 페레스는 여러 차례 타이어를 교체하며 완주와 데이터 확보에 집중했다.', array['Sergio Perez','Valtteri Bottas'])
  ) as item(team_code, title, summary, participants)
  join public.teams on teams.code = item.team_code
  where events.slug = '2026-bahrain'
)
insert into public.team_content (
  event_id, team_id, source_id, platform, content_kind, title, source_url,
  participants, korean_summary, published_at, review_status
)
select event_id, team_id, source_id, 'web', 'team-report', title,
  'https://www.formula1.com/en/latest/article/what-the-teams-said-race-day-in-bahrain-2026.4kwHL7ygJLqVlSMHhAj6ce',
  participants, summary, '2026-10-04T14:11:00Z', 'approved'
from race_report
on conflict (event_id, team_id, source_url) do update set
  title = excluded.title, participants = excluded.participants,
  korean_summary = excluded.korean_summary, published_at = excluded.published_at,
  review_status = excluded.review_status;

insert into public.team_content (
  event_id, team_id, source_id, platform, content_kind, title, source_url,
  participants, korean_summary, published_at, is_embeddable, review_status
)
select events.id, teams.id, sources.id, item.platform, item.content_kind,
  item.title, item.source_url, item.participants, item.summary,
  item.published_at::timestamptz, item.is_embeddable, 'approved'
from public.events
join public.teams on teams.code = 'red-bull'
join public.sources on sources.code = 'redbull-racing'
cross join (values
  ('web', 'video', '막스의 말레이시아 우승 디브리프', 'https://www.redbullracing.com/int-en/videos/max-wins-bahrain-grand-prix-2026', array['Max Verstappen'], '베르스타펜이 세팡 우승과 레드불 포드 파워트레인의 첫 승이 팀에 갖는 의미를 1분 분량으로 설명한다.', '2026-10-04T13:00:00Z', true)
) as item(platform, content_kind, title, source_url, participants, summary, published_at, is_embeddable)
where events.slug = '2026-bahrain'
on conflict (event_id, team_id, source_url) do update set korean_summary = excluded.korean_summary, review_status = excluded.review_status;

insert into public.team_content (
  event_id, team_id, source_id, platform, content_kind, title, source_url,
  participants, korean_summary, published_at, is_embeddable, review_status
)
select events.id, teams.id, sources.id, 'web', 'interview', item.title,
  item.source_url, item.participants, item.summary, item.published_at::timestamptz,
  true, 'approved'
from public.events
join public.teams on teams.code = 'mercedes'
join public.sources on sources.code = 'sky-sports-f1'
cross join (values
  ('업그레이드 이후 예선 페이스를 분석한 메르세데스', 'https://www.skysports.com/f1/news/13594549/mercedes-boss-toto-wolff-admits-confusion-over-lack-of-qualifying-pace-following-upgrades-at-bahrain-gp-in-malaysia', array['Toto Wolff','George Russell','Kimi Antonelli'], '볼프는 대규모 업그레이드가 기대한 랩타임 개선으로 이어지지 않은 이유를 데이터로 확인해야 한다고 말했다. 러셀과 안토넬리는 거친 노면과 높은 온도에서의 타이어 과열을 핵심 문제로 꼽았다.', '2026-10-03T12:08:00Z'),
  ('러셀 리타이어 이후 메르세데스 반응', 'https://www.skysports.com/f1/news/13594862/george-russell-mercedes-boss-toto-wolff-massively-annoyed-by-bahrain-gp-unreliability-with-driver-now-beyond-disappointment', array['Toto Wolff','George Russell'], '종료 직전 파워유닛 고장으로 러셀이 포디엄과 중요한 챔피언십 포인트를 잃었다. 볼프는 반복되는 신뢰성 문제를 용납할 수 없다고 했고 러셀은 실망 속에서도 계속 싸우겠다고 말했다.', '2026-10-04T14:22:00Z')
) as item(title, source_url, participants, summary, published_at)
where events.slug = '2026-bahrain'
on conflict (event_id, team_id, source_url) do update set korean_summary = excluded.korean_summary, review_status = excluded.review_status;
