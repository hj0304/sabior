# KBO 데이터 소스 점검 (W1-W2, 2026-09-07 ~ 09-13)

결론: 공식 사이트와 STATIZ 는 자동 수집이 금지되어 있다. 대신 두 가지 현실적인 경로가 확인되었다. 하나는 **야구나라의 연구자 대상 데이터 요청 창구**(정식 경로), 다른 하나는 **네이버 스포츠 API**(kbo-cli 가 쓰는 방식, 약관상 회색지대). 최종 선택은 ADR 0008.

## 1. 소스별 점검 결과

| 소스 | 자동 수집 | 근거 | 데이터 범위 | 비고 |
|---|---|---|---|---|
| KBO 공식 기록실 (koreabaseball.com) | 금지 | robots.txt `User-agent: * Disallow: /`. 주석: "본 사이트의 데이터를 사전 승인 없이 자동 수집·크롤링·복제하는 행위를 금지합니다" | 1982~ 전체, SF/SH/IBB 포함 | "사전 승인" 경로 존재. 메일 요청 초안: docs/data_request_drafts.md |
| STATIZ (statiz.co.kr) | 금지 | robots `User-agent: *` 에 `Disallow: /`, Cloudflare Content-Signal `ai-train=no`. AI 크롤러 UA 전부 차단 | 1982~, 세이버 지표 | 수동 열람으로 대조·검증에만 사용. 학습 데이터 사용 불가 |
| 네이버 스포츠 API (api-gw.sports.naver.com) | 회색 | robots.txt 없음(404). 네이버 이용약관은 "이용자(사람)의 실제 이용을 전제로 하는 서비스 제공 취지에 부합하지 않는 방식"의 자동화 이용을 금지 (아래 인용) | **2010~2026** 시즌별 타자·투수 기록, 팀 순위, 경기 일정·중계 | kbo-cli(MIT, npm 공개)가 사용. 네이버는 KBO 데이터의 라이선시이므로 공개 서비스 재배포는 불가 |
| 야구나라 (yagoonara.com) | 자동 수집 부적절(상용 사이트) | robots 는 AI 학습 봇만 차단. 데이터 출처를 koreabaseball.com 으로 명시 | 1982~ 전 시즌, 세이버 지표, 상황별 기록 | **"개인 데이터 요청: 기자·세이버메트리션을 위한 맞춤 KBO 데이터"** 창구 운영. 협업·제휴 문의 창구도 있음 |
| MyKBO Stats (mykbostats.com) | 금지 | 이용약관에 크롤러·플러그인 등 자동 접근 금지 명시 | 영문 KBO 기록 | 제외 |
| kbodata, kbodatatools (PyPI) | 사실상 금지 | KBO 공식 사이트 경기 리뷰 페이지를 스크래핑 | 경기 단위 | 공식 사이트 robots 위반이 되므로 사용하지 않음 |
| Baseball-Reference KBO register | 금지 | 이용약관상 자동 수집 금지 | 팀-시즌 단위 전 선수 | 수동 저장은 가능하나 후순위 |
| DACON, Kaggle 데이터셋 | - | 대회용 라이선스, 2018년 이전 | 제한적 | 참고용 |
| Sportradar Global Baseball, API4Sports, Entity Sports | 라이선스 | 상용 데이터 피드. KBO 포함 | 실시간·경기 단위 중심. 선수 시즌 기록 제공 여부는 요금제별 확인 필요 | 공개 웹서비스 단계의 후보. Sportradar 는 B2B (월 $500~1,000+ 추정), API4Sports 는 무료 티어 존재 |
| 공공데이터포털 | - | KBO 선수 기록 데이터셋 없음 | - | 제외 |

### 네이버 이용약관 인용 (2026-09-13 확인)

> 네이버의 사전 허락 없이 자동화된 수단(예: 매크로 프로그램, 로봇(봇), 스파이더, 스크래퍼 등)을 이용하여 (...) 네이버 서비스에 게재된 회원의 아이디(ID), 게시물 등을 수집하거나, (...) 이용자(사람)의 실제 이용을 전제로 하는 네이버 서비스의 제공 취지에 부합하지 않는 방식으로 네이버 서비스를 이용하거나 (...) 일체의 행위를 시도해서는 안 됩니다.

명시적으로 "기록 데이터 수집"을 금지한 문장은 없지만, 마지막 포괄 조항이 자동화 이용 일반을 막는다. 개인 연구용 저속·1회 백필은 실질적 피해가 없지만 약관 준수 관점에서는 회색지대다.

## 2. 네이버 스포츠 API 구조 (kbo-cli 분석 + 검증 호출 12건)

- 기본 URL: `https://api-gw.sports.naver.com`
- 시즌 선수 기록: `/statistics/categories/kbo/seasons/{year}/players?playerType=HITTER|PITCHER&field=hra|era&direction=DESC|ASC&pageSize=100&page=1[&teamCode=LG]`
  - `pageSize` 최대 100 (1000 은 400). `page` 파라미터는 동작이 불확실 (page=3 이 page=1 과 동일 응답). `teamCode` 필터로 팀별 호출하면 전 선수 확보 가능
  - 응답: `result.seasonPlayerStats[]`, `result.gameType = REGULAR_SEASON`
- 팀 순위: `/statistics/categories/kbo/seasons/{year}/teams` → 승·패·무, 팀 공격·수비 집계 (득점 `offenseRun`, 실점 `defenseR`)
- 리더보드: `/statistics/categories/kbo/seasons/{year}/top-players?playerType=HITTER&limit=30`
- 일정·중계: `/schedule/games?upperCategoryId=kbaseball&fromDate=&toDate=`, `/schedule/games/{gameId}`, `/schedule/games/{gameId}/relay`
- 시즌 커버리지: 2010 ✓, 2015 ✓, 2025 ✓. 2005 는 200 이지만 0행, 2001·1982 는 400 → **2010 시즌부터**로 추정 (2006~2009 는 미확인)

### 필드 매핑 (스키마 대비)

| 스키마 | 네이버 타자 필드 | 비고 |
|---|---|---|
| g, ab, r, h, doubles, triples, hr, rbi, sb, cs, bb, hbp, so, gidp | hitterGameCount, hitterAb, hitterRun, hitterHit, hitterH2, hitterH3, hitterHr, hitterRbi, hitterSb, hitterCs, hitterBb, hitterHp, hitterKk, hitterGd | 2015 시즌은 cs, gd 가 NULL |
| pa, sf, sh, ibb | **없음** | SF 는 OBP 역산으로 근사 가능: (H+BB+HBP)/OBP − AB − BB − HBP. SH, IBB 는 복구 불가 |
| (검증용) | hitterObp, hitterSlg, hitterOps, hitterIsop, hitterBabip, hitterWoba, hitterWrcPlus, hitterWpa, hitterWar | 2015 는 wrcPlus, war 가 0.0 → 과거 시즌 미계산. 자체 계산 대조에만 사용 |

| 스키마 | 네이버 투수 필드 | 비고 |
|---|---|---|
| g, gs, w, l, sv, hld, ip_outs, h, r, er, hr, bb, hbp, so | pitcherGameCount, pitcherStart, pitcherWin, pitcherLose, pitcherSave, pitcherHold, pitcherInning(문자열 → outs 변환), pitcherHit, pitcherR, pitcherEr, pitcherHr, pitcherBb, pitcherHp, pitcherKk | |
| bf | **없음** | pitcherPaKkRate = K/BF 로 역산 가능 (반올림 오차) |
| (검증용) | pitcherEra, pitcherWhip, pitcherQs, pitcherWpa, pitcherWar, pitcherPitchCount | |

### 백필 비용 추정
2010~2026 = 17 시즌 × 10 팀 × 2 (타자·투수) ≈ 340 요청 + 팀 순위 17 요청. 2초 간격이면 약 12분. 1회 실행 후 캐시. 시즌 중 갱신은 주 1회 당해 시즌만.

## 3. 야구나라 데이터 요청 창구

- URL: https://www.yagoonara.com/inquiry/data-request
- 안내문: "기사 작성, 세이버메트릭스 분석, 리서치 등에 필요한 KBO 데이터가 있다면 자유롭게 요청해주세요. 사이트에 없는 맞춤 집계·상황별 기록·기간별 추출도 가능한 범위에서 제공해드립니다."
- 운영: 사업자 등록된 개인사업자(클라우디아). 협업·제휴 문의 창구 별도 (https://www.yagoonara.com/inquiry/partnership)
- 요청 초안: docs/data_request_drafts.md. 받은 데이터의 이용 범위(재배포·학습)는 회신 시 확인한다. 이용약관 https://www.yagoonara.com/terms 도 읽을 것

## 4. 선택지와 권고 (ADR 0008 로 결정)

| 선택지 | 장점 | 단점 | 권고 |
|---|---|---|---|
| A. 야구나라 데이터 요청 + KBO 승인 요청 (정식) | 약관 문제 없음. SF/SH/IBB 포함 완전한 기록 가능. 웹서비스 제휴로 이어질 수 있음 | 회신 기간 불확실 (수일~수주). 거절 가능 | **1순위. 오늘 요청 발송** |
| B. 네이버 API 저속 1회 백필 (연구용) | 즉시 가능. 2010~2026, 340 요청 | 약관 회색지대. SF/SH/IBB 없음. 공개 서비스에 재사용 불가 | A 회신 대기 중 임시 데이터로만. 사용자 판단 |
| C. MLB 우선 | 완전 합법, 즉시 | KBO 과제 지연 | A·B 와 병행 (원래 계획) |
| D. 공식 사이트 저속 크롤링 | - | 명시적 금지 위반 | 하지 않음 |

## 5. 페이지 구조 조사표 (KBO 기록실, 참고용)

| 대상 | URL | 필터 | 컬럼 |
|---|---|---|---|
| 타자 기본 | `/Record/Player/HitterBasic/Basic1.aspx` | 시즌(1982-2026), 시리즈, 팀, 포지션. ASP.NET `__doPostBack` | 순위, 선수명, 팀명, AVG, G, PA, AB, R, H, 2B, 3B, HR, TB, RBI, SAC, SF |
| 타자 세부 | `/Record/Player/HitterBasic/Detail1.aspx` | 동일 | BB, IBB, HBP, SO, GDP 등 (미확인) |
| 투수 기본 | `/Record/Player/PitcherBasic/Basic1.aspx` | 동일 | (미확인) |

## 결정 기록
- 2026-09-07: KBO·STATIZ 자동 수집 불가 확인.
- 2026-09-13: kbo-cli 분석으로 네이버 API 구조 파악, 2010~2026 커버리지 확인. 야구나라 데이터 요청 창구 발견. 선택지 정리 → ADR 0008 (사용자 결정 대기).
