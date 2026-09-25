"""조회·지표 도구: 선수 검색, 시즌 타격·투구, 리더보드, 리그 상수, 팀 시즌."""

from __future__ import annotations

from pydantic import Field

from agent.tools.base import AsOf, con, not_found, ok
from agent.tools.registry import tool


class SearchPlayer(AsOf):
    name: str = Field(..., description="선수 이름 (일부만 써도 됨). MLB 는 영문, KBO 는 한글")
    league: str | None = Field(None, description="'KBO' 또는 'MLB'")


@tool(
    "search_player",
    "선수를 이름으로 찾아 player_id 후보를 돌려준다. 다른 도구를 부르기 전에 먼저 쓴다.",
    SearchPlayer,
)
def search_player(a: SearchPlayer) -> dict:
    q = """
        SELECT player_id, name, birth_date, bats, throws, debut_season, final_season, league_origin
        FROM players WHERE lower(name) LIKE lower(?) {lg} ORDER BY final_season DESC NULLS LAST LIMIT 10
    """.format(lg="AND league_origin = ?" if a.league else "")
    params = [f"%{a.name}%"] + ([a.league] if a.league else [])
    rows = con().execute(q, params).df().to_dict(orient="records")
    if not rows:
        hint = ""
        if any("가" <= ch <= "힣" for ch in a.name) and a.league != "KBO":
            hint = " MLB 선수 이름은 영문으로 저장돼 있다. 영문 이름(예: 'Aaron Judge' 또는 성 'Judge')으로 다시 검색하라."
        return not_found(f"'{a.name}' 선수를 찾지 못했다 (리그: {a.league or '전체'}).{hint}")
    return ok(rows, a.as_of_date(), ["players"])


class PlayerSeason(AsOf):
    player_id: str = Field(..., description="search_player 로 얻은 ID")
    season: int = Field(..., description="시즌 연도")


@tool(
    "get_batting_season",
    "선수의 시즌 타격 기록과 wOBA, wRAA, wRC+, OPS, ISO, BABIP 를 돌려준다. 파크팩터는 중립(1.0).",
    PlayerSeason,
)
def get_batting_season(a: PlayerSeason) -> dict:
    from stats.player import batting_line

    try:
        b = batting_line(con(), a.player_id, a.season, as_of=a.as_of)
    except LookupError as e:
        return not_found(str(e))
    if b is None:
        return not_found(
            f"{a.player_id} 의 {a.season} 시즌 타격 기록이 기준일 {a.as_of_date()} 시점에 없다"
        )
    return ok(
        b,
        a.as_of_date(),
        ["batting_seasons", "league_constants"],
        ["wRC+ 는 파크팩터 미적용(중립), FanGraphs 값과 수 점 차이 날 수 있음"],
    )


@tool(
    "get_pitching_season",
    "선수의 시즌 투구 기록과 ERA, FIP, WHIP, K%, BB% 를 돌려준다.",
    PlayerSeason,
)
def get_pitching_season(a: PlayerSeason) -> dict:
    from stats.player import pitching_line

    try:
        p = pitching_line(con(), a.player_id, a.season, as_of=a.as_of)
    except LookupError as e:
        return not_found(str(e))
    if p is None:
        return not_found(
            f"{a.player_id} 의 {a.season} 시즌 투구 기록이 기준일 {a.as_of_date()} 시점에 없다"
        )
    return ok(p, a.as_of_date(), ["pitching_seasons", "league_constants"])


class Leaders(AsOf):
    league: str = Field("MLB", description="'KBO' 또는 'MLB'")
    season: int
    min_pa: int = Field(502, description="최소 타석 (MLB 규정타석 502, KBO 는 팀 경기수×3.1)")
    top_n: int = Field(10, ge=1, le=30)


@tool("get_wrc_plus_leaders", "시즌 wRC+ 상위 타자 목록 (최소 타석 조건).", Leaders)
def get_wrc_plus_leaders(a: Leaders) -> dict:
    from stats.player import wrc_plus_leaders

    try:
        rows = wrc_plus_leaders(con(), a.league, a.season, a.min_pa, a.top_n, a.as_of)
    except LookupError as e:
        return not_found(str(e))
    if not rows:
        return not_found(f"{a.league} {a.season} 시즌 PA {a.min_pa} 이상 타자가 없다")
    keep = ["player_id", "name", "teams", "pa", "woba", "wrc_plus", "hr", "ops"]
    return ok([{k: r.get(k) for k in keep} for r in rows], a.as_of_date(), ["batting_seasons"])


class LeagueSeason(AsOf):
    league: str = Field("MLB", description="'KBO' 또는 'MLB'")
    season: int


@tool(
    "get_league_constants",
    "리그·시즌 상수 (리그 wOBA, wOBA 스케일, 선형 가중치, R/PA, 리그 ERA, FIP 상수, 1승당 득점).",
    LeagueSeason,
)
def get_league_constants(a: LeagueSeason) -> dict:
    row = (
        con()
        .execute(
            "SELECT * FROM league_constants_as_of(?::DATE) WHERE league = ? AND season = ? ORDER BY source LIMIT 1",
            [a.as_of_date(), a.league, a.season],
        )
        .df()
    )
    if row.empty:
        return not_found(f"{a.league} {a.season} 리그 상수가 없다")
    return ok(row.iloc[0].to_dict(), a.as_of_date(), ["league_constants"])


class TeamSeason(AsOf):
    team_id: str = Field(..., description="팀 ID (예: MLB_NYA, KBO_LG)")
    season: int


@tool(
    "get_team_season",
    "팀 시즌 성적: 승·패, 득점·실점, Pythagenpat 기대 승률, 최종 순위, 포스트시즌.",
    TeamSeason,
)
def get_team_season(a: TeamSeason) -> dict:
    df = (
        con()
        .execute(
            """
        SELECT s.*, t.name FROM team_seasons_as_of(?::DATE) s LEFT JOIN teams t USING (team_id)
        WHERE s.team_id = ? AND s.season = ?
        """,
            [a.as_of_date(), a.team_id, a.season],
        )
        .df()
    )
    if df.empty:
        return not_found(f"{a.team_id} {a.season} 시즌 팀 기록이 없다")
    r = df.iloc[0].to_dict()
    rs, ra, g = r["runs_scored"], r["runs_allowed"], r["games"]
    x = ((rs + ra) / g) ** 0.287
    r["pythag_wpct"] = rs**x / (rs**x + ra**x)
    r["wpct"] = r["wins"] / g
    keep = [
        "team_id",
        "name",
        "season",
        "games",
        "wins",
        "losses",
        "wpct",
        "runs_scored",
        "runs_allowed",
        "pythag_wpct",
        "final_rank",
        "postseason",
        "sub_league",
        "division",
    ]
    return ok({k: r.get(k) for k in keep}, a.as_of_date(), ["team_seasons"])
