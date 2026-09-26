# sabior 설계·진행 문서 (세션 인계용)

> **새 세션은 이 파일을 먼저 읽는다.** 작업을 마치면 "5. 진행 현황"과 "6. 다음 할 일"을 갱신하고 커밋한다.
> 마지막 갱신: 2026-09-26 · 마지막 커밋 기준 `b27c271` · 테스트 44개 통과

---

## 1. 한 줄 요약

KBO 데이터를 계산·예측하는 도구 위에 세이버메트리션처럼 추론하는 LLM 에이전트를 올리고, 그 LLM(오픈 모델)을 노트북에서 직접 파인튜닝하는 1인 프로젝트. 장기적으로 야구 분석 웹서비스로 확장한다.

- 기간: 2026-09-07 ~ 2027-01-24 (18주 코어 + 2주 버퍼). 지금은 P2~P3 을 MLB 데이터로 앞당겨 진행 중.
- 기획서(일정·체크리스트 원본): Notion https://app.notion.com/p/3d12477e31ea81379be8d9a9afe0bac0
- 저장소: https://github.com/hj0304/sabior (main 브랜치에 직접 커밋)

## 2. 절대 원칙 (코드 리뷰 기준)

1. **LLM 은 계산하지 않는다.** 모든 수치는 `stats/`, `models/` 도구 출력에서만 나온다. 에이전트 답변의 숫자는 `evals/graders/trace_check.py` 로 검사한다.
2. **미래 정보 누출 금지.** 모든 사실 테이블에 `known_at`. 모델·백테스트·도구는 `db/snapshots.sql` 의 `*_as_of(d)` 매크로로만 읽는다. 에이전트 러너는 기준일을 모든 도구 호출에 강제로 넣는다(as_of 가드).
3. **평가가 먼저.** 모든 모델은 베이스라인과 같은 하네스에서 비교하고, 파라미터 탐색 구간과 평가 구간을 분리한다. 못 이기면 솔직하게 기록한다.
4. **규정 수치는 `rules` 테이블에만.** 프롬프트·코드·학습 데이터에 하드코딩 금지 (현재 rules 는 비어 있다).
5. **데이터 권리.** 자동 수집이 금지된 사이트(KBO 공식, STATIZ, MyKBO, 야구나라 자동 수집)는 긁지 않는다. 사실 테이블마다 `source` 를 남기고, 공개 서비스에는 권리가 확보된 source 만 노출한다.
6. **예측은 구간으로 말한다.** 점추정만 내는 도구·답변은 형식 위반.

## 3. 확정된 결정 (ADR 요약, 상세는 `docs/ADR/`)

| # | 결정 | 날짜 |
|---|---|---|
| 0001 | KBO 단독 서비스, 스키마는 리그 중립, MLB 는 검증·방법론용 | 09-04 |
| 0002 | LLM 은 도구 호출만, 계산 금지 | 09-04 |
| 0003 | 파인튜닝은 필수 단계 (학습 목표 그 자체) | 09-04 |
| 0004 | 로컬 RTX 4070 Laptop 8GB. **학습·VRAM 측정은 WSL2 에서만** (Windows 는 sysmem 폴백으로 무효) | 09-04, 09-13 갱신 |
| 0005 | 18주 코어 + 2주 버퍼, 범위 축소 순서: 드래프트 → 보상선수 → FA 행선지 → UI → 선호 최적화 | 09-04 |
| 0006 | DuckDB 단일 파일 `data/sabior.duckdb` | 09-04 |
| 0007 | 에이전트 루프 직접 구현 (프레임워크 없음) | 09-04 |
| 0008 | **KBO 선수 기록 1차 소스 = 야구나라 데이터 요청.** 네이버 API 백필 안 함, 공식 사이트 크롤링 안 함 | 09-13, 09-26 재확인 |
| 0009 | 베이스 모델은 실측 수치로 선정. 후보 Qwen3-4B-Instruct-2507, A.X-4.0-Light. Qwen3-8B 제외 | 09-13 |
| 0010 | 로컬 오픈 모델 파인튜닝으로 진행 (API 모델 대체 안 함) | 09-25 |
| 0011 | **프론티어 API 비교(조건 A)는 비용 때문에 안 한다.** 필요하면 Claude Code 세션이 직접 도구를 호출해 상한선 답변을 만든다 | 09-26 |

## 4. 환경과 명령

### 장비·스택
- 갤럭시북4 울트라, RTX 4070 Laptop 8GB (WSL2 가용 약 6.9GB), Windows 11 + WSL2 Ubuntu 24.04 (사용자 `sabior`, sudo 무암호)
- Python 3.11, uv. 의존성 그룹: `dev`(기본) / `models` / `agent` / `finetune` / `unsloth` / `serve`
- Windows venv: `.venv/` (분석·ETL·테스트). WSL venv: `~/.venvs/sabior` (finetune + unsloth, CUDA torch 2.14 cu130)
- Ollama (Windows): `qwen3:4b-instruct` 설치됨. `http://localhost:11434`

### 자주 쓰는 명령 (Windows, 저장소 루트)
```bash
.venv/Scripts/python.exe -m pytest -q                 # 테스트 (uv run 은 그룹 동기화로 패키지를 지울 수 있어 venv 직접 호출 권장)
.venv/Scripts/python.exe -m ruff format . && .venv/Scripts/python.exe -m ruff check .
.venv/Scripts/python.exe db/init_db.py                # 스키마 적용 (여러 번 실행해도 안전)
.venv/Scripts/python.exe etl/mlb/download_lahman.py && .venv/Scripts/python.exe etl/mlb/load_lahman.py
.venv/Scripts/python.exe -m stats.league --league MLB --from 1995 --to 2025
.venv/Scripts/python.exe -m etl.kbo_fa.namu_parse && .venv/Scripts/python.exe -m etl.kbo_fa.load
.venv/Scripts/python.exe -m backtest.harness --league MLB --kind batting --from 2015 --to 2025
.venv/Scripts/python.exe -m backtest.team --league MLB --from 2015 --to 2025
.venv/Scripts/python.exe -m backtest.fa_value
.venv/Scripts/python.exe -m agent.runner "질문" --model ollama:qwen3:4b-instruct [--as-of 2025-01-15]
.venv/Scripts/python.exe -m evals.run_smoke --model ollama:qwen3:4b-instruct
```

### WSL (학습·VRAM)
```bash
# Git Bash 에서 호출할 때는 MSYS_NO_PATHCONV=1 을 붙인다 (경로 변환 방지). PowerShell 에서는 그대로.
wsl -d Ubuntu-24.04 -u sabior -- bash /mnt/c/Users/SSAFY/Desktop/sabior/scripts/wsl_probe.sh <model> <seq> <batch> --unsloth [--ladder]
wsl -d Ubuntu-24.04 -u sabior -- bash /mnt/c/Users/SSAFY/Desktop/sabior/scripts/wsl_run.sh python <script> ...
```

### 알려진 함정
- **Bash 도구에 긴 heredoc(8천 자 이상) 금지** → 큰 파일은 Write 도구로.
- **Windows CUDA 는 VRAM 초과 시 OOM 대신 RAM 으로 넘친다.** 측정은 WSL + `vram_probe.py` 하드 캡.
- **`from_pretrained` 는 eval 모드.** 직접 학습 루프를 쓸 때 `model.train()` 을 빼먹으면 gradient checkpointing 이 적용되지 않는다.
- **A.X 4.0 Light 는 nf4 사전 양자화 체크포인트로 로드**해야 로딩 피크를 피한다: `scripts/prequantize.py` → `data/models/A.X-4.0-Light-bnb-4bit`
- `git push` 가 Git Credential Manager 로그인 창에서 멈출 수 있다 (사용자가 창을 완료해야 함). `timeout 240 git push` 로 감싼다.
- Unsloth 는 실행 시 저장소에 `unsloth_compiled_cache/` 를 만든다 (git·ruff 제외됨).

## 5. 진행 현황

### 5.1 단계별 상태

| 단계 | 계획 | 상태 |
|---|---|---|
| P0 기획·환경 | W1-W2 | **완료.** 스키마, 평가셋 v0 100문항, VRAM 게이트, WSL 환경 |
| P1 데이터 플랫폼 | W3-W5 | **MLB 완료, KBO 대기.** Lahman 1871~2025 적재, 지표 엔진 검증. KBO 선수 기록은 야구나라 데이터 대기 |
| P2 예측 모델 | W6-W8 | **MLB 선행 완료 + KBO FA MVP.** 선수(Marcel, Marcel+, 구간), 팀(시뮬), FA 금액(배수법). FA 행선지·보상선수는 KBO 데이터 필요 |
| P3 에이전트 v1 | W9-W11 | **골격 완료.** 도구 11개, 루프, 채점기, FastAPI, 스모크 12문항 |
| P4 파인튜닝 | W12-W16 | 미착수. 약점 목록 확보 (5.4) |
| P5 서비스화 | W17-W18 | 미착수. FastAPI 골격만 |

### 5.2 데이터 (DuckDB `data/sabior.duckdb`, git 제외)

| 테이블 | 내용 | source |
|---|---|---|
| players / batting / pitching / fielding / team_seasons | MLB 1871~2025 (선수 24,270, 타자 시즌 128,598) | lahman |
| league_constants | MLB 1995~2025 자체 계산 (2024 FanGraphs 관례와 일치) | computed |
| park_factors | MLB Lahman BPF 3,105 팀-시즌 (기본은 미사용, 적용 시 오차 커짐) | lahman_bpf |
| contracts / transactions | **KBO FA 2021~2026 시장 108건** + 보상선수 25·보상금 34 | namu_wiki (8건 namu_wiki+news) |
| team_sim_results | MLB 2026 팀 예측 30팀 | team_sim_v1 |
| rules | **비어 있음** (KBO 규약 원문 미적재) | - |

- KBO FA 원자료: `data/raw/kbo_fa/namu/*.html` (나무위키 문서당 1회 수집), 파싱 결과 `data/processed/kbo_fa_contracts.csv`, 기사 대조 `etl/kbo_fa/verification.csv`
- 야구나라 로더는 준비됨: `etl/yagoonara/` (컬럼 매핑 YAML 만 채우면 적재)

### 5.3 모델 성적 (상세는 `evals/reports/`)

| 과제 | 모델 | 핵심 수치 | 비교 기준 | 리포트 |
|---|---|---|---|---|
| 타자 예측 (MLB) | Marcel+ v1 | 평가 2021~2025 wOBA 가중 RMSE .02976 | Marcel .03106 (−4.2%) | backtest_marcel_mlb.md |
| 타자 구간 | 경험적 잔차 분위 | 80% 구간 적중 .792, 50% .497 | 명목 .80/.50 | 같은 파일 |
| 투수 예측 (MLB) | Marcel 투수 | FIP 가중 RMSE 0.703 | 리그 평균 0.825 | 같은 파일 |
| 팀 예측 (MLB) | 선수 합산 + 피타고리안 + 몬테카를로, 전년 피타고리안 혼합 | 승수 MAE 8.65, PS Brier 0.194, 80% 구간 .803 | 전년 승률 절반 반영 8.84 | backtest_team_mlb.md |
| FA 금액 (KBO) | 직전 연봉 × 등급별 배수 (MVP) | 로그 RMSE .966, 80% 구간 .782 | 회귀 .992 (회귀가 못 이김) | backtest_fa_value_kbo.md |
| 에이전트 (Qwen3-4B, 프롬프트 v1.1) | 스모크 12문항 | 도구 75%, 내용 88%, 환각 거절 75%, 숫자 근거 88%, 21초 | 프롬프트 v1: 거절 50%, 근거 78% | agent_smoke_v0.md |

### 5.4 에이전트 약점 (P4 파인튜닝 대상, 프롬프트로 안 고쳐짐)

1. **도구 호출 날조**: 도구를 부르지 않고 "근거: get_rule" 이라 쓰고 수치를 지어냄 (S11)
2. **도구 없이 답함**: 특정 선수 질문에 조회 없이 일반론 (S03)
3. **검색 실패 후 재시도 안 함**: 한글 이름 실패 후 영문 재검색 없이 포기, MLB 선수를 KBO 로 검색 (S05)
4. **결과 옮기기 오류**: 팀 ID·선수명 번역 오류, 지표 해석 오류 (S02)

### 5.5 베이스 모델 VRAM 실측 (WSL2, Unsloth, 캡 6.5GB)

| 모델 | 통과 설정 | peak | 비고 |
|---|---|---|---|
| Qwen3-4B-Instruct-2507 | seq 2048 × batch 2 (rank 16) | 6.34GB | 4B 주력. rank 32 는 2048×2 OOM |
| A.X-4.0-Light 7B (nf4 사전 양자화) | seq 1536 × 1, 1024 × 2 | 5.78 / 6.01GB | 7B 후보 |
| Qwen3-8B | 없음 | - | 제외 |

## 6. 다음 할 일 (우선순위 순)

### 사용자 행동이 필요한 것
- [ ] **야구나라 데이터 요청 발송** (초안 `docs/data_request_drafts.md`). KBO 선수 기록이 들어와야 P1 KBO, FA 행선지·보상선수, 벤치마크 100문항 대부분이 진행된다. 야구나라는 자동 수집하지 않는다.
- [ ] (선택) KBO 사전 승인 요청 메일

### 바로 할 수 있는 것 (데이터 없이)
1. **도구 개선으로 에이전트 약점 줄이기** (P3)
   - 도구 결과에 팀 한글 이름 추가 (MLB_LAN → "LA 다저스")
   - 주요 MLB 선수 한글 이름 → 영문 매핑 사전을 `search_player` 에
   - 지표 해석 필드 (`wrc_plus_interp`: "리그 평균 대비 +114%")
   - 스모크 재실행 후 `evals/reports/agent_smoke_v0.md` 에 v1.2 열 추가
2. **KBO 규정 KB** (P1): FA 등급·보상, 샐러리캡, 드래프트 규정을 KBO 규약 원문에서 `rules` 테이블로. 원문은 KBO 사이트 e-book (수동 확보). 적재되면 S11 류 질문이 정답을 가진다.
3. **SFT 데이터 합성 파이프라인 설계** (P4 선행): 5.4 약점을 겨냥한 질문 템플릿 × MLB·FA 데이터 × 도구 실행 → 교사 답변 → 숫자 검증 필터. 교사 모델은 API 비용 문제로 **Claude Code 세션이 직접 작성하거나, 규칙 기반 템플릿 답변**으로 (ADR 0011).
4. **첫 SFT 파일럿** (P4): Qwen3-4B, 500 샘플, 1 에폭, WSL + Unsloth. 스모크 재실행으로 약점 변화 측정.
5. KBO FA 나머지 100건 기사 대조 (웹서비스 공개 전 필수)
6. 투수 예측 구간, 예측 모델 잔차에 LightGBM (5% 개선 목표)

### KBO 데이터가 오면
1. `etl/yagoonara/mapping.yaml` 채우고 `load.py --dry-run` → 적재 (source='yagoonara')
2. KBO 리그 상수 계산 (`stats.league --league KBO`), 공개값 대조
3. Marcel·Marcel+ 를 KBO 백테스트로 재조정, 팀 예측 KBO 적용 (포스트시즌 상위 5팀)
4. FA 금액 모델에 성적 피처(직전 3년 WAR) 추가 → 목표 로그 RMSE .80
5. FA 행선지·보상선수 MVP, 벤치마크 100문항 정답 채우기
6. KBO player_id 매핑 (FA 계약의 임시 ID `KBO_N{이름}_{출생연도}` 교체)

## 7. 파일 지도

```
design.md                      ← 이 파일 (세션 인계)
CLAUDE.md                      ← 작업 지침 (자동 로드)
db/schema.sql, snapshots.sql   ← 스키마 v1.3, as_of 매크로
etl/mlb/                       ← Lahman 다운로드·적재
etl/kbo_fa/                    ← KBO FA 계약 (나무위키 파서, 적재, 기사 대조)
etl/yagoonara/                 ← 야구나라 로더 (데이터 대기)
etl/kbo/README.md              ← KBO 소스 점검 결과 (자동 수집 불가 근거)
stats/                         ← 지표 엔진: batting, pitching, league(상수), player(선수 라인), park
models/projection/             ← marcel, marcel_plus(+params/), marcel_pitching, intervals, MODEL_CARD
models/team_sim/sim.py         ← 팀 시뮬레이터
models/fa_value/model.py       ← FA 금액 MVP (SalaryMultipleModel), estimate()
backtest/                      ← harness(선수), team, fa_value
agent/tools/                   ← 도구 11개, registry, base(응답 봉투)
agent/adapters.py, runner.py   ← 모델 어댑터, 함수 호출 루프
agent/prompts/system_v1*.md    ← 시스템 프롬프트 (v1_1 이 현행)
evals/benchmark/               ← questions.jsonl(100문항 v0), smoke_v0.jsonl(12문항)
evals/graders/trace_check.py   ← 숫자 근거 추적 채점
evals/reports/                 ← 모든 백테스트·평가 리포트
finetune/configs/              ← SFT 설정 초안 (Qwen3-4B, A.X)
scripts/                       ← vram_probe, prequantize, wsl_setup/probe/run, check_env
app/api/main.py                ← FastAPI (도구 공유, /v1/ask)
docs/                          ← ADR, weekly 로그, 로드맵, API 명세, 데이터 사전, 모델 선정 기록
```

## 8. 세션 작업 규칙

- 시작: 이 파일 → `CLAUDE.md` → 최근 `docs/weekly/*.md` → `git log --oneline | head` 순으로 읽는다.
- 끝: 이 파일의 5·6절 갱신, 주간 로그에 한 줄, 테스트 통과 확인 후 커밋·푸시. 큰 결정은 ADR 로.
- 커밋 메시지는 한국어, 끝에 `Co-Authored-By` 줄.
- 여러 세션이 동시에 작업할 때는 서로 다른 디렉터리를 맡고, 이 파일은 작업 끝에만 수정한다 (충돌 최소화).
