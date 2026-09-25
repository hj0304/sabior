"""KBO FA 계약 CSV(namu_parse 산출물) + 기사 검증 파일을 contracts / transactions 테이블에 적재한다.

- contracts: FA 계약 1건 = 1행. 금액은 원 단위 (억 × 1e8), currency 'KRW'.
- transactions: 계약(FA_SIGN), 보상선수 지명(FA_COMP_PICK), 보상금(FA_COMP_CASH). 보상 행은 related_txn_id 로 계약을 가리킨다.
- player_id: 공식 ID 가 없으므로 임시 규칙 'KBO_N{이름}_{추정 출생연도}' (출생연도 = 시장연도 − 1 − 공시 나이).
  야구나라 데이터가 오면 player_external_ids 로 매핑해 교체한다. 보상선수는 나이를 몰라 'KBO_N{이름}_x'.
- source: 'namu_wiki', 기사로 대조한 행은 'namu_wiki+news' (etl/kbo_fa/verification.csv).
- known_at: 발표일. 백테스트에서 FA 시장 도중 시점(as_of)으로 보면 아직 발표 안 된 계약은 보이지 않는다.

사용:
    uv run python -m etl.kbo_fa.namu_parse && uv run python -m etl.kbo_fa.load
"""

from __future__ import annotations

import re
import uuid
from datetime import date, datetime
from pathlib import Path

import pandas as pd

from db.init_db import default_db_path, init_db

ROOT = Path(__file__).resolve().parents[2]
CSV = ROOT / "data" / "processed" / "kbo_fa_contracts.csv"
VERIFY = Path(__file__).with_name("verification.csv")
EOK = 100_000_000


def parse_kdate(s: str | None, market_year: int) -> date:
    """'2025년 11월 18일' → date. 없으면 시장 개장 연도 12-31 (보수적)."""
    if isinstance(s, str):
        m = re.search(r"(\d{4})년\s*(\d{1,2})월\s*(\d{1,2})일", s)
        if m:
            return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    return date(market_year - 1, 12, 31)


def player_id(name: str, age, market_year: int) -> str:
    if pd.notna(age):
        return f"KBO_N{name}_{int(market_year - 1 - int(age))}"
    return f"KBO_N{name}_x"


def load(con) -> dict[str, int]:
    df = pd.read_csv(CSV)
    df = df[df["contract_type"] != "OVERSEAS"].copy()
    ver = pd.read_csv(VERIFY)
    ver_key = {(r.market_year, r.player_name, r.prev_team): r for r in ver.itertuples()}

    con.execute("DELETE FROM contracts WHERE league = 'KBO' AND source LIKE 'namu_wiki%'")
    con.execute("DELETE FROM transactions WHERE league = 'KBO' AND source LIKE 'namu_wiki%'")
    n_c = n_t = 0
    for r in df.itertuples(index=False):
        v = ver_key.get((r.market_year, r.player_name, r.prev_team))
        source = "namu_wiki+news" if v is not None and v.result == "ok" else "namu_wiki"
        url = v.news_url if v is not None else r.source_url
        comp_cash = r.comp_cash_eok
        if pd.isna(comp_cash) and v is not None and pd.notna(v.comp_cash_eok):
            comp_cash = v.comp_cash_eok
        signed = parse_kdate(r.announced, r.market_year)
        pid = player_id(r.player_name, r.age, r.market_year)
        cid = f"KBO_FA_{r.market_year}_{r.player_name}_{r.prev_team}"
        g = r.guaranteed_eok if pd.notna(r.guaranteed_eok) else None
        con.execute(
            """
            INSERT OR REPLACE INTO contracts
                (contract_id, league, player_id, team_id, signed_date, season_start, years, total_amount,
                 guaranteed, options_amount, currency, contract_type, fa_grade, source_url, known_at, source,
                 prev_salary, age_at_signing, prev_team_id, years_text)
            VALUES (?, 'KBO', ?, ?, ?, ?, ?, ?, ?, ?, 'KRW', ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                cid,
                pid,
                r.new_team,
                signed,
                int(r.market_year),
                int(r.years),
                r.total_eok * EOK,
                g * EOK if g is not None else None,
                r.options_eok * EOK if pd.notna(r.options_eok) else None,
                r.contract_type,
                r.fa_grade if pd.notna(r.fa_grade) else None,
                url,
                signed,
                source,
                r.prev_salary_eok * EOK if pd.notna(r.prev_salary_eok) else None,
                int(r.age) if pd.notna(r.age) else None,
                r.prev_team,
                str(r.years_text),
            ],
        )
        n_c += 1
        sign_txn = f"{cid}_SIGN"
        con.execute(
            """
            INSERT OR REPLACE INTO transactions
                (txn_id, league, txn_date, txn_type, player_id, from_team_id, to_team_id, related_txn_id,
                 details, source_url, known_at, source)
            VALUES (?, 'KBO', ?, 'FA_SIGN', ?, ?, ?, NULL, ?, ?, ?, ?)
            """,
            [
                sign_txn,
                signed,
                pid,
                r.prev_team,
                r.new_team,
                pd.Series(
                    {
                        "player_name": r.player_name,
                        "years_text": r.years_text,
                        "total_eok": r.total_eok,
                    }
                ).to_json(force_ascii=False),
                url,
                signed,
                source,
            ],
        )
        n_t += 1
        if (
            r.contract_type == "FA"
            and isinstance(r.comp_player, str)
            and r.comp_player.strip() not in ("", "-", "없음")
        ):
            con.execute(
                """
                INSERT OR REPLACE INTO transactions
                    (txn_id, league, txn_date, txn_type, player_id, from_team_id, to_team_id, related_txn_id,
                     details, source_url, known_at, source)
                VALUES (?, 'KBO', ?, 'FA_COMP_PICK', ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    f"{cid}_COMP",
                    signed,
                    f"KBO_N{r.comp_player.strip()}_x",
                    r.new_team,
                    r.prev_team,
                    sign_txn,
                    pd.Series({"player_name": r.comp_player.strip(), "for": r.player_name}).to_json(
                        force_ascii=False
                    ),
                    url,
                    signed,
                    source,
                ],
            )
            n_t += 1
        if r.contract_type == "FA" and pd.notna(comp_cash):
            con.execute(
                """
                INSERT OR REPLACE INTO transactions
                    (txn_id, league, txn_date, txn_type, player_id, from_team_id, to_team_id, related_txn_id,
                     details, source_url, known_at, source)
                VALUES (?, 'KBO', ?, 'FA_COMP_CASH', NULL, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    f"{cid}_CASH",
                    signed,
                    r.new_team,
                    r.prev_team,
                    sign_txn,
                    pd.Series({"amount_eok": comp_cash, "for": r.player_name}).to_json(
                        force_ascii=False
                    ),
                    url,
                    signed,
                    source,
                ],
            )
            n_t += 1
    return {"contracts": n_c, "transactions": n_t}


def main() -> None:
    con = init_db(default_db_path())
    run_id = str(uuid.uuid4())
    con.execute(
        "INSERT INTO ingest_log VALUES (?, 'kbo_fa_namu', ?, NULL, NULL, 'running', NULL)",
        [run_id, datetime.now()],
    )
    try:
        counts = load(con)
        con.execute(
            "UPDATE ingest_log SET finished_at = ?, rows = ?, status = 'ok', notes = ? WHERE run_id = ?",
            [datetime.now(), sum(counts.values()), str(counts), run_id],
        )
        print(counts)
    except Exception as e:
        con.execute(
            "UPDATE ingest_log SET finished_at = ?, status = 'failed', notes = ? WHERE run_id = ?",
            [datetime.now(), str(e)[:500], run_id],
        )
        raise
    finally:
        con.close()


if __name__ == "__main__":
    main()
