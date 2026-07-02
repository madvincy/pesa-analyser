"""
Staged analysis tables.

Each table holds ONE group of fields from the full analysis result, written
as soon as that group is computed — cheapest/fastest first, AI-enriched
insights last (the only step with real network latency). This lets the
frontend render progressively via WebSocket instead of waiting for the
entire analysis to finish before showing anything.

⚠️ ASSUMPTION: the parent `Analysis` model's table is named "analyses" and
its primary key column `id` is a String/UUID. Adjust the ForeignKey target
and column type below if your actual model differs — I don't have the
contents of app/models/analysis.py yet to confirm this exactly.
"""

import uuid
from datetime import datetime

from sqlalchemy import Column, String, Integer, Float, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import relationship

from app.core.database import Base


# ─── Stage 1: Basic summary (fastest — totals & aggregates) ──────────────────
class AnalysisBasicSummary(Base):
    __tablename__ = "analysis_basic_summary"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    analysis_id = Column(UUID(as_uuid=False), ForeignKey("analyses.id"), unique=True, nullable=False, index=True)

    total_income = Column(Float, default=0)
    total_expenses = Column(Float, default=0)
    net_cash_flow = Column(Float, default=0)
    average_balance = Column(Float, default=0)
    savings_rate = Column(Float, default=0)
    burn_rate_daily = Column(Float, default=0)
    total_fees = Column(Float, default=0)
    fee_pct = Column(Float, default=0)
    fuliza_total = Column(Float, default=0)
    fuliza_count = Column(Integer, default=0)
    betting_total = Column(Float, default=0)
    betting_pct = Column(Float, default=0)
    p2p_total = Column(Float, default=0)
    p2p_count = Column(Integer, default=0)
    highest_transaction = Column(Float, default=0)
    highest_transaction_date = Column(String, nullable=True)
    total_transactions = Column(Integer, default=0)
    transaction_count = Column(Integer, default=0)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    analysis = relationship("Analysis", backref="basic_summary", uselist=False)


# ─── Stage 2: Category breakdown (medium — grouping & sorting) ───────────────
class AnalysisCategoryBreakdown(Base):
    __tablename__ = "analysis_category_breakdown"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    analysis_id = Column(UUID(as_uuid=False), ForeignKey("analyses.id"), unique=True, nullable=False, index=True)

    category_data = Column(JSON, default=list)
    monthly_data = Column(JSON, default=list)
    trend_data = Column(JSON, default=list)
    top_depositors = Column(JSON, default=list)
    top_creditors = Column(JSON, default=list)

    top_category = Column(String, nullable=True)
    top_category_amount = Column(Float, default=0)
    top_category_percent = Column(Float, default=0)
    top_income_source = Column(String, nullable=True)
    income_concentration = Column(Float, default=0)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    analysis = relationship("Analysis", backref="category_breakdown", uselist=False)


# ─── Stage 3: Behavior metrics (heavier — pattern detection) ─────────────────
class AnalysisBehaviorMetrics(Base):
    __tablename__ = "analysis_behavior_metrics"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    analysis_id = Column(UUID(as_uuid=False), ForeignKey("analyses.id"), unique=True, nullable=False, index=True)

    health_score = Column(Integer, default=0)
    health_breakdown = Column(JSON, default=dict)
    fuliza_cycles = Column(JSON, default=dict)
    income_analysis = Column(JSON, default=dict)
    day_of_week_spend = Column(JSON, default=list)
    salary_day = Column(Integer, nullable=True)
    recurring_payments = Column(JSON, default=list)
    anomalies = Column(JSON, default=list)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    analysis = relationship("Analysis", backref="behavior_metrics", uselist=False)


# ─── Stage 4: Insights (slowest — deterministic text, then AI enrichment) ────
class AnalysisInsights(Base):
    __tablename__ = "analysis_insights"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    analysis_id = Column(UUID(as_uuid=False), ForeignKey("analyses.id"), unique=True, nullable=False, index=True)

    insights = Column(JSON, default=list)
    warnings = Column(JSON, default=list)
    recommendations = Column(JSON, default=list)
    income_change = Column(Float, default=0)
    expenses_change = Column(Float, default=0)

    # True once AI enrichment has successfully overwritten the deterministic
    # (fallback) insights/warnings/recommendations above.
    ai_enriched = Column(String, default="pending")  # "pending" | "enriched" | "deterministic_only"

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    analysis = relationship("Analysis", backref="insights_detail", uselist=False)