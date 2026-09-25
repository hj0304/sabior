"""KBO FA 파서 단위 테스트와 적재 결과 통합 테스트."""

from pathlib import Path

import pytest

from etl.kbo_fa.namu_parse import eok, parse_result, team_id


def test_eok_units():
    assert eok("4억 5,000만") == pytest.approx(4.5)
    assert eok("0.975억") == pytest.approx(0.975)
    assert eok("8,000만") == pytest.approx(0.8)
    assert eok("1억 9000만 원") == pytest.approx(1.9)
    assert eok("-") is None and eok("") is None


def test_parse_result():
    r = parse_result("3+1년 20억 (보장 18억)")
    assert (r["years_text"], r["years"], r["total_eok"], r["guaranteed_eok"]) == (
        "3+1",
        4,
        20.0,
        18.0,
    )
    r = parse_result("4년 48억 (보장 42억)")
    assert (r["years"], r["total_eok"], r["guaranteed_eok"]) == (4, 48.0, 42.0)
    r = parse_result("4+2년 152억")
    assert (r["years"], r["total_eok"], r["guaranteed_eok"]) == (6, 152.0, None)


def test_team_id():
    assert team_id("삼성") == "KBO_SS"
    assert team_id("삼성 라이온즈") == "KBO_SS"
    assert team_id("kt wiz") == "KBO_KT"
    assert team_id("SSG 랜더스") == "KBO_SK"
    assert team_id("텍사스 레인저스") == "텍사스 레인저스"


CSV = Path(__file__).resolve().parents[1] / "data" / "processed" / "kbo_fa_contracts.csv"


@pytest.mark.skipif(not CSV.exists(), reason="FA 계약 CSV 없음")
def test_parsed_contracts_match_verified_news():
    import pandas as pd

    d = pd.read_csv(CSV)
    key = d.set_index(["market_year", "player_name", "prev_team"])
    # 기사로 확인한 값 (etl/kbo_fa/verification.csv)
    assert key.loc[(2026, "강백호", "KBO_KT"), "total_eok"] == 100
    assert key.loc[(2026, "최원준", "KBO_NC"), "new_team"] == "KBO_KT"
    assert key.loc[(2026, "최원준", "KBO_OB"), "contract_type"] == "FA_RESIGN"  # 동명이인 분리
    assert key.loc[(2022, "나성범", "KBO_NC"), "comp_player"] == "하준영"
    assert key.loc[(2021, "이용찬", "KBO_OB"), "years_text"] == "3+1"
    assert (d["contract_type"] == "OVERSEAS").sum() == 1
