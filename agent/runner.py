"""함수호출 루프 러너 (P3 W9 에 구현).

설계 메모
  - 입력: 사용자 질문, as_of(기본 오늘), 모델 어댑터(ollama | anthropic)
  - 루프: 모델 응답에 tool_calls 가 있으면 registry 로 실행 -> 결과를 tool 턴으로 추가 -> 반복
  - 종료: 최종 답변. 답변에 포함된 모든 숫자가 도구 로그에 존재하는지 검사(evals.graders.trace_check)
  - 로그: 호출한 도구, 인자, 결과, 소요 시간을 JSONL 로 남긴다 (SFT 데이터 합성과 평가에 재사용)
"""
