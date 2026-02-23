"""Tests for deal_flow.py"""
import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import deal_flow as df
df.DB_PATH = Path("/tmp/test_deal_flow.db")


@pytest.fixture(autouse=True)
def clean_db():
    if df.DB_PATH.exists():
        df.DB_PATH.unlink()
    df.init_db()
    yield
    if df.DB_PATH.exists():
        df.DB_PATH.unlink()


def make_deal(**kwargs):
    defaults = dict(company="AcmeCo", sector="SaaS", raise_amount=5_000_000.0, valuation=25_000_000.0)
    defaults.update(kwargs)
    return df.add_deal(**defaults)


def test_add_deal():
    deal = make_deal()
    assert deal.company == "AcmeCo"
    assert deal.stage == df.DealStage.AWARENESS
    assert deal.score == 0


def test_advance_stage():
    deal = make_deal()
    df.advance_stage(deal.deal_id, df.DealStage.FIRST_MEETING, "analyst@vc.com", "Initial screening positive")
    details = df.get_deal_details(deal.deal_id)
    assert details["stage"] == df.DealStage.FIRST_MEETING.value
    assert len(details["stage_history"]) == 1


def test_add_due_diligence():
    deal = make_deal()
    dd = df.add_due_diligence(
        deal.deal_id, df.DDCategory.TECHNICAL,
        findings=["Strong engineering team", "Scalable architecture"],
        red_flags=["Single point of failure in infra"],
        rating=4, reviewer="TechLead"
    )
    assert dd.rating == 4
    assert len(dd.findings) == 2
    assert len(dd.red_flags) == 1


def test_score_deal():
    deal = make_deal()
    df.add_due_diligence(deal.deal_id, df.DDCategory.TECHNICAL, ["Good tech"], rating=4, reviewer="CTO")
    df.add_due_diligence(deal.deal_id, df.DDCategory.MARKET, ["Large TAM"], rating=5, reviewer="VP")
    score = df.score_deal(deal.deal_id)
    assert 0 <= score <= 100


def test_pass_deal():
    deal = make_deal()
    df.pass_deal(deal.deal_id, "Valuation too high", "partner@vc.com")
    details = df.get_deal_details(deal.deal_id)
    assert details["stage"] == df.DealStage.PASSED.value


def test_pipeline_report():
    make_deal(company="Alpha", sector="AI")
    make_deal(company="Beta", sector="Fintech")
    report = df.pipeline_report()
    assert report["total_deals"] >= 2
    assert "by_stage" in report


def test_sector_analysis():
    make_deal(company="X1", sector="AI")
    make_deal(company="X2", sector="AI")
    make_deal(company="X3", sector="Fintech")
    analysis = df.sector_analysis()
    assert "AI" in analysis
    assert analysis["AI"]["count"] >= 2


def test_log_interaction():
    deal = make_deal()
    interaction_id = df.log_interaction(
        deal.deal_id, "call", "Intro call with founders",
        participants=["Partner A", "CEO"], date="2025-01-15"
    )
    assert interaction_id is not None
    details = df.get_deal_details(deal.deal_id)
    assert len(details["interactions"]) == 1


def test_deal_summary():
    deal = make_deal(company="SummaryTest")
    df.add_due_diligence(deal.deal_id, df.DDCategory.TEAM, ["Strong founders"], rating=5, reviewer="GP")
    summary = df.deal_summary_text(deal.deal_id)
    assert "DEAL SUMMARY" in summary
    assert "SummaryTest" in summary


def test_list_deals_filter():
    deal = make_deal(company="FilterTest", sector="HealthTech")
    df.add_due_diligence(deal.deal_id, df.DDCategory.MARKET, ["Good market"], rating=4, reviewer="Analyst")
    df.score_deal(deal.deal_id)
    results = df.list_deals(sector="HealthTech")
    assert len(results) >= 1
    assert results[0]["company"] == "FilterTest"
