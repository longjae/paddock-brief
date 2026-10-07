-- Official Formula 1 driver interviews and press-conference archive for Sepang 2026.
-- Safe to re-run: rows are keyed by (event_id, source_url).

with context as (
  select
    (select id from public.events where slug = '2026-bahrain') as event_id,
    (select id from public.sources where code = 'formula1-editorial') as source_id
), rows (
  category, title, source_url, korean_summary, korean_detail, author, tags,
  team_codes, driver_codes, published_at, is_paywalled, review_status
) as (
  values
  (
    'interview',
    '세팡을 앞둔 드라이버들의 목요일 전망',
    'https://www.formula1.com/en/latest/article/its-going-to-be-completely-different-drivers-reflect-on-the-key-challenge-they-expect-in-sepang.7g0Dq4ropQsKfaVoaYjHDj.7g0Dq4ropQsKfaVoaYjHDj',
    '랜도 노리스와 카를로스 사인츠가 거친 노면, 높은 타이어 열화, 비 가능성이 결합된 세팡의 핵심 변수를 레이스 위크 목요일 인터뷰에서 설명한다.',
    E'목요일 미디어데이 배경\nF1이 2017년 이후 처음 세팡으로 돌아오면서 드라이버들은 축적된 최신 차량 데이터가 거의 없는 상태에서 주말을 시작했다. 특히 새 규정 차량으로 젖은 세팡을 달려 본 경험이 없어 금요일 연습주행의 중요성이 커졌다.\n\n드라이버들이 꼽은 핵심 과제\n랜도 노리스와 카를로스 사인츠는 노면이 타이어에 매우 거칠고 기온까지 높아 열화 관리가 성능을 좌우할 것으로 봤다. 여기에 소나기 가능성이 더해져 셋업을 마른 노면 한쪽에만 맞추기 어렵고, 세션마다 그립 변화에 빠르게 대응해야 한다고 설명했다.\n\n주말을 읽는 포인트\n단일 랩 순위보다 롱런에서 타이어가 얼마나 오래 버티는지, 비가 왔을 때 새 차량이 어떤 균형을 보이는지가 더 중요한 자료다. 목요일 전망은 이후 실제 레이스에서 타이어 선택과 변화무쌍한 노면이 결정적 변수가 된 이유를 이해하는 출발점이다.',
    'Formula 1',
    array['목요일 인터뷰', '드라이버', '타이어', '날씨'],
    array['mclaren', 'williams'],
    array['NOR', 'SAI'],
    '2026-10-01T15:21:00Z'::timestamptz,
    false,
    'approved'
  ),
  (
    'interview',
    '베르스타펜: 금요일에는 소프트보다 롱런이 중요했다',
    'https://www.formula1.com/en/latest/article/verstappen-assesses-positive-start-in-malaysia-as-he-explains-why-he-didnt-run-soft-tyre-in-fp2.6FNsYUfLmu6eTjCszeCMU5',
    '막스 베르스타펜은 FP1 1위 뒤에도 고온과 열화를 경계했고, 비 예보 속에서 소프트 랩 대신 미디엄 롱런 데이터를 우선한 이유를 밝혔다.',
    E'금요일 출발점\n베르스타펜은 FP1에서 가장 빨랐고 FP2에서도 미디엄 타이어로 경쟁력 있는 페이스를 보였다. 다만 세팡의 높은 노면 온도와 큰 열화 때문에 첫날 결과만으로 우위를 단정하기는 어렵다고 평가했다.\n\n소프트 타이어를 쓰지 않은 이유\nFP2에서 소프트 타이어 기록을 시도하지 않은 것은 비가 오기 전에 롱런을 마치고 미디엄 타이어 데이터를 확보하기 위한 선택이었다. 레드불은 차량의 작은 문제와 날씨 변화를 고려해 예선용 한 랩보다 레이스 열화 자료를 더 가치 있게 봤다.\n\n업그레이드와 남은 과제\n기술진은 바쿠에서 투입한 패키지가 세팡의 다른 코너 유형에서도 이전 사양보다 나아 보인다고 설명했다. 긍정적인 첫날이었지만 상대 페이스와 우천 거동은 아직 불확실해, 수집한 롱런 데이터를 토대로 셋업을 정교하게 다듬어야 한다.',
    'Formula 1',
    array['선수 인터뷰', '연습주행', '롱런', '타이어'],
    array['red-bull'],
    array['VER'],
    '2026-10-02T11:33:00Z'::timestamptz,
    false,
    'approved'
  ),
  (
    'interview',
    '르클레르: 세팡의 핵심은 극심한 타이어 열화',
    'https://www.formula1.com/en/latest/article/leclerc-highlights-main-talking-point-in-sepang-as-he-evaluates-ferraris-performance.2G9wLgsgXcns7GrEAlbUVQ.2G9wLgsgXcns7GrEAlbUVQ',
    '샤를 르클레르는 FP2 1위에도 레드불과 메르세데스를 경계하며, 세팡 주말의 가장 큰 화두는 극심한 타이어 열화라고 평가했다.',
    E'FP2 선두의 의미\n르클레르는 미끄럽고 더러운 노면에서도 FP2 선두를 기록했지만 페라리가 가장 빠르다고 보지는 않았다. 베르스타펜이 소프트 타이어 랩을 하지 않았고 하자르도 마지막 구간에서 실수가 있었기 때문에 기록표에 숨은 여지가 있다고 판단했다.\n\n경쟁 구도와 노면 변화\n레드불의 페이스가 특히 돋보였고, 메르세데스도 소프트 랩을 제대로 완성하면 다시 강해질 것이라고 내다봤다. 토요일까지 노면 그립이 크게 향상될 수 있어 금요일 균형을 그대로 유지하는 것보다 변화 방향을 예측하는 일이 중요하다고 말했다.\n\n레이스의 핵심 과제\n르클레르는 타이어 열화를 주말의 가장 큰 화두로 꼽았다. 작은 코너링 차이도 장거리 열화에 큰 영향을 줄 수 있으므로 페라리는 좋은 출발에 만족하지 않고 레이스 셋업과 타이어 관리 방식을 더 다듬어야 한다.',
    'Formula 1',
    array['선수 인터뷰', '연습주행', '타이어 열화'],
    array['ferrari'],
    array['LEC'],
    '2026-10-02T11:45:00Z'::timestamptz,
    false,
    'approved'
  ),
  (
    'interview',
    '베르스타펜: 시즌 첫 폴, 이제 목표는 우승',
    'https://www.formula1.com/en/latest/article/verstappen-reacts-to-incredible-first-pole-of-season-as-he-sets-out-target-for-bahrain-gp-in-malaysia.1uIwUE6iPuGfTS6XEwxGbW',
    '막스 베르스타펜은 1분 35초130으로 2026시즌 첫 폴을 차지한 뒤, 시즌 초 부진에서 회복한 팀의 진전을 강조하며 결승 우승을 목표로 제시했다.',
    E'예선 결과\n베르스타펜은 Q1과 Q2에 이어 Q3에서도 가장 빠른 1분 35초130을 기록해 해밀턴을 약 0.3초 차로 제쳤다. 이는 레드불과 본인에게 2026시즌 첫 폴 포지션이었다.\n\n회복 과정에 대한 평가\n시즌 초 선두권보다 뒤처졌던 상황에서 여러 그랑프리를 거쳐 차를 이해하고 개선한 끝에 얻은 결과라는 점을 가장 크게 평가했다. 직전 아제르바이잔에서도 우승에 근접했던 흐름이 세팡 예선 경쟁력으로 이어졌다.\n\n결승 목표\n폴에서 출발하는 만큼 목표를 우승으로 분명히 정했다. 다만 세팡의 높은 타이어 열화와 변덕스러운 날씨 때문에 한 랩 우위를 레이스 전체 우위로 바꾸려면 스타트, 타이어 관리, 전략 실행이 모두 필요하다.',
    'Formula 1',
    array['선수 인터뷰', '예선', '폴 포지션'],
    array['red-bull'],
    array['VER'],
    '2026-10-03T10:13:00Z'::timestamptz,
    false,
    'approved'
  ),
  (
    'interview',
    '해밀턴: 마지막 셋업 변경으로 스위트 스폿을 찾았다',
    'https://www.formula1.com/en/latest/article/hamilton-explains-how-ferrari-hit-the-sweet-spot-in-qualifying-for-bahrain-gp-in-malaysia.012Xq9ylnwbXl6HOmHai9v.012Xq9ylnwbXl6HOmHai9v',
    '루이스 해밀턴은 마지막 셋업 변경으로 과열과 슬라이딩을 줄여 예선 2위를 차지했지만, 결승에서는 타이어 열화가 완전히 다른 승부를 만들 것이라고 경계했다.',
    E'예선 전 문제\n세팡의 고온에서 차가 미끄러지고 타이어가 과열되면서 페라리는 연습주행 내내 균형을 찾기 어려웠다. 해밀턴은 르클레르보다 뒤에 있던 흐름 때문에 Q3 2위가 예상보다 더 좋은 결과였다고 돌아봤다.\n\n결정적인 변경\n예선을 앞둔 마지막 셋업 변경이 차의 균형을 맞추며 스위트 스폿을 찾게 했고, 해밀턴은 베르스타펜과의 차이를 0.2~0.3초까지 좁혔다. 세팡 경험과 팀의 반복적인 조정이 프런트로우 확보에 함께 작용했다.\n\n결승 전망\n예선용 균형이 좋아졌어도 결승은 타이어를 오래 살려야 하는 다른 과제라고 강조했다. 작은 휠스핀이나 순간적인 오버스티어도 스틴트 길이에 영향을 주기 때문에, 레드불의 강한 롱런을 상대로 안정적인 페이스 유지가 핵심이다.',
    'Formula 1',
    array['선수 인터뷰', '예선', '셋업', '타이어'],
    array['ferrari'],
    array['HAM'],
    '2026-10-03T10:24:00Z'::timestamptz,
    false,
    'approved'
  ),
  (
    'interview',
    '해밀턴: 1분 뒤처진 뒤 되찾은 포디엄은 씁쓸하고도 값졌다',
    'https://www.formula1.com/en/latest/article/hamilton-hails-bittersweet-podium-in-sepang-after-comeback-drive.kacizmhSQaUfUkYHV5H47',
    '루이스 해밀턴은 젖은 출발에서 소프트 타이어를 택해 17위까지 밀렸지만, 트랙에 남는 승부수와 추격으로 3위를 되찾은 경기를 씁쓸한 포디엄이라고 평가했다.',
    E'출발에서 잃은 기회\n혼합 노면에서 인터미디어트 대신 소프트 타이어로 출발한 선택은 트랙이 예상만큼 빨리 마르지 않으면서 큰 손실이 됐다. 2번 그리드에서 17위, 선두와 약 1분 차까지 떨어져 우승 경쟁 기회를 사실상 잃었다.\n\n추격을 만든 판단과 실행\n팀이 교체를 제안했을 때 해밀턴은 소프트로 더 버티는 도박을 선택했고, 이후 여러 차례 타이어 교체와 빠른 피트스톱을 발판으로 순위를 되찾았다. 어려운 노면에서 실수를 억제하며 끝내 베르스타펜과 안토넬리 뒤 3위로 결승선을 통과했다.\n\n경기 후 평가\n포디엄 자체는 예상하기 어려웠던 회복의 결과라 만족했지만, 초반 판단 때문에 더 큰 결과를 놓쳤다는 점에서 씁쓸하다고 말했다. 페라리에서 보낸 주말 중 차의 감각은 가장 좋았던 편이므로, 팀은 출발 전략을 복기해 이 성능을 다음 경기로 이어갈 계획이다.',
    'Formula 1',
    array['선수 인터뷰', '결승', '포디엄', '전략'],
    array['ferrari'],
    array['HAM'],
    '2026-10-04T12:50:00Z'::timestamptz,
    false,
    'approved'
  ),
  (
    'interview',
    '안토넬리: 세팡 2위가 우리가 얻을 수 있었던 최대치',
    'https://www.formula1.com/en/latest/article/p2-was-the-maximum-we-could-have-achieved-in-malaysia-antonelli.2pwbKbJ3dldp6qKJS7Hwad',
    '키미 안토넬리는 올바른 인터미디어트 선택으로 한때 선두에 올랐지만, 베르스타펜의 페이스를 인정하며 2위가 메르세데스의 최대 결과였다고 평가했다.',
    E'좋았던 출발\n안토넬리는 3번 그리드에서 인터미디어트를 선택해 턴 1에서 베르스타펜을 앞지르고 선두에 올랐다. 혼합 노면에 맞는 타이어 선택과 과감한 스타트가 초반 우승 가능성을 만들었다.\n\n레이스의 전환점\n첫 세이프티카 이후 베르스타펜에게 자리를 내줬고 한때 러셀에게도 추월당했지만, 다시 2위를 회복한 뒤 끝까지 지켰다. 레드불의 전체 페이스가 더 강했기 때문에 현재 조건에서 2위가 얻을 수 있었던 최대치라고 판단했다.\n\n팀에 남은 숙제\n챔피언십 선두를 크게 넓힌 결과에도 메르세데스가 평소보다 고전했고 신뢰성 문제로 러셀까지 리타이어한 점을 강조했다. 개인 결과에 안주하기보다 반복되는 파워 유닛 문제의 원인을 해결해야 시즌 경쟁을 안정적으로 이어갈 수 있다는 평가다.',
    'Formula 1',
    array['선수 인터뷰', '결승', '포디엄', '챔피언십'],
    array['mercedes'],
    array['ANT'],
    '2026-10-04T13:55:00Z'::timestamptz,
    false,
    'approved'
  ),
  (
    'interview',
    '하자르: 배터리 문제로 놓친 세팡 포디엄',
    'https://www.formula1.com/en/latest/article/how-a-battery-issue-robbed-frustrated-hadjar-of-a-podium-in-sepang.lpydtOJ2CszTQCvhK4pDo',
    '아이작 하자르는 8위 출발에서 포디엄권까지 올라왔지만 재시작 직후 배터리 부족으로 페라리 두 대를 막지 못해 5위에 그친 과정과 좌절감을 설명했다.',
    E'포디엄 경쟁까지의 과정\n엔진 교체 페널티로 8번 그리드에서 출발했지만 인터미디어트를 고른 덕분에 초반 순위를 빠르게 올렸다. 러셀의 리타이어 뒤에는 3위까지 올라 포디엄을 현실적인 목표로 삼을 수 있었다.\n\n두 가지 성능 문제\n레이스 중반부터 평소보다 한 랩에 약 1초 느릴 정도로 그립이 부족했고 차를 다루기 어렵다고 느꼈다. 마지막 세이프티카 재시작 직후에는 배터리 에너지가 부족해 직선에서 해밀턴과 르클레르를 방어하지 못했고, 문제가 안정됐을 때는 이미 5위로 밀린 뒤였다.\n\n선수의 결론\n하자르는 파워 유닛 자체보다 일시적인 배터리 운용과 섀시 그립 문제가 포디엄을 앗아갔다고 봤다. 팀 동료와 레드불의 시즌 첫 승은 축하했지만 자신의 결과는 재앙에 가깝다며 싱가포르 전까지 원인을 고쳐야 한다고 강조했다.',
    'Formula 1',
    array['선수 인터뷰', '결승', '배터리', '포디엄'],
    array['red-bull'],
    array['HAD'],
    '2026-10-04T14:36:00Z'::timestamptz,
    false,
    'approved'
  ),
  (
    'interview',
    '피아스트리: 개인적으로는 회복했지만 맥라렌은 충분히 빠르지 않았다',
    'https://www.formula1.com/en/latest/article/we-just-werent-quick-enough-piastri-admits-mclaren-need-to-improve-after-malaysia-p6.6xn5ElSyF1kysf39dqwDGt',
    '오스카 피아스트리는 젖은 출발에서 미디엄 타이어를 택한 뒤 1랩에 인터미디어트로 바꿔 6위까지 회복했지만, 맥라렌의 기본 페이스가 부족했다고 진단했다.',
    E'초반 전략 손실\n피아스트리는 젖은 노면에서 미디엄 타이어로 출발했지만 조건이 맞지 않아 첫 랩에 인터미디어트로 전환해야 했다. 이 선택으로 초반 트랙 포지션을 잃어 뒤쪽에서 긴 추격전을 시작했다.\n\n6위까지의 회복\n혼란스러운 레이스에서 실수를 줄이고 전략 기회를 활용해 6위까지 올라왔다. 개인적으로는 주어진 상황에서 합리적인 회복이었다고 봤지만, 선두권을 위협할 속도는 처음부터 부족했다고 인정했다.\n\n맥라렌의 과제\n주말 전체를 보면 레드불이 가장 강했고 맥라렌은 한 랩과 롱런 모두 개선이 필요하다는 결론이다. 결과만으로 만족하기보다 타이어 운용과 차의 순수 페이스가 왜 경쟁 팀보다 떨어졌는지 분석하는 것이 다음 경기의 핵심이다.',
    'Formula 1',
    array['선수 인터뷰', '결승', '전략', '페이스'],
    array['mclaren'],
    array['PIA'],
    '2026-10-04T15:05:00Z'::timestamptz,
    false,
    'approved'
  ),
  (
    'interview',
    'Formula 1 공식 기자회견 아카이브',
    'https://www.formula1.com/en/latest/tags/press-conferences.55FMj3vhksoIIIQmuKwSuq',
    '목요일 드라이버 회견부터 팀 대표, 예선, 스프린트, 결승 후 기자회견까지 Formula 1이 공개하는 공식 회견문을 모아 보는 상시 업데이트 아카이브다.',
    E'무엇을 볼 수 있나\nFormula 1 공식 사이트가 공개한 기자회견 기사들을 한곳에 모은 태그 페이지다. 그랑프리 목요일 드라이버 기자회견, 팀 대표 회견, 예선과 스프린트 및 결승 뒤 공식 기자회견이 게시될 때 이 페이지에 순차적으로 추가된다.\n\n세팡 자료 상태\n현재 아카이브 목록에는 세팡 2026 회견문이 별도 항목으로 노출되지 않아, 이 카드는 특정 세팡 회견문의 번역본이 아니라 공식 원문 아카이브로 연결하는 안내 카드다. 세팡 선수 발언은 같은 화면의 개별 Formula 1 인터뷰 카드에서 한국어 상세 요약으로 확인할 수 있다.\n\n앞으로의 활용\n새 회견문이 게시되면 참가 선수와 팀을 확인해 해당 그랑프리 및 선수 탭에 개별 카드로 연결한다. 원문 전체를 복제하지 않고 핵심 맥락과 답변을 한국어로 구조화해 요약하며, 원문 보기 버튼은 항상 이 공식 출처 또는 개별 회견문으로 연결한다.',
    'Formula 1',
    array['공식 기자회견', '아카이브', '원문'],
    array[]::text[],
    array[]::text[],
    '2026-10-05T06:00:00Z'::timestamptz,
    false,
    'approved'
  )
)
insert into public.event_news (
  event_id, source_id, category, title, source_url, korean_summary,
  korean_detail, author, tags, team_codes, driver_codes, published_at,
  is_paywalled, review_status
)
select
  context.event_id, context.source_id, rows.category, rows.title,
  rows.source_url, rows.korean_summary, rows.korean_detail, rows.author,
  rows.tags, rows.team_codes, rows.driver_codes, rows.published_at,
  rows.is_paywalled, rows.review_status
from context cross join rows
where context.event_id is not null and context.source_id is not null
on conflict (event_id, source_url) do update set
  source_id = excluded.source_id,
  category = excluded.category,
  title = excluded.title,
  korean_summary = excluded.korean_summary,
  korean_detail = excluded.korean_detail,
  author = excluded.author,
  tags = excluded.tags,
  team_codes = excluded.team_codes,
  driver_codes = excluded.driver_codes,
  published_at = excluded.published_at,
  is_paywalled = excluded.is_paywalled,
  review_status = excluded.review_status,
  collected_at = now();
