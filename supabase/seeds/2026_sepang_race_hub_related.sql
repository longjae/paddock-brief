-- Formula 1 race-hub related articles for the 2026 Sepang weekend.
-- Safe to re-run through the existing unique source URL constraints.

insert into public.team_content (
  event_id, team_id, source_id, platform, content_kind, title, source_url,
  participants, korean_summary, korean_detail, published_at, is_embeddable,
  review_status
)
select events.id, teams.id, sources.id, 'web', 'team-report', item.title,
  item.source_url, item.participants, item.summary, item.detail,
  item.published_at::timestamptz, true, 'approved'
from public.events
join public.sources on sources.code = 'formula1-editorial'
cross join (values
  (
    'ferrari',
    '바서가 설명한 페라리의 세팡 손실 최소화',
    'https://www.formula1.com/en/latest/article/vasseur-explains-how-hamilton-and-leclerc-saved-ferraris-day-at-sepang.12TUUZbQJnGxaCmruB9vMR',
    array['Fred Vasseur','Lewis Hamilton','Charles Leclerc'],
    '프레데릭 바서는 잘못된 슬릭 출발을 인정하면서도 해밀턴과 르클레르의 추격, 타이어 관리와 레이스 페이스가 3·4위로 손실을 줄였다고 평가했다.',
    E'초반 판단\n페라리는 트랙이 빠르게 마를 것으로 예상해 두 차 모두 슬릭으로 출발했지만 실제 건조 속도는 훨씬 느렸다. 바서는 당시 정보에 근거한 결정이었다면서도 인터미디어트가 더 나은 선택이었다는 점을 분명히 인정했다.\n\n드라이버들의 회복\n르클레르는 첫 랩 접촉 뒤 즉시 프런트윙과 타이어를 교체했고, 해밀턴은 차 안에서 소프트 타이어를 더 오래 쓰는 승부수를 선택했다. 두 드라이버는 강한 레이스 페이스와 타이어 관리로 필드를 통과해 3위와 4위까지 회복했다.\n\n팀의 결론\n세이프티카 뒤 서로 다른 컴파운드가 뒤섞인 상황에서도 페라리의 순수 페이스는 경쟁력이 있었다. 팀은 출발 전략을 복기하되 세팡에서 확인한 장거리 성능을 싱가포르로 이어가는 데 집중한다.',
    '2026-10-05T12:24:00Z'
  ),
  (
    'red-bull',
    '메키스: 레드불 포드 파워트레인의 첫 승이 만든 이정표',
    'https://www.formula1.com/en/latest/article/mekies-explains-why-verstappens-milestone-bahrain-gp-victory-meant-so-much-to-red-bull.5Gl4kO0FOg77Dcr18hkabd',
    array['Laurent Mekies','Max Verstappen','Isack Hadjar'],
    '로랑 메키스는 베르스타펜의 세팡 우승이 레드불 포드 파워트레인의 첫 승이자 팀 전체 개발 프로젝트의 중요한 이정표라고 설명했다.',
    E'승리의 의미\n세팡 우승은 2026시즌 레드불의 첫 승이면서 자체 파워트레인 프로젝트가 기록한 첫 승이었다. 메키스는 차량과 엔진 조직이 함께 만든 결과라는 점에서 일반적인 한 경기 우승보다 상징성이 크다고 평가했다.\n\n주말의 실행\n베르스타펜은 예선 폴 이후 변화하는 노면과 세이프티카 재시작을 침착하게 처리했다. 팀은 타이어 선택과 에너지 운용을 맞추며 시즌 초 약점이었던 전체 패키지의 균형이 개선됐음을 확인했다.\n\n앞으로의 기준\n한 번의 성공이 모든 문제가 해결됐다는 의미는 아니지만 개발 방향을 검증하는 중요한 자료가 됐다. 레드불은 세팡의 성과를 기준점으로 삼아 남은 경기에서 경쟁력을 반복하는 것을 다음 목표로 잡았다.',
    '2026-10-05T09:40:00Z'
  )
) as item(team_code, title, source_url, participants, summary, detail, published_at)
join public.teams on teams.code = item.team_code
where events.slug = '2026-bahrain'
on conflict (event_id, team_id, source_url) do update set
  title = excluded.title,
  participants = excluded.participants,
  korean_summary = excluded.korean_summary,
  korean_detail = excluded.korean_detail,
  published_at = excluded.published_at,
  review_status = excluded.review_status;

with context as (
  select
    (select id from public.events where slug = '2026-bahrain') as event_id,
    (select id from public.sources where code = 'formula1-editorial') as source_id
), rows (
  title, source_url, korean_summary, korean_detail, tags, team_codes,
  driver_codes, published_at
) as (
  values
  (
    '린드블라드: 최후미 출발에서 얻은 기대 이상의 10위',
    'https://www.formula1.com/en/latest/article/more-than-we-could-have-ever-imagined-lindblad-reflects-on-p10-finish-from-back-of-the-grid-in-malaysia.5UjynLy03wJSix8bDHhZhd',
    '아비드 린드블라드는 엔진 페널티로 22위에서 출발했지만 인터미디어트 선택과 팀의 전략으로 10위까지 올라 4경기 연속 포인트를 기록했다.',
    E'최후미 출발\n새 엔진 부품 페널티로 22번 그리드에서 시작했지만 젖은 노면에 맞춰 인터미디어트를 선택해 슬릭 출발 차량들을 초반에 앞질렀다. 출발 판단이 긴 추격전의 기반이 됐다.\n\n포인트까지의 과정\n러셀의 리타이어와 노리스의 세이프티카 상황 이탈도 순위 상승에 영향을 줬고, 린드블라드는 최종 10위로 네 경기 연속 포인트를 완성했다. 팀 동료 로슨도 7위에 올라 레이싱 불스는 알핀과의 컨스트럭터 경쟁에서 격차를 벌렸다.\n\n개인 평가\n결과는 기대 이상이었지만 린드블라드는 중반 롱런 속도가 부족했던 자신의 주행에는 만족하지 않았다. 예선보다 레이스에서 약해지는 원인을 찾아야 한다며 성과와 개선점을 분리해 평가했다.',
    array['선수 인터뷰','결승','포인트'],
    array['racing-bulls'],
    array['LIN'],
    '2026-10-05T10:04:00Z'::timestamptz
  ),
  (
    '알론소: 세팡에서 붙잡은 애스턴 마틴의 기회',
    'https://www.formula1.com/en/latest/article/we-have-some-hope-how-alonso-and-aston-martin-took-their-opportunity-in-sepang.VfUQ0Vt8HaJIi0flQEaxH',
    '페르난도 알론소는 잘못된 미디엄 출발에도 세이프티카 기회를 활용해 8위를 차지했고, 애스턴 마틴이 경쟁력 있는 주말에는 실행으로 포인트를 잡아야 한다고 말했다.',
    E'출발 전 전망과 변수\n알론소는 직선 속도와 기본 페이스 때문에 12번 그리드에서 포인트가 어렵다고 예상했다. 비가 내리면서 새로운 기회가 생겼지만 애스턴 마틴도 미디엄 슬릭으로 출발해 초반에는 잘못된 선택의 대가를 치렀다.\n\n세이프티카 이후의 회복\n알론소는 바로 타이어를 바꾸는 대신 세이프티카를 기다렸고 실제 중립화가 나오면서 필드와 다시 가까워졌다. 재출발 뒤 꾸준히 순위를 올렸고 러셀의 리타이어와 노리스의 실수까지 더해져 8위를 지켰다.\n\n팀에 남긴 의미\n애스턴 마틴이 정기적으로 포인트를 얻을 속도는 아니지만 세팡에서는 두 차 모두 Q2에 진출할 만큼 상대적으로 경쟁력이 있었다. 알론소와 팀은 이런 드문 기회가 왔을 때 실행으로 결과를 만들어야 하며, 싱가포르에서도 비슷한 특성의 이점을 기대한다고 정리했다.',
    array['선수 인터뷰','결승','전략'],
    array['aston-martin'],
    array['ALO'],
    '2026-10-05T09:43:00Z'::timestamptz
  )
)
insert into public.event_news (
  event_id, source_id, category, title, source_url, korean_summary,
  korean_detail, author, tags, team_codes, driver_codes, published_at,
  is_paywalled, review_status
)
select context.event_id, context.source_id, 'interview', rows.title,
  rows.source_url, rows.korean_summary, rows.korean_detail, 'Formula 1',
  rows.tags, rows.team_codes, rows.driver_codes, rows.published_at, false,
  'approved'
from context cross join rows
where context.event_id is not null and context.source_id is not null
on conflict (event_id, source_url) do update set
  title = excluded.title,
  korean_summary = excluded.korean_summary,
  korean_detail = excluded.korean_detail,
  tags = excluded.tags,
  team_codes = excluded.team_codes,
  driver_codes = excluded.driver_codes,
  published_at = excluded.published_at,
  review_status = excluded.review_status,
  collected_at = now();
