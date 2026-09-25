# 모델카드: Marcel (타자·투수)

| 항목 | 내용 |
|---|---|
| 역할 | 모든 선수 예측 모델의 베이스라인. 이 모델을 이기지 못하면 배포하지 않는다 |
| 코드 | `models/projection/marcel.py` (타자 wOBA), `models/projection/marcel_pitching.py` (투수 FIP) |
| 입력 | 직전 3시즌 기록 (`*_as_of(season_cutoff(t-1))`), 생년월일, t-1 시즌 리그 상수 |
| 출력 | 타자: 이벤트별 타석당 비율, proj_woba, proj_pa. 투수: 아웃당 HR·BB·HBP·SO, proj_fip, proj_ip, 선발 여부 |
| 파라미터 | 타자 가중 5/4/3, 회귀 1200 PA. 투수 가중 3/2/1, 회귀 134 IP. 나이 기준 29세, +0.6%/−0.3% |
| 검증 | MLB 2015~2025 백테스트 (evals/reports/backtest_marcel_mlb.md). 타자 wOBA 가중 RMSE .0307, 투수 FIP 0.703 |
| 적용 리그 | MLB 검증 완료. KBO 는 야구나라 데이터 도착 후 파라미터를 KBO 백테스트로 재조정 |
| 한계 | 파크팩터 미적용, 구간 미출력, 신인 예측 불가 (직전 기록 없음) |
| 버전 | v1 (2026-09-25) |
