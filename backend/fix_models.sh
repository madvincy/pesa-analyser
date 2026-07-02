#!/bin/bash

echo "🔧 Fixing Models..."

cd backend

# Create all model files
cat > app/models/user.py << 'USER_EOF'
# (paste the user.py content above)
USER_EOF

cat > app/models/analysis.py << 'ANALYSIS_EOF'
# (paste the analysis.py content above)
ANALYSIS_EOF

cat > app/models/payment.py << 'PAYMENT_EOF'
# (paste the payment.py content above)
PAYMENT_EOF

cat > app/models/chat.py << 'CHAT_EOF'
# (paste the chat.py content above)
CHAT_EOF

cat > app/models/__init__.py << 'INIT_EOF'
"""Database Models Module"""

from app.models.user import User, ApiKey
from app.models.analysis import Analysis, Transaction
from app.models.payment import Payment, PaymentConfig
from app.models.chat import ChatHistory, ChatSession

__all__ = [
    "User",
    "ApiKey",
    "Analysis",
    "Transaction",
    "Payment",
    "PaymentConfig",
    "ChatHistory",
    "ChatSession"
]
INIT_EOF

echo "✅ Models fixed!"
echo ""
echo "🚀 Start the backend:"
echo "  cd backend && source venv/bin/activate && uvicorn app.main:app --reload"
