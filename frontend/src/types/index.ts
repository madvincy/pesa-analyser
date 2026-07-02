export interface AnalysisData {
  totalIncome: number
  totalExpenses: number
  netCashFlow: number
  averageBalance: number
  monthlyData: Array<{
    month: string
    income: number
    expenses: number
    balance: number
  }>
  categoryData: Array<{
    name: string
    value: number
  }>
  topCategory: string
  topCategoryAmount: number
  topCategoryPercent: number
  highestTransaction: number
  highestTransactionDate: string
  totalFees: number
  totalTransactions: number
  p2pTotal: number
  p2pCount: number
  fulizaTotal: number
  fulizaCount: number
  incomeConcentration: number
  topIncomeSource: string
  transactionCount: number
  trendData: Array<{
    date: string
    transactions: number
    amount: number
  }>
  insights: string[]
  warnings: string[]
  recommendations: string[]
  incomeChange: number
  expensesChange: number
}
