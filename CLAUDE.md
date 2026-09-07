# sabior 작업 지침

KBO 세이버메트리션 LLM 프로젝트. 1인, 20주 (2026-09-07 ~ 2027-01-24). 기획서와 일정·ADR의 단일 원본은 Notion:
https://app.notion.com/p/3d12477e31ea81379be8d9a9afe0bac0

## 지켜야 할 원칙
- LLM(에이전트)은 계산하지 않는다. 수치는 `stats/`, `models/` 도구 출력에서만 나온다.
- 모든 사실 테이블은 `known_at` 을 가진다. 백테스트·평가 코드는 `db/snapshots.sql` 의 `*_as_of(d)` 매크로만 사용한다. 원 테이블 직접 조회는 ETL과 탐색용으로만.
- 규정(FA 등급, 보상, 샐러리캡, 드래프트) 수치는 `rules` 테이블에만 둔다. 프롬프트·코드·학습 데이터에 하드코딩 금지.
- 지표 공식은 FanGraphs 정의를 따르고, 리그·연도별 상수는 `league_constants` 에서 읽는다.
- 평가셋(`evals/benchmark/questions.jsonl`)에 쓰인 선수-시즌 조합은 SFT 데이터에서 제외한다.
- 스크래핑 전 `etl/kbo/README.md` 의 사전 점검을 통과해야 한다. 요청 간격 2초 이상, 원본 HTML 캐시 필수.

## 환경
- 장비: 갤럭시북4 울트라, RTX 4070 Laptop 8GB. 4B 모델 주력, 8B는 QLoRA seq 1024. 14B 이상 로컬 학습 제안 금지.
- Python 3.11, uv. 의존성 그룹: dev(기본) / models / agent / finetune / serve.
- 파인튜닝은 WSL2 Ubuntu 권장 (bitsandbytes·Unsloth 호환).

## 명령
- `uv sync`, `uv run pytest`, `uv run python db/init_db.py`, `uv run ruff check .`
- VRAM 실측: `uv run --group finetune python scripts/vram_probe.py --model <id> --seq-len <n> --batch <b>`

## 문서 관례
- 문서와 주석은 한국어, 코드 식별자는 영어.
- 결정은 `docs/ADR/` 에 번호 순으로. 주간 로그는 `docs/weekly/`.
- 게이트 미통과 시 다음 단계로 넘어가지 않는다. 범위 축소 순서: 드래프트 → 보상선수 → FA 행선지 → UI → 선호 최적화.
