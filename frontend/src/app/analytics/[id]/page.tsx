"use client";

import { EmailReportDialog } from "@/components/reports/EmailReportDialog";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useToast } from "@/components/ui/use-toast";
import { analysisService } from "@/services/analysisService";
import { reportService } from "@/services/reportService";
import {
  Activity,
  ArrowLeft,
  Award,
  Download,
  FileText,
  Loader2,
  Mail,
  TrendingDown,
  TrendingUp,
  TrendingUp as TrendUp,
  Wallet,
} from "lucide-react";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ComposedChart,
  Legend,
  Line,
  LineChart,
  Pie,
  PieChart,
  PolarAngleAxis,
  PolarGrid,
  PolarRadiusAxis,
  Radar,
  RadarChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

const COLORS = [
  "#0088FE",
  "#00C49F",
  "#FFBB28",
  "#FF8042",
  "#8884d8",
  "#82ca9d",
  "#ffc658",
  "#ff6b6b",
];

export default function AnalyticsPage() {
  const params = useParams();
  const router = useRouter();
  const { toast } = useToast();
  const analysisId = params.id as string;
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [exporting, setExporting] = useState<{ pdf: boolean; csv: boolean }>({
    pdf: false,
    csv: false,
  });

  useEffect(() => {
    if (analysisId) {
      fetchAnalytics();
    }
  }, [analysisId]);

  const fetchAnalytics = async () => {
    try {
      setLoading(true);
      const result = await analysisService.getAnalysis(analysisId);
      setData(result);
    } catch (error: any) {
      console.error("Failed to fetch analytics:", error);

      if (error.status === 404) {
        toast({
          title: "Not Found",
          description: "Analysis not found",
          variant: "destructive",
        });
      } else if (error.status === 403) {
        toast({
          title: "Access Denied",
          description: "You don't have permission to view this analysis",
          variant: "destructive",
        });
      } else if (error.status === 402) {
        toast({
          title: "Payment Required",
          description: "Please complete payment to access this analysis",
          variant: "destructive",
        });
      } else {
        toast({
          title: "Error",
          description: error.message || "Failed to load analytics",
          variant: "destructive",
        });
      }

      // Redirect to dashboard if analysis not found
      if (error.status === 404 || error.status === 403) {
        setTimeout(() => router.push("/dashboard"), 2000);
      }
    } finally {
      setLoading(false);
    }
  };

  const handleExportPDF = async () => {
    setExporting((prev) => ({ ...prev, pdf: true }));
    try {
      await reportService.downloadAndSave(analysisId, "pdf");
      toast({
        title: "Success",
        description: "PDF report downloaded successfully",
      });
    } catch (error: any) {
      toast({
        title: "Export Failed",
        description: error.message || "Failed to export PDF report",
        variant: "destructive",
      });
    } finally {
      setExporting((prev) => ({ ...prev, pdf: false }));
    }
  };

  const handleExportCSV = async () => {
    setExporting((prev) => ({ ...prev, csv: true }));
    try {
      await reportService.downloadAndSave(analysisId, "csv");
      toast({
        title: "Success",
        description: "CSV data exported successfully",
      });
    } catch (error: any) {
      toast({
        title: "Export Failed",
        description: error.message || "Failed to export CSV data",
        variant: "destructive",
      });
    } finally {
      setExporting((prev) => ({ ...prev, csv: false }));
    }
  };

  // ─── Memoize chart data ──────────────────────────────────────────────
  const chartData = useMemo(
    () => ({
      monthlyData: data?.monthly_data || [],
      categoryData: data?.category_data || [],
      trendData: data?.trend_data || [],
    }),
    [data],
  );

  if (loading) {
    return (
      <div className="flex items-center justify-center h-96">
        <div className="text-center">
          <Loader2 className="h-12 w-12 animate-spin text-primary mx-auto" />
          <p className="mt-4 text-muted-foreground">Loading analytics...</p>
        </div>
      </div>
    );
  }

  if (!data) {
    return (
      <div className="text-center py-12">
        <p className="text-muted-foreground">No analytics data found</p>
        <Button className="mt-4" onClick={() => router.push("/dashboard")}>
          <ArrowLeft className="h-4 w-4 mr-2" />
          Back to Dashboard
        </Button>
      </div>
    );
  }

  return (
    <div className="container mx-auto py-8 space-y-6">
      {/* Header with Export Buttons */}
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div className="flex items-center gap-4">
          <Button
            variant="outline"
            size="sm"
            onClick={() => router.push("/dashboard")}
          >
            <ArrowLeft className="h-4 w-4 mr-2" />
            Back to History
          </Button>
          <div>
            <h1 className="text-2xl font-bold font-playfair">
              Financial Analysis Report
            </h1>
            <p className="text-sm text-muted-foreground">
              {data.file_name || "Unknown file"} • Generated{" "}
              {data.completed_at || data.created_at
                ? new Date(
                    data.completed_at || data.created_at,
                  ).toLocaleDateString()
                : "Recently"}
            </p>
          </div>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={handleExportPDF}
            disabled={exporting.pdf}
          >
            <FileText className="h-4 w-4 mr-2" />
            {exporting.pdf ? "Exporting..." : "PDF"}
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={handleExportCSV}
            disabled={exporting.csv}
          >
            <Download className="h-4 w-4 mr-2" />
            {exporting.csv ? "Exporting..." : "CSV"}
          </Button>
          <EmailReportDialog
            analysisId={analysisId}
            analysisName={data.file_name}
            onSuccess={() => {
              toast({
                title: "Success",
                description: "Report sent successfully",
              });
            }}
          >
            <Button size="sm" variant="default">
              <Mail className="h-4 w-4 mr-2" />
              Email
            </Button>
          </EmailReportDialog>
        </div>
      </div>

      {/* Health Score */}
      <Card className="bg-gradient-to-r from-primary/10 to-primary/5 border-primary/20">
        <CardContent className="p-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-full bg-primary/20">
              <Award className="h-6 w-6 text-primary" />
            </div>
            <div>
              <p className="text-sm text-muted-foreground">
                Financial Health Score
              </p>
              <p className="text-2xl font-bold">{data.health_score || 0}/100</p>
            </div>
          </div>
          <div className="w-1/3">
            <Progress value={data.health_score || 0} className="h-2" />
          </div>
        </CardContent>
      </Card>

      {/* Summary Cards */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        <Card>
          <CardContent className="p-4 flex items-center gap-4">
            <div className="p-3 rounded-full bg-green-500/10">
              <TrendingUp className="h-6 w-6 text-green-500" />
            </div>
            <div>
              <p className="text-sm text-muted-foreground">Total Income</p>
              <p className="text-xl font-bold">
                KES {data.total_income?.toLocaleString() || 0}
              </p>
              <p className="text-xs text-green-500">
                {data.income_change !== undefined && data.income_change !== 0
                  ? `${data.income_change > 0 ? "+" : ""}${data.income_change}% from last month`
                  : "No change"}
              </p>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4 flex items-center gap-4">
            <div className="p-3 rounded-full bg-red-500/10">
              <TrendingDown className="h-6 w-6 text-red-500" />
            </div>
            <div>
              <p className="text-sm text-muted-foreground">Total Expenses</p>
              <p className="text-xl font-bold">
                KES {data.total_expenses?.toLocaleString() || 0}
              </p>
              <p className="text-xs text-red-500">
                {data.expenses_change !== undefined &&
                data.expenses_change !== 0
                  ? `${data.expenses_change > 0 ? "+" : ""}${data.expenses_change}% from last month`
                  : "No change"}
              </p>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4 flex items-center gap-4">
            <div className="p-3 rounded-full bg-blue-500/10">
              <Wallet className="h-6 w-6 text-blue-500" />
            </div>
            <div>
              <p className="text-sm text-muted-foreground">Net Cash Flow</p>
              <p
                className={`text-xl font-bold ${data.net_cash_flow >= 0 ? "text-green-500" : "text-red-500"}`}
              >
                KES {data.net_cash_flow?.toLocaleString() || 0}
              </p>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4 flex items-center gap-4">
            <div className="p-3 rounded-full bg-purple-500/10">
              <Activity className="h-6 w-6 text-purple-500" />
            </div>
            <div>
              <p className="text-sm text-muted-foreground">Avg Balance</p>
              <p className="text-xl font-bold">
                KES {data.average_balance?.toLocaleString() || 0}
              </p>
              <p className="text-xs text-muted-foreground">
                {data.total_transactions} transactions
              </p>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Charts Section */}
      <Tabs defaultValue="overview" className="space-y-4">
        <TabsList className="flex flex-wrap gap-2">
          <TabsTrigger value="overview">Overview</TabsTrigger>
          <TabsTrigger value="categories">Categories</TabsTrigger>
          <TabsTrigger value="trends">Trends</TabsTrigger>
          <TabsTrigger value="radar">Radar</TabsTrigger>
        </TabsList>

        {/* Overview Tab */}
        <TabsContent value="overview">
          <div className="grid gap-4 md:grid-cols-2">
            <Card>
              <CardHeader>
                <CardTitle className="text-sm font-medium">
                  Monthly Income vs Expenses
                </CardTitle>
                <CardDescription>Comparison over time</CardDescription>
              </CardHeader>
              <CardContent className="h-[300px]">
                <ResponsiveContainer width="100%" height="100%">
                  <ComposedChart data={chartData.monthlyData}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="month" />
                    <YAxis />
                    <Tooltip />
                    <Legend />
                    <Bar dataKey="income" fill="#22c55e" name="Income" />
                    <Bar dataKey="expenses" fill="#ef4444" name="Expenses" />
                    <Line
                      type="monotone"
                      dataKey="balance"
                      stroke="#3b82f6"
                      name="Balance"
                    />
                  </ComposedChart>
                </ResponsiveContainer>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle className="text-sm font-medium">
                  Category Breakdown
                </CardTitle>
                <CardDescription>Top spending categories</CardDescription>
              </CardHeader>
              <CardContent className="h-[300px]">
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie
                      data={chartData.categoryData}
                      cx="50%"
                      cy="50%"
                      labelLine={false}
                      label={({ name, percent }) =>
                        `${name} ${(percent * 100).toFixed(0)}%`
                      }
                      outerRadius={80}
                      fill="#8884d8"
                      dataKey="value"
                    >
                      {chartData.categoryData.map(
                        (entry: any, index: number) => (
                          <Cell
                            key={`cell-${index}`}
                            fill={COLORS[index % COLORS.length]}
                          />
                        ),
                      )}
                    </Pie>
                    <Tooltip />
                    <Legend />
                  </PieChart>
                </ResponsiveContainer>
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        {/* Categories Tab */}
        <TabsContent value="categories">
          <div className="grid gap-4 md:grid-cols-2">
            <Card>
              <CardHeader>
                <CardTitle className="text-sm font-medium">
                  Spending by Category
                </CardTitle>
                <CardDescription>Detailed category breakdown</CardDescription>
              </CardHeader>
              <CardContent className="h-[300px]">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={chartData.categoryData} layout="vertical">
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis type="number" />
                    <YAxis type="category" dataKey="name" width={100} />
                    <Tooltip />
                    <Bar dataKey="value" fill="#3b82f6" />
                  </BarChart>
                </ResponsiveContainer>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle className="text-sm font-medium">
                  Top Categories
                </CardTitle>
                <CardDescription>Your top spending areas</CardDescription>
              </CardHeader>
              <CardContent className="space-y-3">
                {chartData.categoryData
                  .slice(0, 5)
                  .map((category: any, index: number) => (
                    <div
                      key={index}
                      className="flex items-center justify-between"
                    >
                      <div className="flex items-center gap-2">
                        <div
                          className="w-3 h-3 rounded-full"
                          style={{
                            backgroundColor: COLORS[index % COLORS.length],
                          }}
                        />
                        <span className="text-sm">{category.name}</span>
                      </div>
                      <div className="flex items-center gap-2">
                        <span className="text-sm font-medium">
                          KES {category.value.toLocaleString()}
                        </span>
                        <span className="text-xs text-muted-foreground">
                          (
                          {data.total_expenses > 0
                            ? (
                                (category.value / data.total_expenses) *
                                100
                              ).toFixed(1)
                            : 0}
                          %)
                        </span>
                      </div>
                    </div>
                  ))}
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        {/* Trends Tab */}
        <TabsContent value="trends">
          <div className="grid gap-4 md:grid-cols-2">
            <Card>
              <CardHeader>
                <CardTitle className="text-sm font-medium">
                  Transaction Trends
                </CardTitle>
                <CardDescription>
                  Daily transaction volume and amounts
                </CardDescription>
              </CardHeader>
              <CardContent className="h-[300px]">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={chartData.trendData}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="date" />
                    <YAxis yAxisId="left" />
                    <YAxis yAxisId="right" orientation="right" />
                    <Tooltip />
                    <Legend />
                    <Line
                      yAxisId="left"
                      type="monotone"
                      dataKey="transactions"
                      stroke="#8884d8"
                      name="Transactions"
                    />
                    <Line
                      yAxisId="right"
                      type="monotone"
                      dataKey="amount"
                      stroke="#82ca9d"
                      name="Total Amount"
                    />
                  </LineChart>
                </ResponsiveContainer>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle className="text-sm font-medium">
                  Monthly Comparison
                </CardTitle>
                <CardDescription>Month-over-month changes</CardDescription>
              </CardHeader>
              <CardContent className="h-[300px]">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={chartData.monthlyData}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="month" />
                    <YAxis />
                    <Tooltip />
                    <Legend />
                    <Bar dataKey="income" fill="#22c55e" name="Income" />
                    <Bar dataKey="expenses" fill="#ef4444" name="Expenses" />
                  </BarChart>
                </ResponsiveContainer>
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        {/* Radar Tab */}
        <TabsContent value="radar">
          <Card>
            <CardHeader>
              <CardTitle className="text-sm font-medium">
                Financial Health Radar
              </CardTitle>
              <CardDescription>
                Visual overview of your financial metrics
              </CardDescription>
            </CardHeader>
            <CardContent className="h-[400px]">
              <ResponsiveContainer width="100%" height="100%">
                <RadarChart cx="50%" cy="50%" outerRadius="80%">
                  <PolarGrid />
                  <PolarAngleAxis dataKey="subject" />
                  <PolarRadiusAxis angle={30} domain={[0, 100]} />
                  <Radar
                    name="Financial Health"
                    dataKey="score"
                    stroke="#3b82f6"
                    fill="#3b82f6"
                    fillOpacity={0.6}
                    data={[
                      {
                        subject: "Income",
                        score: Math.min(
                          100,
                          ((data.total_income || 0) / 150000) * 100,
                        ),
                      },
                      {
                        subject: "Savings",
                        score: Math.min(
                          100,
                          ((data.net_cash_flow || 0) / 50000) * 100,
                        ),
                      },
                      {
                        subject: "Spending",
                        score: Math.max(
                          0,
                          100 - ((data.total_expenses || 0) / 100000) * 100,
                        ),
                      },
                      {
                        subject: "Stability",
                        score: Math.min(
                          100,
                          ((data.average_balance || 0) / 50000) * 100,
                        ),
                      },
                      {
                        subject: "Growth",
                        score: Math.min(100, (data.income_change || 0) + 50),
                      },
                    ]}
                  />
                  <Tooltip />
                  <Legend />
                </RadarChart>
              </ResponsiveContainer>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>

      {/* Insights & Recommendations */}
      <div className="grid gap-4 md:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle className="text-sm font-medium flex items-center gap-2">
              <TrendUp className="h-4 w-4 text-green-500" />
              Key Insights
            </CardTitle>
          </CardHeader>
          <CardContent>
            <ul className="space-y-2">
              {(data.insights || []).map((insight: string, i: number) => (
                <li key={i} className="text-sm flex items-start gap-2">
                  <span className="text-green-500 mt-0.5">•</span>
                  <span>{insight}</span>
                </li>
              ))}
              {(data.insights || []).length === 0 && (
                <p className="text-sm text-muted-foreground">
                  No insights available
                </p>
              )}
            </ul>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-sm font-medium flex items-center gap-2">
              <Award className="h-4 w-4 text-purple-500" />
              Recommendations
            </CardTitle>
          </CardHeader>
          <CardContent>
            <ul className="space-y-2">
              {(data.recommendations || []).map((rec: string, i: number) => (
                <li key={i} className="text-sm flex items-start gap-2">
                  <span className="text-purple-500 mt-0.5">✦</span>
                  <span>{rec}</span>
                </li>
              ))}
              {(data.recommendations || []).length === 0 && (
                <p className="text-sm text-muted-foreground">
                  No recommendations available
                </p>
              )}
            </ul>
          </CardContent>
        </Card>
      </div>

      {/* Transaction Summary */}
      <Card>
        <CardHeader>
          <CardTitle className="text-sm font-medium">
            Transaction Summary
          </CardTitle>
          <CardDescription>Key transaction statistics</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div className="text-center p-3 bg-muted/50 rounded-lg">
              <p className="text-2xl font-bold">
                {data.total_transactions || 0}
              </p>
              <p className="text-xs text-muted-foreground">
                Total Transactions
              </p>
            </div>
            <div className="text-center p-3 bg-green-50 dark:bg-green-950/20 rounded-lg">
              <p className="text-2xl font-bold text-green-500">
                {data.income_count || 0}
              </p>
              <p className="text-xs text-muted-foreground">
                Income Transactions
              </p>
            </div>
            <div className="text-center p-3 bg-red-50 dark:bg-red-950/20 rounded-lg">
              <p className="text-2xl font-bold text-red-500">
                {data.expense_count || 0}
              </p>
              <p className="text-xs text-muted-foreground">
                Expense Transactions
              </p>
            </div>
            <div className="text-center p-3 bg-blue-50 dark:bg-blue-950/20 rounded-lg">
              <p className="text-2xl font-bold text-blue-500">
                KES {data.total_fees?.toLocaleString() || 0}
              </p>
              <p className="text-xs text-muted-foreground">Total Fees</p>
            </div>
          </div>
          <div className="mt-4 grid grid-cols-2 gap-4">
            <div className="text-sm">
              <span className="text-muted-foreground">
                Highest Transaction:
              </span>
              <span className="font-medium ml-2">
                KES {data.highest_transaction?.toLocaleString() || 0}
              </span>
              <span className="text-xs text-muted-foreground ml-2">
                {data.highest_transaction_date
                  ? new Date(data.highest_transaction_date).toLocaleDateString()
                  : ""}
              </span>
            </div>
            <div className="text-sm">
              <span className="text-muted-foreground">Top Category:</span>
              <span className="font-medium ml-2">
                {data.top_category || "N/A"}
              </span>
              <span className="text-xs text-muted-foreground ml-2">
                ({data.top_category_percent || 0}% of expenses)
              </span>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Footer */}
      <Card>
        <CardContent className="p-4 text-center text-sm text-muted-foreground">
          <p>
            Generated by{" "}
            <span className="font-semibold">Pesa Analyzer v1.0</span>
          </p>
          <p>Data processed on {new Date().toLocaleString()}</p>
          <p className="text-xs mt-2">
            For support:{" "}
            <a
              href="mailto:support@pesa-analyzer.com"
              className="text-primary hover:underline"
            >
              support@pesa-analyzer.com
            </a>{" "}
            | Phone: +254 700 000 000
          </p>
          <p className="text-xs text-muted-foreground mt-1">
            © {new Date().getFullYear()} Pesa Analyzer. All rights reserved.
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
