# 야구나라 데이터 적재 (ADR 0008, 1차 KBO 소스)

야구나라 데이터 요청 창구로 받은 파일을 sabior 스키마로 적재한다. 파일 형식과 컬럼명은 회신을 받아야 알 수 있으므로, 로더는 **컬럼 매핑 YAML 만 채우면 동작**하도록 만들어 두었다.

## 절차

1. 받은 파일을 `data/raw/yagoonara/<받은날짜>/` 에 원본 그대로 둔다 (git 제외). 함께 온 안내 메일·이용 조건은 같은 폴더에 `TERMS.md` 로 저장한다.
2. `etl/yagoonara/mapping.yaml` 의 각 섹션에 파일명과 컬럼 매핑을 채운다. 예시가 들어 있다.
3. `uv run python -m etl.yagoonara.load --dir data/raw/yagoonara/<받은날짜> --dry-run` 으로 매핑 누락과 행 수를 확인한다.
4. `--dry-run` 을 빼고 실행하면 `source='yagoonara'` 로 적재된다. `ingest_log` 에 기록된다.
5. `uv run pytest tests/test_kbo_load.py` (데이터 도착 후 작성) 로 STATIZ 수동 대조 표본과 비교한다.

## 매핑 규칙

- 선수 식별자: 야구나라 선수 ID 가 있으면 `player_external_ids(source='yagoonara')` 에 넣고 내부 ID 는 `KBO_Y<id>` 로 만든다. ID 가 없으면 이름+생년으로 만들고 동명이인은 수동 확인 목록에 남긴다.
- 팀 코드: `mapping.yaml` 의 `teams` 표로 통일한다 (예: 두산 → KBO_OB, LG → KBO_LG). 구단명 변경(넥센 → 키움, SK → SSG 등)은 시즌별로 같은 프랜차이즈 ID 를 유지한다.
- 이닝: "180.1" 표기는 `stats.pitching.outs_from_ip` 로 아웃 수로 변환한다.
- `known_at`: 시즌 기록은 해당 시즌 11-30, 계약은 발표일. 파일에 날짜가 없으면 이 기본값.
- 없는 컬럼은 NULL 로 두고 데이터 사전에 "야구나라 미제공" 으로 표기한다.

## 이용 조건 확인 (회신 시)

- 재배포 가능 여부, 파생물(모델·집계) 공개 가능 여부, 출처 표기 문구, 상업적 이용(웹서비스) 가능 여부, 갱신 주기.
- 확인 결과는 `data/raw/yagoonara/<날짜>/TERMS.md` 와 ADR 0008 결과 절에 기록한다.
