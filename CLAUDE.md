# sabior 작업 지침

KBO 세이버메트리션 LLM 프로젝트. 1인, 2026-09-07 ~ 2027-01-24. 기획서(일정·체크리스트)는 Notion:
https://app.notion.com/p/3d12477e31ea81379be8d9a9afe0bac0

## 세션 시작 시 반드시
1. **`design.md` 를 먼저 읽는다.** 한 것, 결정, 진행 현황, 다음 할 일, 알려진 함정이 모두 있다.
2. 최근 주간 로그(`docs/weekly/` 의 마지막 파일)와 `git log --oneline | head` 를 확인한다.
3. 작업을 마치면 `design.md` 의 5절(진행 현황)·6절(다음 할 일)을 갱신하고, 테스트 통과 후 커밋·푸시한다.

## 지켜야 할 원칙
- LLM(에이전트)은 계산하지 않는다. 수치는 `stats/`, `models/` 도구 출력에서만 나온다.
- 모든 사실 테이블은 `known_at` 을 가진다. 모델·백테스트·도구는 `db/snapshots.sql` 의 `*_as_of(d)` 매크로만 쓴다. 원 테이블 직접 조회는 ETL과 탐색용으로만.
- 규정(FA 등급, 보상, 샐러리캡, 드래프트) 수치는 `rules` 테이블에만 둔다. 프롬프트·코드·학습 데이터에 하드코딩 금지.
- 지표 공식은 FanGraphs 정의, 리그·연도별 상수는 `league_constants` 에서 읽는다.
- 평가셋(`evals/benchmark/`)에 쓰인 선수-시즌 조합은 SFT 데이터에서 제외한다.
- KBO 선수 기록 소스는 야구나라 데이터 요청(ADR 0008). KBO 공식·STATIZ·MyKBO·야구나라는 자동 수집하지 않는다. 다른 수집은 `etl/kbo/README.md` 점검 후, 요청 간격 2초 이상, 원본 캐시 필수.
- 프론티어 API 자동 비교는 하지 않는다 (비용, ADR 0011).
- 모델을 개선했다고 주장하려면 베이스라인과 같은 하네스, 탐색에 쓰지 않은 구간에서 비교한다. 못 이기면 그대로 기록한다.

## 환경
- RTX 4070 Laptop 8GB. **학습·VRAM 측정은 WSL2 Ubuntu-24.04 에서만** (Windows CUDA 는 VRAM 초과 시 RAM 으로 넘쳐 측정이 무효). WSL 가용 VRAM 약 6.9GB.
- 베이스 모델 후보: Qwen3-4B-Instruct-2507 (Unsloth seq 2048×2), A.X-4.0-Light 7B (nf4 사전 양자화 필요). 8B 이상 로컬 학습 제안 금지.
- Python 3.11, uv. 의존성 그룹: dev(기본) / models / agent / finetune / unsloth / serve.
- Windows 에서는 `.venv/Scripts/python.exe` 를 직접 호출한다 (`uv run` 은 그룹 동기화로 finetune 패키지를 지울 수 있다). WSL 은 `scripts/wsl_run.sh`, `scripts/wsl_probe.sh`.
- Bash 도구에 긴 heredoc 금지 (잘림). 큰 파일은 Write 도구로.

## 명령
- 테스트: `.venv/Scripts/python.exe -m pytest -q` · 린트: `.venv/Scripts/python.exe -m ruff format . && .venv/Scripts/python.exe -m ruff check .`
- 에이전트: `.venv/Scripts/python.exe -m agent.runner "질문" --model ollama:qwen3:4b-instruct`
- 스모크 평가: `.venv/Scripts/python.exe -m evals.run_smoke`
- 그 밖의 명령은 `design.md` 4절

## 문서 관례
- 문서와 주석은 한국어, 코드 식별자는 영어.
- 결정은 `docs/ADR/` 에 번호 순으로. 주간 로그는 `docs/weekly/`. 평가·백테스트 리포트는 `evals/reports/`.
- 게이트 미통과 시 다음 단계로 넘어가지 않는다. 범위 축소 순서: 드래프트 → 보상선수 → FA 행선지 → UI → 선호 최적화.
