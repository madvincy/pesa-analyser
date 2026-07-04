"""
All regex patterns and constants for the AI Analyzer.
"""

import re
from typing import List, Tuple, Dict, Any

# ─── M-PESA Patterns ──────────────────────────────────────────────────────────

RECEIPT_PATTERN = re.compile(
    r"^([A-Z0-9]{10})\s+" r"(\d{4}-\d{2}-\d{2})\s+" r"(\d{2}:\d{2}:\d{2})\s+" r"(.*)$"
)

AMOUNT_PATTERN = re.compile(
    r"(Completed|Failed|Pending|Complete)\s+"
    r"(-?[\d,]+\.\d{2})\s+"
    r"(-?[\d,]+\.\d{2})\s*$"
)

PHONE_PATTERN = re.compile(r"(\+?254|0)?[7-9]\d{8}\b")
EMAIL_PATTERN = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")

# ─── Kenyan PayBill → Merchant lookup ────────────────────────────────────────

KNOWN_PAYBILLS: Dict[str, Tuple[str, str, str]] = {
    "888880": ("KPLC Prepaid", "utilities", "electricity"),
    "888884": ("KPLC Postpaid", "utilities", "electricity"),
    "888861": ("Nairobi Water", "utilities", "water"),
    "200222": ("KCB Bank", "finance", "bank_transfer"),
    "522522": ("Equity Bank", "finance", "bank_transfer"),
    "400200": ("DSTV", "entertainment", "subscription"),
    "969696": ("Safaricom Data", "airtime", "mobile_data"),
    "290290": ("Fuliza Repay", "loan", "fuliza_repayment"),
    "300300": ("M-Shwari", "loan", "mshwari"),
    "601600": ("Zuku", "utilities", "internet"),
    "802900": ("Faiba", "utilities", "internet"),
    "185185": ("Startimes", "entertainment", "subscription"),
    "111222": ("Stanbic Bank", "finance", "bank_transfer"),
    "303030": ("NCBA Bank", "finance", "bank_transfer"),
}

# ─── Category rules: (pattern, category, subcategory, direction) ─────────────

CATEGORY_RULES: List[Tuple[str, str, str, str]] = [
    (r"received from", "income", "peer_transfer", "in"),
    (r"salary|wages|payroll", "income", "salary", "in"),
    (r"reversal", "income", "reversal", "in"),
    (r"pay bill received|paybill received", "income", "business_receipt", "in"),
    (r"mshwari deposit|m-shwari deposit", "income", "mshwari", "in"),
    (r"sent to|transfer to", "transfer", "peer_transfer", "out"),
    (r"kplc|kenya power", "utilities", "electricity", "out"),
    (r"nairobi water|nwsc", "utilities", "water", "out"),
    (r"zuku|faiba|safaricom home", "utilities", "internet", "out"),
    (r"dstv|startimes|showmax|netflix", "entertainment", "subscription", "out"),
    (r"fuliza", "loan", "fuliza", "out"),
    (r"fuliza repay|repay fuliza", "loan", "fuliza_repayment", "out"),
    (r"m-shwari|mshwari", "loan", "mshwari", "out"),
    (r"kcb mpesa|kcb m-pesa", "loan", "kcb_mpesa", "out"),
    (r"withdraw.*agent|agent.*withdraw", "cash", "withdrawal", "out"),
    (r"airtime|scratch card", "airtime", "airtime", "out"),
    (r"data bundle|data pack", "airtime", "data", "out"),
    (r"uber|bolt|little cab|faras", "transport", "ride_hailing", "out"),
    (r"fuel|petrol|diesel|total energies|kenol|rubis", "transport", "fuel", "out"),
    (r"matatu|bus|sacco", "transport", "public_transport", "out"),
    (
        r"naivas|quickmart|carrefour|chandarana|cleanshelf|uchumi",
        "food",
        "grocery",
        "out",
    ),
    (
        r"java|kfc|chicken inn|pizza|burger|cafe|restaurant|hotel",
        "food",
        "dining",
        "out",
    ),
    (r"jumia|kilimall|amazon", "shopping", "ecommerce", "out"),
    (r"buy goods|till", "shopping", "till_payment", "out"),
    (r"hospital|clinic|pharmacy|chemist|doctor|nhif", "health", "medical", "out"),
    (r"school|university|college|tuition|kcse|knec", "education", "tuition", "out"),
    (
        r"sportpesa|betika|shabiki|mcheza|odibets|premiumbetting",
        "betting",
        "betting",
        "out",
    ),
    (r"sacco|chama|investment|shares|nse|cma", "savings", "investment", "out"),
    (r"mshwari lock|fixed deposit", "savings", "fixed_deposit", "out"),
]

# ─── M-PESA mechanic keywords ────────────────────────────────────────────────

MECHANIC_KEYWORDS = (
    "overdraft of credit party",
    "customer transfer of funds charge",
    "pay merchant charge",
    "pay bill charge",
    "withdrawal charge",
    "agent withdrawal charge",
    "agent deposit charge",
    "send money charge",
)

# ─── Fuliza keywords ─────────────────────────────────────────────────────────

FULIZA_KEYWORDS = (
    "fuliza",
    "overdraft",
    "od loan",
)

# ─── Charge keywords ─────────────────────────────────────────────────────────

CHARGE_KEYWORDS = (
    "charge",
    "fee",
)

# ─── Transaction type mapping ───────────────────────────────────────────────

TRANSACTION_TYPE_MAP = {
    "salary payment": "salary",
    "funds received from": "funds_received",
    "business payment from": "business_payment",
    "merchant payment": "merchant_payment",
    "customer payment to small business": "pochi",
    "pay bill": "paybill",
    "withdrawal at agent": "agent_withdrawal",
    "deposit at agent": "agent_deposit",
    "customer transfer": "customer_transfer",
    "customer send money": "customer_send_money",
    "sent to": "sent_to",
    "airtime": "airtime",
    "bundle purchase": "data_bundle",
    "m-shwari": "m_shwari",
    "international transfer": "international_transfer",
    "promotion payment": "promotion",
}

# ─── Transaction description patterns ──────────────────────────────────────

DESCRIPTION_PATTERNS = [
    # Funds received
    (
        r"^Funds received from\s*-?\s*(?:(?P<phone>(?:254|0)\d{9})\s+)?(?P<name>.+)$",
        "funds_received",
    ),
    # Sent to individual
    (r"^Sent to\s+(?P<phone>(?:254|0)\d{9})\s+(?P<name>.+)$", "sent"),
    # Merchant / Buy Goods
    (
        r"^Merchant Payment(?: Fuliza M-Pesa)? to\s+(?P<till>\d+)(?:\s*-\s*|\s+)(?P<name>.+)$",
        "merchant",
    ),
    # Pochi
    (
        r"^Customer Payment to Small Business(?: to)?\s+(?P<till>\d+)(?:\s*-\s*|\s+)(?P<name>.+)$",
        "pochi",
    ),
    # Paybill
    (
        r"^Pay Bill(?: Online)? to\s+(?P<paybill>\d+)(?:\s*-\s*|\s+)(?P<name>.+)$",
        "paybill",
    ),
    # Withdrawal at agent
    (
        r"^(?:Withdrawal at Agent|Agent Withdrawal)\s+(?:(?P<agent>\d+)(?:\s*-\s*|\s+))?(?P<location>.+)$",
        "withdrawal_agent",
    ),
    # Deposit at agent
    (
        r"^(?:Deposit at Agent|Agent Deposit)\s+(?:(?P<agent>\d+)(?:\s*-\s*|\s+))?(?P<location>.+)$",
        "deposit_agent",
    ),
    # Airtime
    (r"^Airtime Purchase.*?(?P<phone>(?:254|0)\d{9})?$", "airtime"),
    # Fuliza repayment
    (
        r"^OD Loan Repayment to\s+(?P<paybill>\d+)\s*-\s*(?P<name>.+)$",
        "fuliza_repayment",
    ),
    # Overdraft credit
    (r"^OverDraft of Credit Party$", "fuliza_credit"),
]

# ─── Financial statement validation keywords ──────────────────────────────

FINANCIAL_KEYWORDS = [
    "amount",
    "balance",
    "credit",
    "debit",
    "transaction",
    "mpesa",
    "m-pesa",
    "bank",
    "account",
    "withdrawal",
    "deposit",
    "payment",
    "transfer",
    "fee",
    "charge",
    "statement",
    "summary",
    "period",
    "date",
    "opening",
    "closing",
    "total",
    "currency",
    "kes",
    "shillings",
    "receipt",
    "reference",
    "code",
    "service",
    "charges",
    "m-shwari",
    "fuliza",
    "paybill",
    "till",
    "airtime",
    "safaricom",
    "mobile",
    "money",
    "sender",
    "receiver",
]
