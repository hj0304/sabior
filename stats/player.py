"""선수 단위 시즌 지표 계산 (P1 W3 선행). DB 행 + league_constants → wOBA, wRAA, wRC+, FIP 등.

- 조회는 as_of 매크로만 쓴다 (기본 as_of = season_cutoff(season)).
- 여러 stint(팀 이동)는 합산한다.
- 파크팩터는 아직 1.0 (W3 후반에 park_factors 연결). FanGraphs 는 리그(AL/NL)별 R/PA 와 투수 타석 제외 wRC/PA 를 쓰므로
  이 구현의 wRC+ 는 공개값과 수 점 차이가 날 수 있다. 허용 오차는 tests/test_player_mlb.py 에 정의.

사용:
    uv run python -m stats.player MLB_judgeaa01 2024
    uv run python -m stats.player --leaders MLB 2024 --min-pa 502
"""

from __future__ import annotations

import argparse

from stats.batting import babip, iso, woba, wraa, wrc, wrc_plus
from stats.constants import LeagueConstants, load_constants
from stats.pitching import era, fip, ip_from_outs, whip

BATTING_SUM_COLS = [
    "g",
    "pa",
    "ab",
    "r",
    "h",
    "doubles",
    "triples",
    "hr",
    "rbi",
    "sb",
    "cs",
    "bb",
    "ibb",
    "so",
    "hbp",
    "sf",
    "sh",
    "gidp",
]
PITCHING_SUM_COLS = [
    "g",
    "gs",
    "w",
    "l",
    "sv",
    "hld",
    "cg",
    "sho",
    "ip_outs",
    "bf",
    "h",
    "r",
    "er",
    "hr",
    "bb",
    "ibb",
    "so",
    "hbp",
    "wp",
    "bk",
]


def _as_of_expr(as_of: str | None, season: int) -> tuple[str, list]:
    if as_of:
        return "?::DATE", [as_of]
    return "season_cutoff(?)", [season]


def batting_line(
    con, player_id: str, season: int, as_of: str | None = None, park_factor: float = 1.0
) -> dict | None:
    """시즌 타격 라인(stint 합산)과 파생 지표. 행이 없으면 None."""
    expr, params = _as_of_expr(as_of, season)
    sums = ", ".join(f"sum(COALESCE({c}, 0)) AS {c}" for c in BATTING_SUM_COLS)
    row = con.execute(
        f"""
        SELECT any_value(league) AS league, string_agg(DISTINCT team_id, ',') AS teams, {sums}
        FROM batting_as_of({expr}) WHERE player_id = ? AND season = ?
        GROUP BY player_id
        """,
        [*params, player_id, season],
    ).fetchone()
    if row is None:
        return None
    cols = ["league", "teams", *BATTING_SUM_COLS]
    d = dict(zip(cols, row, strict=True))
    for c in BATTING_SUM_COLS:
        d[c] = int(d[c])
    c: LeagueConstants = load_constants(con, d["league"], season)
    d["constants_source"] = c.source
    if d["ab"] + d["bb"] - d["ibb"] + d["sf"] + d["hbp"] <= 0:
        return d
    w = woba(
        c,
        ab=d["ab"],
        bb=d["bb"],
        ibb=d["ibb"],
        hbp=d["hbp"],
        h=d["h"],
        doubles=d["doubles"],
        triples=d["triples"],
        hr=d["hr"],
        sf=d["sf"],
    )
    d["woba"] = w
    d["wraa"] = wraa(c, w, d["pa"])
    d["wrc"] = wrc(c, w, d["pa"])
    d["wrc_plus"] = wrc_plus(c, w, d["pa"], park_factor=park_factor)
    d["avg"] = d["h"] / d["ab"] if d["ab"] else None
    obp_den = d["ab"] + d["bb"] + d["hbp"] + d["sf"]
    d["obp"] = (d["h"] + d["bb"] + d["hbp"]) / obp_den if obp_den else None
    singles = d["h"] - d["doubles"] - d["triples"] - d["hr"]
    d["slg"] = (
        (singles + 2 * d["doubles"] + 3 * d["triples"] + 4 * d["hr"]) / d["ab"] if d["ab"] else None
    )
    d["ops"] = (d["obp"] or 0) + (d["slg"] or 0)
    d["iso"] = iso(d["ab"], d["h"], d["doubles"], d["triples"], d["hr"]) if d["ab"] else None
    try:
        d["babip"] = babip(d["ab"], d["h"], d["hr"], d["so"], d["sf"])
    except ValueError:
        d["babip"] = None
    d["park_factor"] = park_factor
    return d


def pitching_line(con, player_id: str, season: int, as_of: str | None = None) -> dict | None:
    expr, params = _as_of_expr(as_of, season)
    sums = ", ".join(f"sum(COALESCE({c}, 0)) AS {c}" for c in PITCHING_SUM_COLS)
    row = con.execute(
        f"""
        SELECT any_value(league) AS league, string_agg(DISTINCT team_id, ',') AS teams, {sums}
        FROM pitching_as_of({expr}) WHERE player_id = ? AND season = ?
        GROUP BY player_id
        """,
        [*params, player_id, season],
    ).fetchone()
    if row is None:
        return None
    cols = ["league", "teams", *PITCHING_SUM_COLS]
    d = dict(zip(cols, row, strict=True))
    for c in PITCHING_SUM_COLS:
        d[c] = int(d[c])
    c = load_constants(con, d["league"], season)
    d["constants_source"] = c.source
    ip = ip_from_outs(d["ip_outs"])
    d["ip"] = ip
    if ip > 0:
        d["era"] = era(d["er"], ip)
        d["fip"] = fip(c, hr=d["hr"], bb=d["bb"], hbp=d["hbp"], so=d["so"], ip=ip)
        d["whip"] = whip(d["bb"], d["h"], ip)
        d["k9"] = d["so"] * 9 / ip
        d["bb9"] = d["bb"] * 9 / ip
        d["k_pct"] = d["so"] / d["bf"] if d["bf"] else None
        d["bb_pct"] = d["bb"] / d["bf"] if d["bf"] else None
    return d


def wrc_plus_leaders(
    con, league: str, season: int, min_pa: int, n: int = 10, as_of: str | None = None
) -> list[dict]:
    expr, params = _as_of_expr(as_of, season)
    ids = [
        r[0]
        for r in con.execute(
            f"""
            SELECT player_id FROM batting_as_of({expr})
            WHERE league = ? AND season = ?
            GROUP BY player_id HAVING sum(COALESCE(pa, 0)) >= ?
            """,
            [*params, league, season, min_pa],
        ).fetchall()
    ]
    rows = [batting_line(con, pid, season, as_of) for pid in ids]
    rows = [
        r | {"player_id": pid} for pid, r in zip(ids, rows, strict=True) if r and "wrc_plus" in r
    ]
    rows.sort(key=lambda r: r["wrc_plus"], reverse=True)
    names = dict(
        con.execute(
            "SELECT player_id, name FROM players WHERE player_id IN (SELECT unnest(?::VARCHAR[]))",
            [[r["player_id"] for r in rows[:n]]],
        ).fetchall()
    )
    for r in rows[:n]:
        r["name"] = names.get(r["player_id"])
    return rows[:n]


def main() -> None:
    from db.init_db import default_db_path, init_db

    ap = argparse.ArgumentParser()
    ap.add_argument("player_id", nargs="?")
    ap.add_argument("season", nargs="?", type=int)
    ap.add_argument("--leaders", nargs=2, metavar=("LEAGUE", "SEASON"))
    ap.add_argument("--min-pa", type=int, default=502)
    ap.add_argument("--as-of", default=None)
    args = ap.parse_args()
    con = init_db(default_db_path())
    if args.leaders:
        league, season = args.leaders[0], int(args.leaders[1])
        for i, r in enumerate(
            wrc_plus_leaders(con, league, season, args.min_pa, 10, args.as_of), 1
        ):
            print(
                f"{i:2d} {r['name']:<22s} {r['teams']:<10s} PA {r['pa']:4d} wOBA {r['woba']:.3f} wRC+ {r['wrc_plus']:6.1f}"
            )
    else:
        b = batting_line(con, args.player_id, args.season, args.as_of)
        if b:
            print({k: (round(v, 3) if isinstance(v, float) else v) for k, v in b.items()})
        p = pitching_line(con, args.player_id, args.season, args.as_of)
        if p:
            print({k: (round(v, 3) if isinstance(v, float) else v) for k, v in p.items()})
    con.close()


if __name__ == "__main__":
    main()
