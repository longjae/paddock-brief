-- Idempotent test collection for the 2026 Bahrain Grand Prix in Malaysia at Sepang.
insert into public.events (
  season, round, slug, official_name, short_name, country, locality,
  circuit_name, track_map_url, date_label, start_at, end_at, timezone
) values (
  2026, 16, '2026-bahrain',
  'FORMULA 1 GULF AIR BAHRAIN GRAND PRIX IN MALAYSIA 2026',
  'Bahrain Grand Prix in Malaysia', 'Malaysia', 'Sepang',
  'Sepang International Circuit',
  'https://media.formula1.com/image/upload/c_fit,h_704/q_auto/v1740000001/common/f1/2026/track/2026trackkualalumpurdetailed.webp',
  '10월 2일 — 10월 4일 · KST', '2026-10-02T04:30:00Z', '2026-10-04T09:00:00Z', 'Asia/Kuala_Lumpur'
)
on conflict (slug) do update set
  official_name = excluded.official_name,
  short_name = excluded.short_name,
  country = excluded.country,
  locality = excluded.locality,
  circuit_name = excluded.circuit_name,
  track_map_url = excluded.track_map_url,
  date_label = excluded.date_label,
  start_at = excluded.start_at,
  end_at = excluded.end_at,
  timezone = excluded.timezone,
  updated_at = now();

insert into public.sessions (event_id, session_type, name, short_name, starts_at, ends_at, status)
select events.id, item.session_type, item.name, item.short_name,
  item.starts_at::timestamptz, item.ends_at::timestamptz, 'done'
from public.events
cross join (values
  ('practice', 'Practice 1', 'FP1', '2026-10-02T04:30:00Z', '2026-10-02T05:30:00Z'),
  ('practice', 'Practice 2', 'FP2', '2026-10-02T08:00:00Z', '2026-10-02T09:00:00Z'),
  ('practice', 'Practice 3', 'FP3', '2026-10-03T04:30:00Z', '2026-10-03T05:30:00Z'),
  ('qualifying', 'Qualifying', 'Q', '2026-10-03T08:00:00Z', '2026-10-03T09:00:00Z'),
  ('race', 'Race', 'R', '2026-10-04T07:00:00Z', '2026-10-04T09:00:00Z')
) as item(session_type, name, short_name, starts_at, ends_at)
where events.slug = '2026-bahrain'
on conflict (event_id, name) do update set
  session_type = excluded.session_type,
  short_name = excluded.short_name,
  starts_at = excluded.starts_at,
  ends_at = excluded.ends_at,
  status = excluded.status;

insert into public.videos (
  event_id, source_id, platform, external_id, category, title, channel_name,
  source_url, duration_label, participants, published_at, is_embeddable, review_status
)
select events.id, sources.id, 'youtube', item.external_id, item.category, item.title,
  'Formula 1', 'https://www.youtube.com/watch?v=' || item.external_id,
  '공식 영상', item.participants, item.published_at::timestamptz, true, 'approved'
from public.events
join public.sources on sources.code = 'formula1-youtube'
cross join (values
  ('SQYus-yb4xE', '예선 후 인터뷰', '드라이버들의 예선 후 반응', array['Max Verstappen','Lewis Hamilton','Isack Hadjar'], '2026-10-03T13:30:35Z'),
  ('XoC8pcPo7A4', '예선 하이라이트', '세팡 그랑프리 예선 하이라이트', array['Formula 1 drivers'], '2026-10-03T09:40:40Z'),
  ('q7iVFMM0XQA', '온보드', '막스 베르스타펜의 폴 포지션 랩', array['Max Verstappen'], '2026-10-03T11:55:07Z'),
  ('U-V7IfBwN1I', '레이스 하이라이트', '비 내린 세팡 그랑프리 레이스 하이라이트', array['Formula 1 drivers'], '2026-10-04T11:40:46Z'),
  ('wqZMYExxLas', '레이스 후 인터뷰', '드라이버들의 레이스 후 반응', array['Formula 1 drivers'], '2026-10-04T15:00:18Z'),
  ('3UZutZLV2vg', '포스트레이스 쇼', '세팡 그랑프리 공식 포스트레이스 쇼', array['Formula 1 presenters'], '2026-10-04T11:30:26Z')
) as item(external_id, category, title, participants, published_at)
where events.slug = '2026-bahrain'
on conflict (platform, external_id) do update set
  event_id = excluded.event_id,
  source_id = excluded.source_id,
  category = excluded.category,
  title = excluded.title,
  source_url = excluded.source_url,
  participants = excluded.participants,
  published_at = excluded.published_at,
  is_embeddable = excluded.is_embeddable,
  review_status = excluded.review_status;

insert into public.interviews (
  event_id, source_id, category, title, source_url, participants,
  korean_summary, published_at, review_status, source_hash
)
select events.id, sources.id, item.category, item.title, item.source_url,
  item.participants, item.korean_summary, item.published_at::timestamptz,
  'published', encode(digest(item.source_url, 'sha256'), 'hex')
from public.events
join public.sources on sources.code = 'fia'
cross join (values
  (
    '레이스 전 기자회견', '목요일 드라이버 기자회견',
    'https://www.fia.com/news/f1-2026-bahrain-grand-prix-malaysia-thursday-press-conference-transcript',
    array['Nico Hulkenberg','Max Verstappen','Oliver Bearman','Arvid Lindblad','Lance Stroll','Pierre Gasly'],
    E'오랜만에 세팡으로 돌아온 드라이버들은 고온, 높은 타이어 열화와 변화하기 쉬운 날씨를 핵심 변수로 꼽았다.\n베르스타펜과 훌켄베르크는 과거 세팡 경험을 떠올렸고, 신인들은 2026년형 차량으로 달릴 고속 코너와 비 가능성에 주목했다.',
    '2026-10-01T00:00:00Z'
  ),
  (
    '팀 대표 기자회견', '금요일 팀 대표 기자회견',
    'https://www.fia.com/news/f1-2026-bahrain-grand-prix-malaysia-friday-press-conference-transcript',
    array['James Vowles','Frederic Vasseur','Flavio Briatore'],
    E'팀 대표들은 짧은 준비 기간에 말레이시아에서 바레인 그랑프리를 운영한 양국 조직위원회의 협업을 높이 평가했다.\n시즌 후반 개발 방향과 각 팀의 경기력, 향후 파워유닛 및 팀 운영 과제도 논의했다.',
    '2026-10-02T00:00:00Z'
  ),
  (
    '예선 후 기자회견', '예선 상위 3인 기자회견',
    'https://www.fia.com/news/f1-2026-bahrain-grand-prix-malaysia-post-qualifying-press-conference-transcript',
    array['Max Verstappen','Lewis Hamilton','Isack Hadjar'],
    E'베르스타펜은 시즌 첫 폴을 차지하며 시즌 초반의 어려움에서 팀이 회복한 결과라고 평가했다.\n해밀턴은 고온과 타이어 과열 속에서 마지막 셋업 변경으로 균형을 찾았다고 설명했고, 하자르는 레드불의 강한 페이스를 확인했다.',
    '2026-10-03T09:30:00Z'
  ),
  (
    '레이스 후 기자회견', '포디엄 드라이버 기자회견',
    'https://www.fia.com/news/f1-2026-bahrain-grand-prix-malaysia-post-race-press-conference-transcript',
    array['Max Verstappen','Kimi Antonelli','Lewis Hamilton'],
    E'베르스타펜은 빗속 인터미디어트 선택과 세이프티카 상황에서의 침착한 판단으로 시즌 첫 승이자 레드불 자체 파워트레인의 첫 승을 거뒀다.\n안토넬리는 현재 패키지로 가능한 최대 결과가 2위였다고 평가했다.\n해밀턴은 초반 슬릭 선택 실패로 1분 가까이 뒤처졌지만 포기하지 않고 3위까지 회복한 팀의 실행력을 강조했다.',
    '2026-10-04T11:00:00Z'
  )
) as item(category, title, source_url, participants, korean_summary, published_at)
where events.slug = '2026-bahrain'
  and not exists (select 1 from public.interviews existing where existing.source_url = item.source_url);

insert into public.interview_segments (
  interview_id, sequence, speaker, original_text, korean_text, review_status
)
select interviews.id, item.sequence, item.speaker, null, item.korean_text, 'reviewed'
from public.interviews
cross join (values
  (1, 'Max Verstappen', '올바른 인터미디어트 선택과 타이어 판단이 복잡한 레이스의 승부를 갈랐고, 팀 자체 파워유닛의 첫 승이라 더욱 특별하다고 말했다.'),
  (2, 'Kimi Antonelli', '메르세데스가 평소보다 고전했지만 2위는 이날 가능한 최대 결과였다고 평가했다.'),
  (3, 'Lewis Hamilton', '초반 타이어 선택이 빗나가 크게 뒤처졌지만 팀이 침착하게 대응해 포디엄까지 회복했다고 설명했다.')
) as item(sequence, speaker, korean_text)
where interviews.source_url = 'https://www.fia.com/news/f1-2026-bahrain-grand-prix-malaysia-post-race-press-conference-transcript'
on conflict (interview_id, sequence) do update set
  speaker = excluded.speaker,
  korean_text = excluded.korean_text,
  review_status = excluded.review_status;

insert into public.tyre_allocations (
  event_id, hard_compound, medium_compound, soft_compound, source_url, announced_at
)
select id, 'C2', 'C3', 'C4',
  'https://press.pirelli.com/tyre-compound-selections-for-baku-sepang-and-singapore/',
  '2026-08-27T09:53:00Z'
from public.events where slug = '2026-bahrain'
on conflict (event_id) do update set
  hard_compound = excluded.hard_compound,
  medium_compound = excluded.medium_compound,
  soft_compound = excluded.soft_compound,
  source_url = excluded.source_url,
  announced_at = excluded.announced_at,
  updated_at = now();

insert into public.race_state_snapshots (session_id, captured_at, lap, state)
select sessions.id, '2026-10-04T10:20:00Z', 55,
  '{"kind":"final-classification","source":"OpenF1 / Formula 1","drivers":[{"position":1,"code":"VER","name":"Max Verstappen","team":"Red Bull Racing","colour":"#4781D7","compound":"SOFT","tyreAge":46,"gap":"WINNER"},{"position":2,"code":"ANT","name":"Kimi Antonelli","team":"Mercedes","colour":"#00D7B6","compound":"SOFT","tyreAge":14,"gap":"+2.307"},{"position":3,"code":"HAM","name":"Lewis Hamilton","team":"Ferrari","colour":"#ED1131","compound":"SOFT","tyreAge":15,"gap":"+4.919"},{"position":4,"code":"LEC","name":"Charles Leclerc","team":"Ferrari","colour":"#ED1131","compound":"SOFT","tyreAge":15,"gap":"+7.258"},{"position":5,"code":"HAD","name":"Isack Hadjar","team":"Red Bull Racing","colour":"#4781D7","compound":"SOFT","tyreAge":14,"gap":"+8.571"}]}'::jsonb
from public.sessions
join public.events on events.id = sessions.event_id
where events.slug = '2026-bahrain' and sessions.name = 'Race'
on conflict (session_id, captured_at) do update set
  lap = excluded.lap,
  state = excluded.state;
