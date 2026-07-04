"""
All regex patterns and constants for financial statement parsing.
"""

import re

# ============================================================================
# M-PESA Patterns
# ============================================================================

RECEIPT_PATTERN = re.compile(
    r"^([A-Z0-9]{10})\s+" r"(\d{4}-\d{2}-\d{2})\s+" r"(\d{2}:\d{2}:\d{2})\s+" r"(.*)$"
)

AMOUNT_PATTERN = re.compile(
    r"^(.*?)\s+"
    r"(Completed|Failed|Pending|Complete)\s+"
    r"(-?[\d,]+\.\d{2})\s+"
    r"(-?[\d,]+\.\d{2})\s*$"
)

# ============================================================================
# Phone Patterns
# ============================================================================

PHONE_PATTERNS = [
    re.compile(r"(254\d{9})"),
    re.compile(r"(07\d{8})"),
    re.compile(r"(01\d{8})"),
    re.compile(r"(\+?254|0)?[7-9]\d{8}\b"),
]

# ============================================================================
# Date Patterns
# ============================================================================

DATE_PATTERNS = [
    re.compile(r"\d{4}-\d{2}-\d{2}"),
    re.compile(r"\d{2}/\d{2}/\d{4}"),
    re.compile(r"\d{2}-\d{2}-\d{4}"),
    re.compile(r"[A-Za-z]+\s+\d{1,2},\s+\d{4}"),
]

# ============================================================================
# M-PESA Indicators
# ============================================================================

M_PESA_INDICATORS = [
    "mpesa",
    "m-pesa",
    "safaricom",
    "fuliza",
    "m-shwari",
    "paybill",
    "till",
    "airtime",
    "kcb mpesa",
]

# ============================================================================
# Bank Indicators
# ============================================================================

BANK_INDICATORS = [
    "kcb",
    "equity",
    "stanbic",
    "ncba",
    "absa",
    "cooperative",
    "co-op",
    "dtb",
    "standard chartered",
    "bank account",
    "overdraft",
    "branch",
    "cheque",
]

# ============================================================================
# Financial Keywords (for validation)
# ============================================================================

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
    "funds",
    "cash",
    "banking",
    "financial",
    "debit",
]

# ============================================================================
# Fuliza Patterns (compiled)
# ============================================================================

FULIZA_PATTERNS = [
    re.compile(r"fuliza", re.IGNORECASE),
    re.compile(r"overdraft", re.IGNORECASE),
    re.compile(r"od loan", re.IGNORECASE),
    re.compile(r"fuliza disbursement", re.IGNORECASE),
]

# ============================================================================
# Charge Patterns (compiled regex) - Comprehensive
# ============================================================================

CHARGE_PATTERNS = [
    # Direct charge/fee mentions
    re.compile(r"\bcharge\b", re.IGNORECASE),
    re.compile(r"\bcharges\b", re.IGNORECASE),
    re.compile(r"\bfee\b", re.IGNORECASE),
    re.compile(r"\bfees\b", re.IGNORECASE),
    # Customer/transfer charges
    re.compile(r"customer.*charge", re.IGNORECASE),
    re.compile(r"transfer.*charge", re.IGNORECASE),
    re.compile(r"send money.*charge", re.IGNORECASE),
    # Withdrawal/deposit charges
    re.compile(r"withdrawal.*charge", re.IGNORECASE),
    re.compile(r"deposit.*charge", re.IGNORECASE),
    re.compile(r"agent withdrawal.*charge", re.IGNORECASE),
    re.compile(r"agent deposit.*charge", re.IGNORECASE),
    # Merchant charges
    re.compile(r"merchant.*charge", re.IGNORECASE),
    re.compile(r"buy goods.*charge", re.IGNORECASE),
    re.compile(r"pay merchant.*charge", re.IGNORECASE),
    # Paybill charges
    re.compile(r"pay bill.*charge", re.IGNORECASE),
    re.compile(r"paybill.*charge", re.IGNORECASE),
    # Business charges
    re.compile(r"business payment.*charge", re.IGNORECASE),
    # Transaction costs/fees
    re.compile(r"transaction.*cost", re.IGNORECASE),
    re.compile(r"transaction.*fee", re.IGNORECASE),
    # Service charges
    re.compile(r"service.*fee", re.IGNORECASE),
    re.compile(r"service.*charge", re.IGNORECASE),
    # M-PESA specific
    re.compile(r"m-?pesa.*charge", re.IGNORECASE),
    # Taxes and duties
    re.compile(r"excise", re.IGNORECASE),
    re.compile(r"levy", re.IGNORECASE),
    re.compile(r"tax", re.IGNORECASE),
    re.compile(r"stamp duty", re.IGNORECASE),
]

# ============================================================================
# Mechanic Keywords (internal accounting entries)
# ============================================================================

MECHANIC_KEYWORDS = [
    "overdraft of credit party",
]

# ============================================================================
# Category Patterns
# ============================================================================

CATEGORY_PATTERNS = {
    r"salary payment": "Salary",
    r"funds received from": "Received Money",
    r"business payment from": "Business Payment",
    r"merchant payment": "Buy Goods",
    r"customer payment to small business": "Pochi La Biashara",
    r"pay bill": "PayBill",
    r"withdrawal at agent": "Agent Withdrawal",
    r"deposit at agent": "Agent Deposit",
    r"customer transfer|customer send money|sent to": "Send Money",
    r"airtime": "Airtime",
    r"bundle purchase": "Data Bundle",
    r"m-shwari": "M-Shwari",
    r"international transfer": "International Transfer",
    r"promotion payment": "Promotion",
}

# ============================================================================
# Category Rules: (pattern, category, subcategory, direction)
# ============================================================================

CATEGORY_RULES = [
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

# ============================================================================
# Known PayBills
# ============================================================================

KNOWN_PAYBILLS = {
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

# ============================================================================
# Metadata Patterns
# ============================================================================

METADATA_PATTERNS = {
    "account_name": r"account\s*(?:name|holder)\s*[:.]?\s*([A-Za-z\s]+)",
    "account_number": r"account\s*(?:number|no)\s*[:.]?\s*([\d\s]+)",
    "bank_name": r"bank\s*[:.]?\s*([A-Za-z\s]+)",
    "branch": r"branch\s*[:.]?\s*([A-Za-z\s]+)",
    "phone": r"phone\s*[:.]?\s*([\d\s]+)",
    "currency": r"currency\s*[:.]?\s*([A-Za-z]+)",
}

# ============================================================================
# Amount Patterns
# ============================================================================

AMOUNT_PATTERNS = [
    re.compile(r"[\d,]+\.\d{2}"),
    re.compile(r"KES\s*[\d,]+\.\d{2}"),
    re.compile(r"KSh\s*[\d,]+\.\d{2}"),
]

# ============================================================================
# Email Pattern
# ============================================================================

EMAIL_PATTERN = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")

# ============================================================================
# Transaction Extraction Patterns
# ============================================================================

TX_PATTERN_STRICT = re.compile(
    r"([A-Z0-9]{10})\s+"
    r"(\d{4}-\d{2}-\d{2})\s+"
    r"(\d{2}:\d{2}:\d{2})\s+"
    r"(.+?)\s+"
    r"(Completed|Failed|Pending)\s+"
    r"(-?[\d,]+\.\d{2})\s+"
    r"(-?[\d,]+\.\d{2})\s+"
    r"([\d,]+\.\d{2})"
)

TX_PATTERN_LENIENT = re.compile(
    r"([A-Z0-9]{10})\s+"
    r"(\d{4}-\d{2}-\d{2})\s+"
    r"(\d{2}:\d{2}:\d{2})\s+"
    r"(.+?)\s+"
    r"(Completed|Failed|Pending)\s+"
    r"([\d,]+\.\d{2})\s+"
    r"([\d,]+\.\d{2})\s+"
    r"([\d,]+\.\d{2})",
    re.DOTALL,
)

# ============================================================================
# Fee Detection Constants
# ============================================================================

SMALL_FEE_LIMIT = 500  # Maximum amount to consider as a potential fee

# ============================================================================
# Charge Keywords
# ============================================================================

CHARGE_KEYWORDS = [
    "charge",
    "fee",
    "customer transfer of funds charge",
    "pay merchant charge",
    "pay bill charge",
    "withdrawal charge",
    "agent withdrawal charge",
    "agent deposit charge",
    "send money charge",
]

FOOTER_PATTERNS = [
    re.compile(r"^Disclaimer:", re.IGNORECASE),
    re.compile(r"^Statement Verification Code", re.IGNORECASE),
    re.compile(r"^To verify the validity", re.IGNORECASE),
    re.compile(r"^For self-help dial", re.IGNORECASE),
    re.compile(r"^Web:", re.IGNORECASE),
    re.compile(r"^Twitter:", re.IGNORECASE),
    re.compile(r"^Facebook:", re.IGNORECASE),
    re.compile(r"^Terms and conditions apply", re.IGNORECASE),
    re.compile(r"^Page\s+\d+\s+of\s+\d+$", re.IGNORECASE),
    re.compile(
        r"^Receipt No\.\s+Completion Time\s+Details\s+Transaction Status\s+Paid In\s+Withdrawn\s+Balance$",
        re.IGNORECASE,
    ),
]
