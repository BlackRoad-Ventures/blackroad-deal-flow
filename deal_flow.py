#!/usr/bin/env python3
"""
BlackRoad Deal Flow — Investment deal flow and due diligence tracker
"""

import sqlite3
import json
import uuid
from datetime import datetime
from dataclasses import dataclass, field, asdict
from typing import Optional, List
from enum import Enum
from pathlib import Path


DB_PATH = Path("deal_flow.db")


class DealStage(str, Enum):
    AWARENESS = "awareness"
    FIRST_MEETING = "first_meeting"
    DEEP_DIVE = "deep_dive"
    TERM_SHEET = "term_sheet"
    DUE_DILIGENCE = "due_diligence"
    CLOSING = "closing"
    PORTFOLIO = "portfolio"
    PASSED = "passed"


class DDCategory(str, Enum):
    LEGAL = "legal"
    FINANCIAL = "financial"
    TECHNICAL = "technical"
    MARKET = "market"
    TEAM = "team"


class DDStatus(str, Enum):
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    COMPLETE = "complete"
    BLOCKED = "blocked"


STAGE_ORDER = [
    DealStage.AWARENESS, DealStage.FIRST_MEETING, DealStage.DEEP_DIVE,
    DealStage.TERM_SHEET, DealStage.DUE_DILIGENCE, DealStage.CLOSING,
    DealStage.PORTFOLIO
]


@dataclass
class Deal:
    company: str
    sector: str
    raise_amount: float
    valuation: float
    stage: DealStage = DealStage.AWARENESS
    lead_investor: Optional[str] = None
    co_investors: List[str] = field(default_factory=list)
    score: int = 0
    notes: str = ""
    assigned_to: Optional[str] = None
    deal_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    website: str = ""
    founder: str = ""
    contact_email: str = ""

    @property
    def multiple_on_capital(self) -> float:
        if self.raise_amount == 0:
            return 0.0
        return round(self.valuation / self.raise_amount, 2)


@dataclass
class DueDiligence:
    deal_id: str
    category: DDCategory
    status: DDStatus = DDStatus.NOT_STARTED
    findings: List[str] = field(default_factory=list)
    red_flags: List[str] = field(default_factory=list)
    rating: int = 0  # 1-5
    reviewer: str = ""
    dd_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    notes: str = ""


@dataclass
class StageChange:
    deal_id: str
    old_stage: str
    new_stage: str
    changed_by: str
    reason: str
    changed_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    change_id: str = field(default_factory=lambda: str(uuid.uuid4()))


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    """Initialize deal flow database."""
    conn = get_connection()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS deals (
            deal_id         TEXT PRIMARY KEY,
            company         TEXT NOT NULL,
            sector          TEXT NOT NULL,
            raise_amount    REAL NOT NULL,
            valuation       REAL NOT NULL,
            stage           TEXT DEFAULT 'awareness',
            lead_investor   TEXT,
            co_investors    TEXT DEFAULT '[]',
            score           INTEGER DEFAULT 0,
            notes           TEXT DEFAULT '',
            assigned_to     TEXT,
            website         TEXT DEFAULT '',
            founder         TEXT DEFAULT '',
            contact_email   TEXT DEFAULT '',
            created_at      TEXT NOT NULL,
            updated_at      TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS due_diligence (
            dd_id           TEXT PRIMARY KEY,
            deal_id         TEXT NOT NULL,
            category        TEXT NOT NULL,
            status          TEXT DEFAULT 'not_started',
            findings        TEXT DEFAULT '[]',
            red_flags       TEXT DEFAULT '[]',
            rating          INTEGER DEFAULT 0,
            reviewer        TEXT DEFAULT '',
            notes           TEXT DEFAULT '',
            created_at      TEXT NOT NULL,
            updated_at      TEXT NOT NULL,
            FOREIGN KEY (deal_id) REFERENCES deals(deal_id)
        );

        CREATE TABLE IF NOT EXISTS stage_changes (
            change_id       TEXT PRIMARY KEY,
            deal_id         TEXT NOT NULL,
            old_stage       TEXT NOT NULL,
            new_stage       TEXT NOT NULL,
            changed_by      TEXT NOT NULL,
            reason          TEXT DEFAULT '',
            changed_at      TEXT NOT NULL,
            FOREIGN KEY (deal_id) REFERENCES deals(deal_id)
        );

        CREATE TABLE IF NOT EXISTS interactions (
            interaction_id  TEXT PRIMARY KEY,
            deal_id         TEXT NOT NULL,
            type            TEXT NOT NULL,
            description     TEXT NOT NULL,
            participants    TEXT DEFAULT '[]',
            date            TEXT NOT NULL,
            created_at      TEXT NOT NULL,
            FOREIGN KEY (deal_id) REFERENCES deals(deal_id)
        );
    """)
    conn.commit()
    conn.close()


def add_deal(company: str, sector: str, raise_amount: float, valuation: float,
             lead_investor: Optional[str] = None, assigned_to: Optional[str] = None,
             notes: str = "", founder: str = "", contact_email: str = "",
             website: str = "") -> Deal:
    """Add a new deal to the pipeline."""
    init_db()
    deal = Deal(
        company=company, sector=sector, raise_amount=raise_amount,
        valuation=valuation, lead_investor=lead_investor, assigned_to=assigned_to,
        notes=notes, founder=founder, contact_email=contact_email, website=website
    )
    conn = get_connection()
    conn.execute(
        "INSERT INTO deals VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (deal.deal_id, company, sector, raise_amount, valuation, deal.stage.value,
         lead_investor, json.dumps([]), 0, notes, assigned_to,
         website, founder, contact_email, deal.created_at, deal.updated_at)
    )
    conn.commit()
    conn.close()
    return deal


def advance_stage(deal_id: str, new_stage: DealStage, changed_by: str = "system",
                  reason: str = "") -> bool:
    """Advance a deal to the next stage."""
    conn = get_connection()
    row = conn.execute("SELECT * FROM deals WHERE deal_id=?", (deal_id,)).fetchone()
    if not row:
        conn.close()
        raise ValueError(f"Deal {deal_id} not found")
    old_stage = row["stage"]
    now = datetime.utcnow().isoformat()
    new_stage_val = new_stage.value if isinstance(new_stage, DealStage) else new_stage
    conn.execute(
        "UPDATE deals SET stage=?, updated_at=? WHERE deal_id=?",
        (new_stage_val, now, deal_id)
    )
    conn.execute(
        "INSERT INTO stage_changes VALUES (?,?,?,?,?,?,?)",
        (str(uuid.uuid4()), deal_id, old_stage, new_stage_val, changed_by, reason, now)
    )
    conn.commit()
    conn.close()
    return True


def add_due_diligence(deal_id: str, category: DDCategory, findings: List[str],
                      red_flags: Optional[List[str]] = None, rating: int = 3,
                      reviewer: str = "", notes: str = "") -> DueDiligence:
    """Add a due diligence report for a deal."""
    conn = get_connection()
    row = conn.execute("SELECT deal_id FROM deals WHERE deal_id=?", (deal_id,)).fetchone()
    if not row:
        conn.close()
        raise ValueError(f"Deal {deal_id} not found")
    if not 1 <= rating <= 5:
        conn.close()
        raise ValueError("Rating must be between 1 and 5")
    dd = DueDiligence(
        deal_id=deal_id, category=category,
        findings=findings, red_flags=red_flags or [],
        rating=rating, reviewer=reviewer, notes=notes,
        status=DDStatus.COMPLETE
    )
    conn.execute(
        "INSERT INTO due_diligence VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        (dd.dd_id, deal_id, category.value if isinstance(category, DDCategory) else category,
         DDStatus.COMPLETE.value, json.dumps(findings), json.dumps(red_flags or []),
         rating, reviewer, notes, dd.created_at, dd.updated_at)
    )
    conn.commit()
    conn.close()
    return dd


def score_deal(deal_id: str) -> int:
    """Calculate and update the deal score based on DD ratings."""
    conn = get_connection()
    row = conn.execute("SELECT * FROM deals WHERE deal_id=?", (deal_id,)).fetchone()
    if not row:
        conn.close()
        raise ValueError(f"Deal {deal_id} not found")
    dd_items = conn.execute(
        "SELECT * FROM due_diligence WHERE deal_id=?", (deal_id,)
    ).fetchall()

    if not dd_items:
        conn.close()
        return 0

    total_rating = sum(d["rating"] for d in dd_items if d["rating"] > 0)
    avg_rating = total_rating / len(dd_items) if dd_items else 0
    base_score = int((avg_rating / 5.0) * 80)

    total_red_flags = sum(len(json.loads(d["red_flags"])) for d in dd_items)
    penalty = min(total_red_flags * 5, 30)

    categories_covered = len(set(d["category"] for d in dd_items))
    coverage_bonus = min(categories_covered * 4, 20)

    score = max(0, min(100, base_score - penalty + coverage_bonus))

    now = datetime.utcnow().isoformat()
    conn.execute(
        "UPDATE deals SET score=?, updated_at=? WHERE deal_id=?",
        (score, now, deal_id)
    )
    conn.commit()
    conn.close()
    return score


def pass_deal(deal_id: str, reason: str, passed_by: str = "system") -> bool:
    """Pass on a deal (mark as not proceeding)."""
    conn = get_connection()
    row = conn.execute("SELECT stage FROM deals WHERE deal_id=?", (deal_id,)).fetchone()
    if not row:
        conn.close()
        raise ValueError(f"Deal {deal_id} not found")
    old_stage = row["stage"]
    now = datetime.utcnow().isoformat()
    conn.execute(
        "UPDATE deals SET stage=?, updated_at=?, notes=notes||? WHERE deal_id=?",
        (DealStage.PASSED.value, now, f"\n[PASSED] {reason}", deal_id)
    )
    conn.execute(
        "INSERT INTO stage_changes VALUES (?,?,?,?,?,?,?)",
        (str(uuid.uuid4()), deal_id, old_stage, DealStage.PASSED.value, passed_by, reason, now)
    )
    conn.commit()
    conn.close()
    return True


def log_interaction(deal_id: str, interaction_type: str, description: str,
                    participants: Optional[List[str]] = None, date: Optional[str] = None) -> str:
    """Log an interaction with a deal company."""
    conn = get_connection()
    interaction_id = str(uuid.uuid4())
    conn.execute(
        "INSERT INTO interactions VALUES (?,?,?,?,?,?,?)",
        (interaction_id, deal_id, interaction_type, description,
         json.dumps(participants or []), date or datetime.utcnow().isoformat()[:10],
         datetime.utcnow().isoformat())
    )
    conn.commit()
    conn.close()
    return interaction_id


def pipeline_report() -> dict:
    """Generate a full pipeline report."""
    conn = get_connection()
    deals = conn.execute("SELECT * FROM deals ORDER BY created_at DESC").fetchall()
    conn.close()

    by_stage = {}
    for stage in DealStage:
        stage_deals = [dict(d) for d in deals if d["stage"] == stage.value]
        for d in stage_deals:
            d["co_investors"] = json.loads(d["co_investors"])
        by_stage[stage.value] = {
            "count": len(stage_deals),
            "total_raise": sum(d["raise_amount"] for d in stage_deals),
            "deals": stage_deals
        }

    total_pipeline_value = sum(d["raise_amount"] for d in deals if d["stage"] != DealStage.PASSED.value)
    active_deals = [d for d in deals if d["stage"] not in (DealStage.PASSED.value, DealStage.PORTFOLIO.value)]
    portfolio = [d for d in deals if d["stage"] == DealStage.PORTFOLIO.value]

    return {
        "generated_at": datetime.utcnow().isoformat(),
        "total_deals": len(deals),
        "active_pipeline": len(active_deals),
        "portfolio_companies": len(portfolio),
        "passed_deals": by_stage[DealStage.PASSED.value]["count"],
        "total_pipeline_value": total_pipeline_value,
        "by_stage": by_stage,
        "top_scored": sorted([dict(d) for d in deals if d["score"] > 0],
                              key=lambda x: x["score"], reverse=True)[:5]
    }


def get_deal_details(deal_id: str) -> dict:
    """Get full details of a deal including DD and history."""
    conn = get_connection()
    deal = conn.execute("SELECT * FROM deals WHERE deal_id=?", (deal_id,)).fetchone()
    if not deal:
        conn.close()
        raise ValueError(f"Deal {deal_id} not found")
    dd_items = conn.execute(
        "SELECT * FROM due_diligence WHERE deal_id=? ORDER BY created_at", (deal_id,)
    ).fetchall()
    stage_hist = conn.execute(
        "SELECT * FROM stage_changes WHERE deal_id=? ORDER BY changed_at", (deal_id,)
    ).fetchall()
    interactions = conn.execute(
        "SELECT * FROM interactions WHERE deal_id=? ORDER BY date DESC", (deal_id,)
    ).fetchall()
    conn.close()

    result = dict(deal)
    result["co_investors"] = json.loads(result["co_investors"])
    result["due_diligence"] = []
    for d in dd_items:
        item = dict(d)
        item["findings"] = json.loads(item["findings"])
        item["red_flags"] = json.loads(item["red_flags"])
        result["due_diligence"].append(item)
    result["stage_history"] = [dict(s) for s in stage_hist]
    result["interactions"] = []
    for i in interactions:
        item = dict(i)
        item["participants"] = json.loads(item["participants"])
        result["interactions"].append(item)
    return result


def sector_analysis() -> dict:
    """Analyze deals by sector."""
    conn = get_connection()
    rows = conn.execute(
        "SELECT sector, COUNT(*) as cnt, AVG(score) as avg_score, SUM(raise_amount) as total_raise FROM deals GROUP BY sector"
    ).fetchall()
    conn.close()
    return {r["sector"]: {
        "count": r["cnt"],
        "avg_score": round(r["avg_score"] or 0, 1),
        "total_raise": r["total_raise"]
    } for r in rows}


def deal_summary_text(deal_id: str) -> str:
    """Generate a text summary for a deal."""
    details = get_deal_details(deal_id)
    dd_summary = {}
    for dd in details["due_diligence"]:
        dd_summary[dd["category"]] = {"rating": dd["rating"], "red_flags": len(dd["red_flags"])}

    lines = [
        "=" * 65,
        "DEAL SUMMARY",
        "=" * 65,
        f"Company     : {details['company']}",
        f"Sector      : {details['sector']}",
        f"Stage       : {details['stage'].upper()}",
        f"Score       : {details['score']}/100",
        f"Raise Ask   : ${details['raise_amount']:,.0f}",
        f"Valuation   : ${details['valuation']:,.0f}",
        f"Lead        : {details.get('lead_investor') or 'TBD'}",
        f"Assigned To : {details.get('assigned_to') or 'Unassigned'}",
        f"Founder     : {details.get('founder') or 'N/A'}",
        "",
        f"DUE DILIGENCE ({len(details['due_diligence'])} reports)",
        "-" * 40,
    ]
    for dd in details["due_diligence"]:
        flags = len(dd["red_flags"])
        lines.append(f"  [{dd['category'].upper()}] Rating: {dd['rating']}/5 | Red Flags: {flags}")
        for f in dd["red_flags"]:
            lines.append(f"    🔴 {f}")

    lines += [
        "",
        f"STAGE HISTORY ({len(details['stage_history'])} changes)",
        "-" * 40,
    ]
    for s in details["stage_history"]:
        lines.append(f"  {s['changed_at'][:10]}: {s['old_stage']} → {s['new_stage']}")

    lines.append("=" * 65)
    return "\n".join(lines)


def list_deals(stage: Optional[str] = None, sector: Optional[str] = None,
               min_score: int = 0) -> List[dict]:
    """List deals with filters."""
    conn = get_connection()
    query = "SELECT * FROM deals WHERE score >= ?"
    params = [min_score]
    if stage:
        query += " AND stage=?"
        params.append(stage)
    if sector:
        query += " AND sector=?"
        params.append(sector)
    rows = conn.execute(query + " ORDER BY score DESC, created_at DESC", params).fetchall()
    conn.close()
    result = []
    for r in rows:
        d = dict(r)
        d["co_investors"] = json.loads(d["co_investors"])
        result.append(d)
    return result


def cli():
    import sys
    if len(sys.argv) < 2:
        print("Usage: python deal_flow.py <command>")
        print("Commands: add, list, pipeline, sector, score, pass, details, summary")
        return
    init_db()
    cmd = sys.argv[1]
    if cmd == "pipeline":
        report = pipeline_report()
        print(f"Total Deals: {report['total_deals']}")
        print(f"Active Pipeline: {report['active_pipeline']}")
        print(f"Portfolio: {report['portfolio_companies']}")
        print(f"Total Pipeline Value: ${report['total_pipeline_value']:,.0f}")
        for stage, data in report["by_stage"].items():
            if data["count"] > 0:
                print(f"  {stage.upper()}: {data['count']} deals (${data['total_raise']:,.0f})")
    elif cmd == "list":
        for d in list_deals():
            print(f"[{d['stage'].upper()}] {d['company']} | {d['sector']} | Score: {d['score']} | ${d['raise_amount']:,.0f}")
    elif cmd == "sector":
        analysis = sector_analysis()
        for sector, data in analysis.items():
            print(f"{sector}: {data['count']} deals, avg score {data['avg_score']}")
    elif cmd == "summary" and len(sys.argv) >= 3:
        print(deal_summary_text(sys.argv[2]))
    else:
        print(f"Unknown command: {cmd}")


if __name__ == "__main__":
    cli()
