"""리그·시즌 집계와 상수 계산 (P1 W3 선행).

방법 (FanGraphs 관례의 근사)
  1. 시즌 리그 합계(PA, AB, H, 2B, 3B, HR, BB, IBB, HBP, SF, R / ER, IP, K, BB, HBP, HR)를 as_of 매크로로 집계한다.
  2. 이벤트별 '원시 득점 가치'(아웃 대비 run value) 는 RE24 가 필요해서 직접 구하지 않고, 기준 가중치를 입력으로 받는다.
     기본값은 FanGraphs 2024 MLB Guts 의 wOBA 가중치를 wOBA 스케일로 나눈 값의 근사 (재확인 필요).
  3. 리그 wOBA 가 리그 OBP 와 같아지도록 스케일(woba_scale)을 맞추고, 가중치에 스케일을 곱해 시즌 가중치를 만든다.
  4. lg_r_per_pa, lg_era, c_fip, runs_per_win(9 * (R/IP) * 1.5 + 3, Tango 근사) 를 계산한다.

한계: 이벤트 데이터가 없으므로 가중치의 상대 비율은 기준 시즌 것을 빌려 쓴다. 득점 환경이 크게 다른 시즌(예: 1968, 2000)은 오차가 커진다.
KBO 는 같은 방식으로 KBO 합계에 맞춰 스케일만 다시 잡는다. 정식 선형 가중치는 이벤트 데이터가 확보되면 교체한다.

사용:
    uv run python -m stats.league --league MLB --from 2015 --to 2025          # league_constants 에 적재
    uv run python -m stats.league --league MLB --from 2024 --to 2024 --dry-run
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass

from stats.constants import LeagueConstants, fip_constant

# FanGraphs 2024 MLB: wBB .689, wHBP .720, w1B .882, w2B 1.254, w3B 1.590, wHR 2.050, scale 1.242 (기억에 의한 전사, 재확인 필요)
RAW_WEIGHTS_REF = {
    "bb": 0.689 / 1.242,
    "hbp": 0.720 / 1.242,
    "1b": 0.882 / 1.242,
    "2b": 1.254 / 1.242,
    "3b": 1.590 / 1.242,
    "hr": 2.050 / 1.242,
}


@dataclass(frozen=True)
class SeasonTotals:
    league: str
    season: int
    pa: int
    ab: int
    h: int
    doubles: int
    triples: int
    hr: int
    bb: int
    ibb: int
    hbp: int
    sf: int
    runs: int
    # 투구 합계
    ip_outs: int
    er: int
    p_hr: int
    p_bb: int
    p_hbp: int
    p_so: int

    @property
    def singles(self) -> int:
        return self.h - self.doubles - self.triples - self.hr

    @property
    def ip(self) -> float:
        return self.ip_outs / 3

    @property
    def obp(self) -> float:
        return (self.h + self.bb + self.hbp) / (self.ab + self.bb + self.hbp + self.sf)

    @property
    def era(self) -> float:
        return self.er * 9 / self.ip


def season_totals(con, league: str, season: int) -> SeasonTotals:
    """as_of 매크로로 시즌 리그 합계를 집계한다 (season_cutoff(season) 시점)."""
    b = con.execute(
        """
        SELECT sum(pa), sum(ab), sum(h), sum(doubles), sum(triples), sum(hr),
               sum(bb), sum(COALESCE(ibb, 0)), sum(COALESCE(hbp, 0)), sum(COALESCE(sf, 0)), sum(r)
        FROM batting_as_of(season_cutoff(?)) WHERE league = ? AND season = ?
        """,
        [season, league, season],
    ).fetchone()
    p = con.execute(
        """
        SELECT sum(ip_outs), sum(er), sum(hr), sum(bb), sum(COALESCE(hbp, 0)), sum(so)
        FROM pitching_as_of(season_cutoff(?)) WHERE league = ? AND season = ?
        """,
        [season, league, season],
    ).fetchone()
    if b[0] is None or p[0] is None:
        raise LookupError(f"{league} {season}: 집계할 행이 없다")
    return SeasonTotals(league, season, *[int(x) for x in b], *[int(x) for x in p])


def compute_constants(
    t: SeasonTotals, raw: dict[str, float] = RAW_WEIGHTS_REF, source: str = "computed"
) -> LeagueConstants:
    """리그 합계와 원시 가중치로 시즌 상수를 만든다. 리그 wOBA = 리그 OBP 가 되도록 스케일을 맞춘다."""
    ubb = t.bb - t.ibb
    denom = t.ab + t.bb - t.ibb + t.sf + t.hbp
    woba_raw = (
        raw["bb"] * ubb
        + raw["hbp"] * t.hbp
        + raw["1b"] * t.singles
        + raw["2b"] * t.doubles
        + raw["3b"] * t.triples
        + raw["hr"] * t.hr
    ) / denom
    scale = t.obp / woba_raw
    c_fip = fip_constant(t.era, t.p_hr, t.p_bb, t.p_hbp, t.p_so, t.ip)
    rpw = 9 * (t.runs / t.ip) * 1.5 + 3
    return LeagueConstants(
        league=t.league,
        season=t.season,
        w_bb=raw["bb"] * scale,
        w_hbp=raw["hbp"] * scale,
        w_1b=raw["1b"] * scale,
        w_2b=raw["2b"] * scale,
        w_3b=raw["3b"] * scale,
        w_hr=raw["hr"] * scale,
        woba_scale=scale,
        lg_woba=t.obp,
        lg_r_per_pa=t.runs / t.pa,
        lg_era=t.era,
        c_fip=c_fip,
        runs_per_win=rpw,
        source=source,
    )


def upsert_constants(con, c: LeagueConstants) -> None:
    con.execute(
        """
        INSERT OR REPLACE INTO league_constants
            (league, season, source, w_bb, w_hbp, w_1b, w_2b, w_3b, w_hr, woba_scale, lg_woba,
             lg_r_per_pa, lg_era, c_fip, runs_per_win, known_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, make_date(?, 11, 30))
        """,
        [
            c.league,
            c.season,
            c.source,
            c.w_bb,
            c.w_hbp,
            c.w_1b,
            c.w_2b,
            c.w_3b,
            c.w_hr,
            c.woba_scale,
            c.lg_woba,
            c.lg_r_per_pa,
            c.lg_era,
            c.c_fip,
            c.runs_per_win,
            c.season,
        ],
    )


def main() -> None:
    from db.init_db import default_db_path, init_db

    ap = argparse.ArgumentParser()
    ap.add_argument("--league", default="MLB")
    ap.add_argument("--from", dest="start", type=int, required=True)
    ap.add_argument("--to", dest="end", type=int, required=True)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    con = init_db(default_db_path())
    cols = [
        "season",
        "lg_woba",
        "woba_scale",
        "w_bb",
        "w_1b",
        "w_hr",
        "lg_r_per_pa",
        "lg_era",
        "c_fip",
        "runs_per_win",
    ]
    print(" ".join(f"{c:>11s}" for c in cols))
    for season in range(args.start, args.end + 1):
        try:
            t = season_totals(con, args.league, season)
        except LookupError as e:
            print(f"{season}: skip ({e})")
            continue
        c = compute_constants(t)
        d = asdict(c)
        print(
            " ".join(f"{d[k]:>11.3f}" if isinstance(d[k], float) else f"{d[k]:>11}" for k in cols)
        )
        if not args.dry_run:
            upsert_constants(con, c)
    con.close()


if __name__ == "__main__":
    main()
