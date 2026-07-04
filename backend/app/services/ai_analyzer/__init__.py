"""
AI Analyzer for financial transaction analysis.

This package provides:
- Transaction extraction and parsing
- Deterministic financial analysis
- AI-powered enrichment with multiple providers
- Staged analysis with WebSocket support
"""

from .analyzer import AIAnalyzer
from .models import (
    TransactionDict,
    AnalysisResult,
    StageCallback,
    CategoryBreakdown,
    MonthlyData,
    HealthScore,
    FulizaCycle,
    IncomeAnalysis,
)
from .patterns import (
    CATEGORY_RULES,
    KNOWN_PAYBILLS,
    RECEIPT_PATTERN,
    AMOUNT_PATTERN,
    PHONE_PATTERN,
    EMAIL_PATTERN,
)

__all__ = [
    "AIAnalyzer",
    "TransactionDict",
    "AnalysisResult",
    "StageCallback",
    "CategoryBreakdown",
    "MonthlyData",
    "HealthScore",
    "FulizaCycle",
    "IncomeAnalysis",
    "CATEGORY_RULES",
    "KNOWN_PAYBILLS",
    "RECEIPT_PATTERN",
    "AMOUNT_PATTERN",
    "PHONE_PATTERN",
    "EMAIL_PATTERN",
]

__version__ = "2.0.0"
