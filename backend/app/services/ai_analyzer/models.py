"""
Data models and type definitions for the AI Analyzer.
"""

from typing import (
    Dict,
    List,
    Any,
    Optional,
    Tuple,
    Callable,
    Awaitable,
    TypedDict,
    Union,
)
from dataclasses import dataclass, field
from enum import Enum


class TransactionDirection(Enum):
    """Direction of transaction flow."""

    IN = "in"
    OUT = "out"
    UNKNOWN = "unknown"


class TransactionType(Enum):
    """Type of transaction."""

    INCOME = "income"
    EXPENSE = "expense"
    TRANSFER = "transfer"
    FULIZA = "fuliza"
    FULIZA_REPAYMENT = "fuliza_repayment"
    LOAN = "loan"
    REVERSAL = "reversal"
    FEE = "fee"
    UNKNOWN = "unknown"


class CategoryType(Enum):
    """Category types."""

    INCOME = "income"
    EXPENSE = "expense"
    TRANSFER = "transfer"
    UTILITIES = "utilities"
    FOOD = "food"
    TRANSPORT = "transport"
    ENTERTAINMENT = "entertainment"
    SHOPPING = "shopping"
    HEALTH = "health"
    EDUCATION = "education"
    BETTING = "betting"
    SAVINGS = "savings"
    LOAN = "loan"
    CASH = "cash"
    AIRTIME = "airtime"
    OTHER = "other"


@dataclass
class TransactionDict:
    """Standardized transaction dictionary."""

    receipt: str = ""
    date: str = ""
    time: str = ""
    description: str = ""
    amount: float = 0.0
    balance: float = 0.0
    status: str = "Completed"
    type: str = "unknown"
    direction: str = "unknown"
    category: str = "other"
    subcategory: str = "other"
    fee: float = 0.0
    fuliza: bool = False
    phone: Optional[str] = None
    till: Optional[str] = None
    paybill: Optional[str] = None
    agent: Optional[str] = None
    location: Optional[str] = None
    party_name: Optional[str] = None
    party_phone: Optional[str] = None
    merchant_till: Optional[str] = None
    paybill_number: Optional[str] = None
    agent_number: Optional[str] = None
    parsed_type: Optional[str] = None
    display_name: Optional[str] = None
    parsed: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict."""
        return {
            "receipt": self.receipt,
            "date": self.date,
            "time": self.time,
            "description": self.description,
            "amount": self.amount,
            "balance": self.balance,
            "status": self.status,
            "type": self.type,
            "direction": self.direction,
            "category": self.category,
            "subcategory": self.subcategory,
            "fee": self.fee,
            "fuliza": self.fuliza,
            "phone": self.phone,
            "till": self.till,
            "paybill": self.paybill,
            "agent": self.agent,
            "location": self.location,
            "party_name": self.party_name,
            "party_phone": self.party_phone,
            "merchant_till": self.merchant_till,
            "paybill_number": self.paybill_number,
            "agent_number": self.agent_number,
            "parsed_type": self.parsed_type,
            "display_name": self.display_name,
            "parsed": self.parsed,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TransactionDict":
        """Create from dict."""
        return cls(
            receipt=data.get("receipt", ""),
            date=data.get("date", ""),
            time=data.get("time", ""),
            description=data.get("description", ""),
            amount=float(data.get("amount", 0) or 0),
            balance=float(data.get("balance", 0) or 0),
            status=data.get("status", "Completed"),
            type=data.get("type", "unknown"),
            direction=data.get("direction", "unknown"),
            category=data.get("category", "other"),
            subcategory=data.get("subcategory", "other"),
            fee=float(data.get("fee", 0) or 0),
            fuliza=bool(data.get("fuliza", False)),
            phone=data.get("phone"),
            till=data.get("till"),
            paybill=data.get("paybill"),
            agent=data.get("agent"),
            location=data.get("location"),
            party_name=data.get("party_name"),
            party_phone=data.get("party_phone"),
            merchant_till=data.get("merchant_till"),
            paybill_number=data.get("paybill_number"),
            agent_number=data.get("agent_number"),
            parsed_type=data.get("parsed_type"),
            display_name=data.get("display_name"),
            parsed=data.get("parsed", {}),
        )


@dataclass
class CategoryBreakdown:
    """Category breakdown data."""

    name: str
    amount: float
    percentage: float = 0.0
    count: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "amount": round(self.amount, 2),
            "percentage": round(self.percentage, 2),
            "count": self.count,
        }


@dataclass
class MonthlyData:
    """Monthly financial data."""

    month: str
    income: float = 0.0
    expenses: float = 0.0
    balance: float = 0.0
    transaction_count: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "month": self.month,
            "income": round(self.income, 2),
            "expenses": round(self.expenses, 2),
            "balance": round(self.balance, 2),
            "transaction_count": self.transaction_count,
        }


@dataclass
class FulizaCycle:
    """Fuliza cycle information."""

    total_fuliza_drawn: float = 0.0
    total_repaid: float = 0.0
    cycle_count: int = 0
    same_day_repayment_rate: float = 0.0
    avg_cycle_amount: float = 0.0
    interpretation: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_fuliza_drawn": round(self.total_fuliza_drawn, 2),
            "total_repaid": round(self.total_repaid, 2),
            "cycle_count": self.cycle_count,
            "same_day_repayment_rate": round(self.same_day_repayment_rate, 1),
            "avg_cycle_amount": round(self.avg_cycle_amount, 2),
            "interpretation": self.interpretation,
        }


@dataclass
class IncomeAnalysis:
    """Income source analysis."""

    by_source: Dict[str, Dict[str, Any]]
    loan_disbursement_warning: bool = False
    loan_as_pct_of_total_inflow: float = 0.0
    total_true_income: float = 0.0
    total_loan_income: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "by_source": self.by_source,
            "loan_disbursement_warning": self.loan_disbursement_warning,
            "loan_as_pct_of_total_inflow": round(self.loan_as_pct_of_total_inflow, 1),
            "total_true_income": round(self.total_true_income, 2),
            "total_loan_income": round(self.total_loan_income, 2),
        }


@dataclass
class HealthScore:
    """Health score information."""

    score: int = 0
    breakdown: Dict[str, int] = field(default_factory=dict)
    label: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "score": self.score,
            "breakdown": self.breakdown,
            "label": self.label,
        }


@dataclass
class AnalysisResult:
    """Complete analysis result."""

    # Core metrics
    total_income: float = 0.0
    total_expenses: float = 0.0
    net_cash_flow: float = 0.0
    savings_rate: float = 0.0
    average_balance: float = 0.0
    burn_rate_daily: float = 0.0

    # Fees
    total_fees: float = 0.0
    fee_pct: float = 0.0

    # Fuliza
    fuliza_total: float = 0.0
    fuliza_count: int = 0
    fuliza_cycles: Dict[str, Any] = field(default_factory=dict)

    # Betting
    betting_total: float = 0.0
    betting_pct: float = 0.0

    # P2P
    p2p_total: float = 0.0
    p2p_count: int = 0

    # Transactions
    total_transactions: int = 0
    highest_transaction: float = 0.0
    highest_transaction_date: str = ""

    # Categories
    category_data: List[Dict[str, Any]] = field(default_factory=list)
    top_category: str = "N/A"
    top_category_amount: float = 0.0
    top_category_percent: float = 0.0

    # Income
    top_income_source: str = "N/A"
    income_concentration: float = 0.0
    income_analysis: Dict[str, Any] = field(default_factory=dict)

    # Reports
    monthly_data: List[Dict[str, Any]] = field(default_factory=list)
    trend_data: List[Dict[str, Any]] = field(default_factory=list)
    day_of_week_spend: List[Dict[str, Any]] = field(default_factory=list)
    salary_day: Optional[int] = None
    recurring_payments: List[Dict[str, Any]] = field(default_factory=list)
    anomalies: List[Dict[str, Any]] = field(default_factory=list)

    # Health
    health_score: int = 0
    health_breakdown: Dict[str, int] = field(default_factory=dict)

    # People
    top_depositors: List[Dict[str, Any]] = field(default_factory=list)
    top_creditors: List[Dict[str, Any]] = field(default_factory=list)

    # AI
    insights: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)

    # Trends
    income_change: float = 0.0
    expenses_change: float = 0.0

    # Metadata
    statement_type: str = "unknown"
    detailed_transaction_metrics: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        result = {}
        for key, value in self.__dict__.items():
            if hasattr(value, "to_dict"):
                result[key] = value.to_dict()
            else:
                result[key] = value
        return result


# Type aliases
StageCallback = Callable[[str, Dict[str, Any]], Awaitable[None]]
TransactionList = List[Union[Dict[str, Any], TransactionDict]]
NormalizedTransaction = Dict[str, Any]
