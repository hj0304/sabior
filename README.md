# sabior

KBO 세이버메트리션 LLM. 야구 팬의 질문에 지표 계산과 예측 모델의 결과를 근거로, 세이버메트리션의 논리로 답하는 도구 호출 에이전트를 만들고 그 LLM을 직접 파인튜닝하는 1인 20주 프로젝트.

기획서 (일정·과제·결정 기록의 단일 원본): https://app.notion.com/p/3d12477e31ea81379be8d9a9afe0bac0

## 원칙

1. LLM은 계산하지 않는다. 답변의 모든 수치는 도구 출력에서만 나온다.
2. 평가셋과 백테스트 하네스를 모델보다 먼저 만든다. 개선은 숫자로만 인정한다.
3. 파인튜닝은 지식 주입이 아니라 추론 스타일 학습이다.
4. 작은 표본은 구간과 확률로 말한다.
5. 규정 수치는 `rules` 테이블에만 둔다. 프롬프트나 코드에 하드코딩하지 않는다.
6. 모든 사실 테이블은 `known_at` 을 가지며, 백테스트는 `*_as_of(d)` 매크로만 통해 데이터를 본다.

## 구조

```
sabior/
  data/          raw/ interim/ processed/   git 제외. 원본 HTML·CSV 캐시와 DuckDB 파일
  db/            schema.sql, snapshots.sql, init_db.py
  etl/           common/(캐시 fetcher)  kbo/  mlb/(Lahman 다운로드·적재)
  stats/         지표 엔진: constants, batting(wOBA·wRC+), pitching(FIP)
  models/        projection/ team_sim/ fa_value/ fa_dest/ compensation/ draft/
  backtest/      컷오프 하네스, 누출 테스트
  agent/         tools/(레지스트리) prompts/ rag/ runner.py
  evals/         benchmark/questions.jsonl, graders/, reports/
  finetune/      data_gen/ sft/ dpo/ configs/ model_cards/
  app/           api/(FastAPI) ui/(Gradio)
  docs/          ADR/, weekly/, question_taxonomy.md, data_dictionary.md, vram_probe_log.md
  scripts/       check_env.py, vram_probe.py
  tests/
```

## 시작하기

```bash
uv sync                          # Python 3.11 가상환경 + 기본 의존성(dev 그룹)
uv run python db/init_db.py      # data/sabior.duckdb 생성
uv run pytest                    # 지표 엔진·스키마 테스트
uv run python scripts/check_env.py
```

의존성 그룹은 단계별로 추가한다.

```bash
uv sync --group models           # P2 예측 모델
uv sync --group agent            # P3 에이전트
uv sync --group finetune         # P4 파인튜닝 (WSL2 권장)
uv sync --group serve            # P5 서비스
```

## VRAM 실측 (W1 게이트)

```bash
uv run --group finetune python scripts/vram_probe.py --model Qwen/Qwen3-4B --seq-len 2048 --batch 2
uv run --group finetune python scripts/vram_probe.py --model Qwen/Qwen3-8B --seq-len 1024 --batch 1
```

결과는 `docs/vram_probe_log.md` 에 자동으로 한 줄씩 쌓인다.

## 데이터

MLB 참조 데이터 (지표 엔진 검증용):

```bash
uv run python etl/mlb/download_lahman.py
uv run python etl/mlb/load_lahman.py
```

KBO 수집은 `etl/kbo/README.md` 의 사전 점검(약관, robots.txt, 요청 간격)을 마친 뒤 시작한다.
