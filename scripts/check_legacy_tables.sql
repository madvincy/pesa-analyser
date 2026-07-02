SELECT 'User' AS table_name, COUNT(*) FROM "User"
UNION ALL SELECT 'Analysis', COUNT(*) FROM "Analysis"
UNION ALL SELECT 'Account', COUNT(*) FROM "Account"
UNION ALL SELECT 'Session', COUNT(*) FROM "Session"
UNION ALL SELECT 'Payment', COUNT(*) FROM "Payment"
UNION ALL SELECT 'transactions', COUNT(*) FROM transactions;
