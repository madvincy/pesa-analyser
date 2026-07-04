"""
Data models for financial statement parsing.
"""

from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum


class TransactionDirection(Enum):
    """Direction of transaction flow."""

    IN = "in"
    OUT = "out"
    UNKNOWN = "unknown"


class TransactionType(Enum):
    """Type of transaction."""

    MERCHANT_PAYMENT = "merchant_payment"
    PAYBILL = "paybill"
    SEND_MONEY = "send_money"
    FUNDS_RECEIVED = "funds_received"
    AGENT_WITHDRAWAL = "agent_withdrawal"
    AGENT_DEPOSIT = "agent_deposit"
    AIRTIME = "airtime"
    DATA_BUNDLE = "data_bundle"
    M_SHWARI = "m_shwari"
    FULIZA_CREDIT = "fuliza_credit"
    FULIZA_REPAYMENT = "fuliza_repayment"
    LOAN_DISBURSEMENT = "loan_disbursement"
    LOAN_REPAYMENT = "loan_repayment"
    REVERSAL = "reversal"
    FEE = "fee"
    SALARY = "salary"
    BUSINESS_PAYMENT = "business_payment"
    POCHI = "pochi"
    DEPOSIT = "deposit"
    WITHDRAWAL = "withdrawal"
    UNKNOWN = "unknown"


@dataclass
class Merchant:
    """Merchant information."""

    name: str
    till_number: Optional[str] = None
    paybill_number: Optional[str] = None
    category: Optional[str] = None
    subcategory: Optional[str] = None


@dataclass
class Customer:
    """Customer information."""

    name: Optional[str] = None
    phone: Optional[str] = None
    account_number: Optional[str] = None


@dataclass
class Transaction:
    """
    Complete transaction model with all fields.

    Separates principal amount from fees, and tracks both paid_in and withdrawn.
    """

    # Core fields
    receipt: str
    date: str
    time: str
    description: str = ""
    details: str = ""

    # Transaction classification
    transaction_type: str = "unknown"
    direction: str = "unknown"  # "in" or "out"

    # Amount fields - separated for accuracy
    principal: float = 0.0  # Main transaction amount
    fee: float = 0.0  # Transaction fee
    paid_in: float = 0.0  # Amount paid in (for income)
    withdrawn: float = 0.0  # Amount withdrawn (for expenses)

    # Balance
    balance: float = 0.0

    # Counterparty information
    customer_name: Optional[str] = None
    customer_phone: Optional[str] = None
    merchant_name: Optional[str] = None
    merchant_number: Optional[str] = None
    paybill_number: Optional[str] = None
    account_reference: Optional[str] = None
    till_number: Optional[str] = None

    # Agent information
    agent_number: Optional[str] = None
    location: Optional[str] = None

    # Fuliza specific
    fuliza_used: bool = False
    fuliza_amount: float = 0.0
    fuliza_repayment: bool = False
    funding_source: Optional[str] = None

    # Additional metadata
    receipt_group: Optional[str] = None
    raw_entries: List[str] = field(default_factory=list)

    # Parsed data
    parsed: Dict[str, Any] = field(default_factory=dict)

    # Status
    status: str = "Completed"

    # Validation
    validation_failed: bool = False

    @property
    def actual_amount(self) -> float:
        """Get the actual amount of the transaction."""
        if self.direction == "in":
            return self.paid_in or self.principal
        else:
            return self.withdrawn or self.principal

    @property
    def total_amount(self) -> float:
        """Get total amount including fees."""
        return self.actual_amount + self.fee

    @property
    def is_income(self) -> bool:
        """Check if this is an income transaction."""
        return self.direction == "in"

    @property
    def is_expense(self) -> bool:
        """Check if this is an expense transaction."""
        return self.direction == "out"

    @property
    def is_fuliza(self) -> bool:
        """Check if this is a Fuliza transaction."""
        return self.fuliza_used

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "receipt": self.receipt,
            "date": self.date,
            "time": self.time,
            "description": self.description,
            "details": self.details or self.description,
            "transaction_type": self.transaction_type,
            "direction": self.direction,
            "principal": round(self.principal, 2),
            "fee": round(self.fee, 2),
            "paid_in": round(self.paid_in, 2),
            "withdrawn": round(self.withdrawn, 2),
            "actual_amount": round(self.actual_amount, 2),
            "total_amount": round(self.total_amount, 2),
            "balance": round(self.balance, 2),
            "customer_name": self.customer_name,
            "customer_phone": self.customer_phone,
            "merchant_name": self.merchant_name,
            "merchant_number": self.merchant_number,
            "paybill_number": self.paybill_number,
            "account_reference": self.account_reference,
            "till_number": self.till_number,
            "agent_number": self.agent_number,
            "location": self.location,
            "fuliza_used": self.fuliza_used,
            "fuliza_amount": round(self.fuliza_amount, 2),
            "fuliza_repayment": self.fuliza_repayment,
            "funding_source": self.funding_source,
            "status": self.status,
            "validation_failed": self.validation_failed,
            "category": self.parsed.get("category", "Other"),
            "phone": self.customer_phone,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Transaction":
        """Create from dictionary."""
        return cls(
            receipt=data.get("receipt", ""),
            date=data.get("date", ""),
            time=data.get("time", ""),
            description=data.get("description", ""),
            details=data.get("details", data.get("description", "")),
            transaction_type=data.get("transaction_type", "unknown"),
            direction=data.get("direction", "unknown"),
            principal=float(data.get("principal", 0)),
            fee=float(data.get("fee", 0)),
            paid_in=float(data.get("paid_in", 0)),
            withdrawn=float(data.get("withdrawn", 0)),
            balance=float(data.get("balance", 0)),
            customer_name=data.get("customer_name"),
            customer_phone=data.get("customer_phone"),
            merchant_name=data.get("merchant_name"),
            merchant_number=data.get("merchant_number"),
            paybill_number=data.get("paybill_number"),
            account_reference=data.get("account_reference"),
            till_number=data.get("till_number"),
            agent_number=data.get("agent_number"),
            location=data.get("location"),
            fuliza_used=bool(data.get("fuliza_used", False)),
            fuliza_amount=float(data.get("fuliza_amount", 0)),
            fuliza_repayment=bool(data.get("fuliza_repayment", False)),
            funding_source=data.get("funding_source"),
            raw_entries=data.get("raw_entries", []),
            parsed=data.get("parsed", {}),
            status=data.get("status", "Completed"),
            validation_failed=bool(data.get("validation_failed", False)),
        )


@dataclass
class StatementMetadata:
    """Metadata for a financial statement."""

    account_name: Optional[str] = None
    account_number: Optional[str] = None
    bank_name: Optional[str] = None
    branch: Optional[str] = None
    phone: Optional[str] = None
    currency: str = "KES"
    period_start: Optional[str] = None
    period_end: Optional[str] = None
    opening_balance: float = 0.0
    closing_balance: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "account_name": self.account_name,
            "account_number": self.account_number,
            "bank_name": self.bank_name,
            "branch": self.branch,
            "phone": self.phone,
            "currency": self.currency,
            "period_start": self.period_start,
            "period_end": self.period_end,
            "opening_balance": self.opening_balance,
            "closing_balance": self.closing_balance,
        }


@dataclass
class MerchantCache:
    """Cache for merchant information."""

    merchants: Dict[str, Merchant] = field(default_factory=dict)

    def get(self, key: str) -> Optional[Merchant]:
        return self.merchants.get(key)

    def set(self, key: str, merchant: Merchant):
        self.merchants[key] = merchant


@dataclass
class CustomerCache:
    """Cache for customer information."""

    customers: Dict[str, Customer] = field(default_factory=dict)

    def get(self, key: str) -> Optional[Customer]:
        return self.customers.get(key)

    def set(self, key: str, customer: Customer):
        self.customers[key] = customer


@dataclass
class ParsedStatement:
    """Complete parsed statement with all data."""

    statement_type: str = "unknown"
    transactions: List[Transaction] = field(default_factory=list)
    raw_text: str = ""
    metadata: StatementMetadata = field(default_factory=StatementMetadata)
    merchant_cache: MerchantCache = field(default_factory=MerchantCache)
    customer_cache: CustomerCache = field(default_factory=CustomerCache)
    receipt_index: Dict[str, Transaction] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "statement_type": self.statement_type,
            "transactions": [t.to_dict() for t in self.transactions],
            "raw_text": self.raw_text,
            "metadata": self.metadata.to_dict(),
        }

    def get_transaction(self, receipt: str) -> Optional[Transaction]:
        """Get transaction by receipt number (O(1))."""
        return self.receipt_index.get(receipt)

    def get_summary(self) -> Dict[str, Any]:
        """Get comprehensive summary."""
        if not self.transactions:
            return self._empty_summary()

        total_income = sum(
            t.principal for t in self.transactions if t.direction == "in"
        )
        total_expenses = sum(
            t.principal + t.fee for t in self.transactions if t.direction == "out"
        )
        total_fees = sum(t.fee for t in self.transactions)

        return {
            "total_transactions": len(self.transactions),
            "total_income": round(total_income, 2),
            "total_expenses": round(total_expenses, 2),
            "total_fees": round(total_fees, 2),
            "net_cash_flow": round(total_income - total_expenses, 2),
            "income_count": sum(1 for t in self.transactions if t.direction == "in"),
            "expense_count": sum(1 for t in self.transactions if t.direction == "out"),
            "fuliza_count": sum(1 for t in self.transactions if t.fuliza_used),
            "fuliza_total": round(
                sum(t.fuliza_amount for t in self.transactions if t.fuliza_used), 2
            ),
        }

    def _empty_summary(self) -> Dict[str, Any]:
        return {
            "total_transactions": 0,
            "total_income": 0.0,
            "total_expenses": 0.0,
            "total_fees": 0.0,
            "net_cash_flow": 0.0,
            "income_count": 0,
            "expense_count": 0,
            "fuliza_count": 0,
            "fuliza_total": 0.0,
        }

    def get_monthly_summary(self) -> List[Dict[str, Any]]:
        """Get monthly breakdown."""
        months = {}
        for tx in self.transactions:
            month = tx.date[:7] if tx.date else "unknown"
            if month not in months:
                months[month] = {
                    "month": month,
                    "income": 0.0,
                    "expenses": 0.0,
                    "fees": 0.0,
                    "transactions": 0,
                }
            months[month]["transactions"] += 1
            if tx.direction == "in":
                months[month]["income"] += tx.principal
            else:
                months[month]["expenses"] += tx.principal + tx.fee
            months[month]["fees"] += tx.fee

        return sorted(
            [{"month": m, **data} for m, data in months.items()],
            key=lambda x: x["month"],
        )

    def get_merchant_summary(self) -> List[Dict[str, Any]]:
        """Get breakdown by merchant."""
        merchants = {}
        for tx in self.transactions:
            key = tx.merchant_name or tx.till_number or tx.paybill_number or "Unknown"
            if key not in merchants:
                merchants[key] = {
                    "merchant": key,
                    "count": 0,
                    "total": 0.0,
                }
            merchants[key]["count"] += 1
            merchants[key]["total"] += tx.principal + tx.fee

        return sorted(merchants.values(), key=lambda x: x["total"], reverse=True)[:20]
