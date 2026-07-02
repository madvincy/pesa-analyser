import { authOptions } from "@/lib/auth";
import { getServerSession } from "next-auth";
import { NextRequest, NextResponse } from "next/server";

const FASTAPI_URL = process.env.FASTAPI_URL ?? "http://localhost:8000";

// ─── Types ────────────────────────────────────────────────────────────────────
// Shape returned by the FastAPI backend (snake_case, matches the Analysis
// model columns + whatever extra fields survive in the Redis-cached
// analysis_result blob from ai_analyzer.py).
interface BackendAnalysisResponse {
  status: "pending" | "processing" | "completed" | "failed" | "unknown";
  message?: string;
  error?: string;
  id?: string;
  file_name?: string;
  statement_type?: string;

  total_income?: number;
  total_expenses?: number;
  net_cash_flow?: number;
  average_balance?: number;
  total_fees?: number;
  total_transactions?: number;
  transaction_count?: number;
  health_score?: number;

  monthly_data?: Array<{
    month: string;
    income: number;
    expenses: number;
    balance: number;
  }>;
  category_data?: Array<{ name: string; value: number }>;
  trend_data?: Array<{ date: string; transactions: number; amount: number }>;

  insights?: string[];
  warnings?: string[];
  recommendations?: string[];

  income_change?: number;
  expenses_change?: number;

  // Present only when the full analysis_result blob is what got returned
  // (Redis cache hit) rather than the trimmed DB-column fallback.
  top_category?: string;
  top_category_amount?: number;
  top_category_percent?: number;
  highest_transaction?: number;
  highest_transaction_date?: string;
  p2p_total?: number;
  p2p_count?: number;
  fuliza_total?: number;
  fuliza_count?: number;
  income_concentration?: number;
  top_income_source?: string;

  created_at?: string;
  completed_at?: string;
}

// Shape the frontend (Dashboard.tsx / AnalysisData type) expects.
interface FrontendAnalysisData {
  totalIncome: number;
  totalExpenses: number;
  netCashFlow: number;
  averageBalance: number;
  incomeChange: number;
  expensesChange: number;
  monthlyData: Array<{
    month: string;
    income: number;
    expenses: number;
    balance: number;
  }>;
  categoryData: Array<{ name: string; value: number }>;
  topCategory: string;
  topCategoryAmount: number;
  topCategoryPercent: number;
  highestTransaction: number;
  highestTransactionDate: string;
  totalFees: number;
  totalTransactions: number;
  p2pTotal: number;
  p2pCount: number;
  fulizaTotal: number;
  fulizaCount: number;
  incomeConcentration: number;
  topIncomeSource: string;
  transactionCount: number;
  trendData: Array<{ date: string; transactions: number; amount: number }>;
  insights: string[];
  warnings: string[];
  recommendations: string[];
}

// ─── Mapper: backend snake_case -> frontend camelCase ─────────────────────────
// Only called when status === "completed". Falls back to sane defaults for
// fields that are only present on a Redis cache hit (the full analysis_result
// blob), since the DB-column-only fallback path in the backend doesn't
// include things like top_category or p2p_total.
function toFrontendShape(data: BackendAnalysisResponse): FrontendAnalysisData {
  return {
    totalIncome: data.total_income ?? 0,
    totalExpenses: data.total_expenses ?? 0,
    netCashFlow: data.net_cash_flow ?? 0,
    averageBalance: data.average_balance ?? 0,
    incomeChange: data.income_change ?? 0,
    expensesChange: data.expenses_change ?? 0,
    monthlyData: data.monthly_data ?? [],
    categoryData: data.category_data ?? [],
    topCategory: data.top_category ?? "N/A",
    topCategoryAmount: data.top_category_amount ?? 0,
    topCategoryPercent: data.top_category_percent ?? 0,
    highestTransaction: data.highest_transaction ?? 0,
    highestTransactionDate: data.highest_transaction_date ?? "",
    totalFees: data.total_fees ?? 0,
    totalTransactions: data.total_transactions ?? 0,
    p2pTotal: data.p2p_total ?? 0,
    p2pCount: data.p2p_count ?? 0,
    fulizaTotal: data.fuliza_total ?? 0,
    fulizaCount: data.fuliza_count ?? 0,
    incomeConcentration: data.income_concentration ?? 0,
    topIncomeSource: data.top_income_source ?? "N/A",
    transactionCount: data.transaction_count ?? data.total_transactions ?? 0,
    trendData: data.trend_data ?? [],
    insights: data.insights ?? [],
    warnings: data.warnings ?? [],
    recommendations: data.recommendations ?? [],
  };
}

// ─── GET /api/analysis/[id] ────────────────────────────────────────────────────
export async function GET(
  request: NextRequest,
  { params }: { params: { id: string } },
) {
  const analysisId = params.id;

  if (!analysisId) {
    return NextResponse.json({ error: "Missing analysis id" }, { status: 400 });
  }

  try {
    // ── Auth ──────────────────────────────────────────────────────────────
    const session = await getServerSession(authOptions);

    if (!session?.user) {
      return NextResponse.json({ error: "Unauthorised" }, { status: 401 });
    }

    // ── Build headers to forward, same pattern as /api/upload ───────────────
    const headers = new Headers();
    if (session.accessToken) {
      headers.set("Authorization", `Bearer ${session.accessToken}`);
    }
    if (
      session.user.id &&
      /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(
        session.user.id,
      )
    ) {
      headers.set("X-User-ID", session.user.id);
    }
    if (session.user.email) {
      headers.set("X-User-Email", session.user.email);
    }
    if (session.user.name) {
      headers.set("X-User-Name", session.user.name);
    }

    // ── Forward to FastAPI ──────────────────────────────────────────────────
    const backendUrl = `${FASTAPI_URL}/api/v1/analysis/${analysisId}`;

    let fastapiResponse: Response;
    try {
      fastapiResponse = await fetch(backendUrl, {
        method: "GET",
        headers,
        credentials: "include",
        // Never cache this at the fetch layer — status changes rapidly
        // while an analysis is still processing.
        cache: "no-store",
      });
    } catch (fetchError) {
      console.error("🔴 [/api/analysis] cannot reach FastAPI:", fetchError);
      return NextResponse.json(
        { error: "Analysis service is unavailable. Please try again later." },
        { status: 503 },
      );
    }

    // ── Parse response body ──────────────────────────────────────────────────
    let data: BackendAnalysisResponse;
    try {
      const text = await fastapiResponse.text();
      data = text ? JSON.parse(text) : ({} as BackendAnalysisResponse);
    } catch (parseError) {
      console.error(
        "🔴 [/api/analysis] failed to parse FastAPI response:",
        parseError,
      );
      return NextResponse.json(
        { error: "Invalid response from analysis service." },
        { status: 502 },
      );
    }

    // ── Handle backend errors ────────────────────────────────────────────────
    if (fastapiResponse.status === 401) {
      return NextResponse.json(
        { error: "Your session has expired. Please sign in again." },
        { status: 401 },
      );
    }

    if (fastapiResponse.status === 403) {
      return NextResponse.json(
        { error: "You don't have access to this analysis." },
        { status: 403 },
      );
    }

    if (fastapiResponse.status === 404) {
      return NextResponse.json(
        { error: "Analysis not found." },
        { status: 404 },
      );
    }

    if (!fastapiResponse.ok) {
      return NextResponse.json(
        {
          error:
            data?.error ??
            data?.message ??
            `Request failed (${fastapiResponse.status})`,
        },
        { status: fastapiResponse.status },
      );
    }

    // ── Non-completed states: pass through as-is ─────────────────────────────
    // Dashboard should branch on `status` before touching numeric fields —
    // there's nothing to map yet while the analysis is pending/processing/failed.
    if (data.status !== "completed") {
      return NextResponse.json({
        status: data.status,
        message: data.message,
        error: data.error,
        id: data.id ?? analysisId,
      });
    }

    // ── Completed: map to the shape the frontend expects ─────────────────────
    const mapped = toFrontendShape(data);

    return NextResponse.json({
      status: "completed",
      ...mapped,
    });
  } catch (error) {
    console.error("🔴 [/api/analysis] unhandled error:", error);
    return NextResponse.json(
      { error: "Failed to fetch analysis. Please try again." },
      { status: 500 },
    );
  }
}
