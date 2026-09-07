"""채점기 (P3 W11).

numeric      : 허용오차 내 일치
interval     : 정답이 제시 구간에 포함되는가 + 구간 폭 페널티
topk         : 정답이 상위 k 후보에 포함되는가
rubric       : LLM judge + 수동 표본 (규정·용어 설명)
refusal      : 환각 함정에서 모른다고 답했는가
trace_check  : 답변 속 모든 숫자가 도구 로그에 존재하는가 (근거 추적성)
"""
