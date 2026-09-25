"""예측·추정 도구: 선수 예측(구간), 팀 예측, FA 금액 추정, FA 계약 조회, 규정 조회."""

from __future__ import annotations

from pydantic import Field

from agent.tools.base import AsOf, con, not_found, ok
from agent.tools.registry import tool


class ProjectPlayer(AsOf):
    player_id: str
    target_season: int = Field(..., description="예측할 시즌. 입력은 전 시즌 말까지의 기록만 쓴다")
    kind: str = Field("batting", description="'batting' (wOBA) 또는 'pitching' (FIP)")


@tool(
    "project_player",
    "선수의 다음 시즌 성적 예측. 타자는 wOBA 점추정과 50%·80% 구간(Marcel+), 투수는 FIP 점추정과 예상 이닝(Marcel).",
    ProjectPlayer,
)
def project_player(a: ProjectPlayer) -> dict:
    c = con()
    if a.kind == "pitching":
        from models.projection import marcel_pitching

        df = marcel_pitching.project(c, a.player_id.split("_")[0], a.target_season)
        row = df[df["player_id"] == a.player_id] if not df.empty else df
        if row.empty:
            return not_found(
                f"{a.player_id} 의 직전 3시즌 투구 기록이 없어 {a.target_season} 예측 불가"
            )
        r = row.iloc[0]
        return ok(
            {
                "player_id": a.player_id,
                "target_season": a.target_season,
                "proj_fip": r["proj_fip"],
                "proj_ip": r["proj_ip"],
                "starter": bool(r["starter"]),
                "age": r["age"],
                "lg_era_prev": r["lg_era_prev"],
                "model": "marcel_pitching_v1",
            },
            a.as_of_date(),
            ["pitching_seasons"],
            ["구간 미제공 (투수 구간은 개발 예정)"],
        )
    from models.projection import intervals, marcel_plus

    league = a.player_id.split("_")[0]
    base = intervals.project_with_intervals(c, league, a.target_season)
    row = base[base["player_id"] == a.player_id]
    if row.empty:
        return not_found(
            f"{a.player_id} 의 직전 3시즌 타격 기록이 없어 {a.target_season} 예측 불가"
        )
    r = row.iloc[0]
    plus = marcel_plus.project(c, league, a.target_season, marcel_plus.load_params()).set_index(
        "player_id"
    )
    point = (
        float(plus.loc[a.player_id, "proj_woba"])
        if a.player_id in plus.index
        else float(r["proj_woba"])
    )
    shift = point - float(r["proj_woba"])
    return ok(
        {
            "player_id": a.player_id,
            "target_season": a.target_season,
            "proj_woba": point,
            "woba_p10": r["p10"] + shift,
            "woba_p25": r["p25"] + shift,
            "woba_p75": r["p75"] + shift,
            "woba_p90": r["p90"] + shift,
            "proj_pa": r["proj_pa"],
            "age": r["age"],
            "reliability": r["reliability"],
            "lg_woba_prev": r["lg_woba_prev"],
            "model": "marcel_plus_v1 + empirical_intervals",
        },
        a.as_of_date(),
        ["batting_seasons", "league_constants"],
        ["구간은 '주전으로 뛴다면'의 조건부 구간", "파크팩터 미적용"],
    )


class ProjectTeam(AsOf):
    team_id: str
    season: int


@tool(
    "project_team",
    "팀 시즌 예측: 기대 승수와 80% 구간, 포스트시즌 확률, 예상 득점·실점. 저장된 배치 결과를 우선 읽고 없으면 계산한다.",
    ProjectTeam,
)
def project_team(a: ProjectTeam) -> dict:
    c = con()
    df = c.execute(
        "SELECT * FROM team_sim_results WHERE team_id = ? AND season = ? ORDER BY as_of DESC LIMIT 1",
        [a.team_id, a.season],
    ).df()
    if not df.empty:
        r = df.iloc[0].to_dict()
        return ok(
            r, a.as_of_date(), ["team_sim_results"], ["전년 로스터 기준 (오프시즌 이적 미반영)"]
        )
    from models.team_sim.sim import simulate, team_strength

    league = a.team_id.split("_")[0]
    try:
        st = team_strength(c, league, a.season, "prior_roster")
    except Exception as e:  # 데이터 부족
        return not_found(f"{a.team_id} {a.season} 예측에 필요한 데이터가 없다: {e}")
    sim = simulate(st, league, a.season, sigma=0.055)
    row = sim[sim["team_id"] == a.team_id]
    if row.empty:
        return not_found(f"{a.team_id} 가 {a.season} 시즌 팀 목록에 없다")
    return ok(
        row.iloc[0].to_dict(),
        a.as_of_date(),
        ["batting_seasons", "pitching_seasons"],
        ["전년 로스터 기준 (오프시즌 이적 미반영)"],
    )


class FAValue(AsOf):
    market_year: int = Field(
        ..., description="FA 시장 연도 = 계약 후 첫 시즌 (2026 = 2025년 11월 개장 시장)"
    )
    fa_grade: str = Field(..., description="'A', 'B', 'C'")
    age: int
    prev_salary_eok: float = Field(..., description="직전 시즌 연봉 (억 원)")


@tool(
    "estimate_fa_value",
    "KBO FA 계약 총액 추정: 중앙값과 50%·80% 구간(억 원), 예상 연수, 비슷한 과거 계약 3건. 성적 피처가 없어 구간이 넓다.",
    FAValue,
)
def estimate_fa_value(a: FAValue) -> dict:
    from models.fa_value.model import estimate

    try:
        r = estimate(con(), a.market_year, a.fa_grade, a.age, a.prev_salary_eok)
    except Exception as e:
        return not_found(f"추정 실패: {e}")
    return ok(r, a.as_of_date(), ["contracts"], [r.pop("caveat")])


class FAContracts(AsOf):
    market_year: int | None = Field(None, description="시장 연도. 비우면 전체")
    player_name: str | None = Field(None, description="선수 이름 (한글)")
    team_id: str | None = Field(None, description="계약 구단 ID")


@tool(
    "list_fa_contracts",
    "KBO FA 계약 기록 조회 (2021~2026 시장): 총액, 연수, 등급, 원소속·계약 구단, 보상선수.",
    FAContracts,
)
def list_fa_contracts(a: FAContracts) -> dict:
    q = """
        SELECT c.season_start AS market_year, split_part(c.contract_id, '_', 4) AS player_name, c.fa_grade,
               c.age_at_signing AS age, c.prev_team_id, c.team_id AS new_team_id, c.contract_type, c.years_text,
               c.total_amount / 1e8 AS total_eok, c.guaranteed / 1e8 AS guaranteed_eok,
               c.prev_salary / 1e8 AS prev_salary_eok, c.signed_date, c.source,
               json_extract_string(t.details, '$.player_name') AS comp_player
        FROM contracts_as_of(?::DATE) c
        LEFT JOIN transactions t ON t.txn_id = c.contract_id || '_COMP'
        WHERE c.league = 'KBO'
    """
    params: list = [a.as_of_date()]
    if a.market_year:
        q += " AND c.season_start = ?"
        params.append(a.market_year)
    if a.player_name:
        q += " AND split_part(c.contract_id, '_', 4) = ?"
        params.append(a.player_name)
    if a.team_id:
        q += " AND c.team_id = ?"
        params.append(a.team_id)
    rows = (
        con()
        .execute(q + " ORDER BY c.total_amount DESC LIMIT 30", params)
        .df()
        .to_dict(orient="records")
    )
    if not rows:
        return not_found("조건에 맞는 FA 계약이 기준일 시점에 없다")
    return ok(
        rows,
        a.as_of_date(),
        ["contracts", "transactions"],
        ["출처 나무위키(2차), 일부만 기사 대조됨 (source='namu_wiki+news')"],
    )


class Rule(AsOf):
    rule_type: str = Field(
        ..., description="'FA_GRADE', 'FA_COMPENSATION', 'SALARY_CAP', 'DRAFT' 등"
    )
    season: int


@tool("get_rule", "KBO 규정 조회 (적용 시즌 기준). 규정 수치는 이 도구 결과로만 말한다.", Rule)
def get_rule(a: Rule) -> dict:
    df = (
        con()
        .execute(
            "SELECT * FROM rules_as_of(?::DATE, ?) WHERE rule_type = ?",
            [a.as_of_date(), a.season, a.rule_type],
        )
        .df()
    )
    if df.empty:
        return not_found(f"{a.rule_type} 규정이 아직 지식베이스에 없다 (규약 원문 적재 전)")
    return ok(df.to_dict(orient="records"), a.as_of_date(), ["rules"])
