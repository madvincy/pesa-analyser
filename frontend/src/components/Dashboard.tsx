// src/components/Dashboard.tsx
"use client";

import {
  Activity,
  AlertCircle,
  Award,
  Download,
  FileText,
  Mail,
  TrendingDown,
  TrendingUp,
  TrendingUp as TrendUp,
  Wallet,
} from "lucide-react";
import { useEffect, useRef, useState } from "react";
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
import { Button } from "./ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "./ui/card";
import { Progress } from "./ui/progress";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "./ui/tabs";
import { useToast } from "./ui/use-toast";

interface DashboardProps {
  analysisId: string;
}

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

export function Dashboard({ analysisId }: DashboardProps) {
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [progress, setProgress] = useState(0);
  const [exporting, setExporting] = useState(false);
  const [emailSending, setEmailSending] = useState(false);
  const { toast } = useToast();
  const wsRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    fetchAnalysisData();
    setupWebSocket();
    return () => {
      if (wsRef.current) {
        wsRef.current.close();
      }
    };
  }, [analysisId]);

  const setupWebSocket = () => {
    const wsUrl = `ws://localhost:8000/api/v1/results/ws/${analysisId}`;
    const ws = new WebSocket(wsUrl);
    wsRef.current = ws;

    ws.onmessage = (event) => {
      const message = JSON.parse(event.data);
      if (message.status === "completed" || message.status === "failed") {
        fetchAnalysisData();
      }
      if (message.progress !== undefined) {
        setProgress(message.progress);
      }
    };

    ws.onerror = (error) => {
      console.error("WebSocket error:", error);
    };
  };

  const fetchAnalysisData = async () => {
    try {
      const response = await fetch(`/api/v1/results/${analysisId}`);
      const result = await response.json();
      setData(result);
      setProgress(100);
    } catch (error) {
      console.error("Failed to fetch analysis:", error);
      toast({
        title: "Error",
        description: "Failed to load analysis data",
        variant: "destructive",
      });
    } finally {
      setLoading(false);
    }
  };

  const handleExportPDF = async () => {
    setExporting(true);
    try {
      const response = await fetch(
        `/api/v1/reports/report/${analysisId}?format=pdf`,
      );
      if (!response.ok) throw new Error("Export failed");

      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `financial_report_${analysisId}.pdf`;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);

      toast({
        title: "Success",
        description: "PDF report downloaded successfully",
      });
    } catch (error) {
      toast({
        title: "Export Failed",
        description: "Failed to export PDF report",
        variant: "destructive",
      });
    } finally {
      setExporting(false);
    }
  };

  const handleExportCSV = async () => {
    setExporting(true);
    try {
      const response = await fetch(
        `/api/v1/reports/report/${analysisId}?format=csv`,
      );
      if (!response.ok) throw new Error("Export failed");

      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `financial_data_${analysisId}.csv`;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);

      toast({
        title: "Success",
        description: "CSV data exported successfully",
      });
    } catch (error) {
      toast({
        title: "Export Failed",
        description: "Failed to export CSV data",
        variant: "destructive",
      });
    } finally {
      setExporting(false);
    }
  };

  const handleEmailReport = async () => {
    const email = prompt("Enter your email address:");
    if (!email) return;

    setEmailSending(true);
    try {
      const response = await fetch("/api/v1/reports/report/email", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, analysis_id: analysisId }),
      });

      if (!response.ok) throw new Error("Failed to send email");

      toast({
        title: "Success",
        description: `Report sent to ${email}`,
      });
    } catch (error) {
      toast({
        title: "Email Failed",
        description: "Failed to send report via email",
        variant: "destructive",
      });
    } finally {
      setEmailSending(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-96">
        <div className="text-center space-y-4">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary mx-auto"></div>
          <p className="text-muted-foreground">Analyzing your statement...</p>
          <Progress value={progress} className="w-64 mx-auto" />
          <p className="text-xs text-muted-foreground">
            This may take a few moments
          </p>
        </div>
      </div>
    );
  }

  if (!data) {
    return (
      <Card>
        <CardContent className="py-12">
          <div className="text-center text-muted-foreground">
            <AlertCircle className="w-12 h-12 mx-auto mb-3" />
            <p>No analysis data available. Please upload a statement.</p>
          </div>
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header with Export Buttons */}
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h2 className="text-2xl font-bold font-playfair">
            Financial Analysis Report
          </h2>
          <p className="text-sm text-muted-foreground">
            {data.file_name} • Generated{" "}
            {new Date(
              data.completed_at || data.created_at,
            ).toLocaleDateString()}
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={handleExportPDF}
            disabled={exporting}
          >
            <FileText className="h-4 w-4 mr-2" />
            {exporting ? "Exporting..." : "PDF"}
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={handleExportCSV}
            disabled={exporting}
          >
            <Download className="h-4 w-4 mr-2" />
            {exporting ? "Exporting..." : "CSV"}
          </Button>
          <Button size="sm" onClick={handleEmailReport} disabled={emailSending}>
            <Mail className="h-4 w-4 mr-2" />
            {emailSending ? "Sending..." : "Email"}
          </Button>
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
                KES {data.totalIncome?.toLocaleString() || 0}
              </p>
              <p className="text-xs text-green-500">
                +{data.incomeChange || 0}% from last month
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
                KES {data.totalExpenses?.toLocaleString() || 0}
              </p>
              <p className="text-xs text-red-500">
                +{data.expensesChange || 0}% from last month
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
                className={`text-xl font-bold ${data.netCashFlow >= 0 ? "text-green-500" : "text-red-500"}`}
              >
                KES {data.netCashFlow?.toLocaleString() || 0}
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
                KES {data.averageBalance?.toLocaleString() || 0}
              </p>
              <p className="text-xs text-muted-foreground">
                {data.totalTransactions} transactions
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
                  <ComposedChart data={data.monthlyData || []}>
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
                      data={data.categoryData || []}
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
                      {(data.categoryData || []).map(
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
                  <BarChart data={data.categoryData || []} layout="vertical">
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
                {(data.categoryData || [])
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
                          {(
                            (category.value / data.totalExpenses) *
                            100
                          ).toFixed(1)}
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
                  <LineChart data={data.trendData || []}>
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
                  <BarChart data={data.monthlyData || []}>
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
                        score: Math.min(100, (data.totalIncome / 150000) * 100),
                      },
                      {
                        subject: "Savings",
                        score: Math.min(100, (data.netCashFlow / 50000) * 100),
                      },
                      {
                        subject: "Spending",
                        score: Math.max(
                          0,
                          100 - (data.totalExpenses / 100000) * 100,
                        ),
                      },
                      {
                        subject: "Stability",
                        score: Math.min(
                          100,
                          (data.averageBalance / 50000) * 100,
                        ),
                      },
                      {
                        subject: "Growth",
                        score: Math.min(100, data.incomeChange + 50),
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
                {data.totalTransactions || 0}
              </p>
              <p className="text-xs text-muted-foreground">
                Total Transactions
              </p>
            </div>
            <div className="text-center p-3 bg-green-50 dark:bg-green-950/20 rounded-lg">
              <p className="text-2xl font-bold text-green-500">
                {data.incomeCount || 0}
              </p>
              <p className="text-xs text-muted-foreground">
                Income Transactions
              </p>
            </div>
            <div className="text-center p-3 bg-red-50 dark:bg-red-950/20 rounded-lg">
              <p className="text-2xl font-bold text-red-500">
                {data.expenseCount || 0}
              </p>
              <p className="text-xs text-muted-foreground">
                Expense Transactions
              </p>
            </div>
            <div className="text-center p-3 bg-blue-50 dark:bg-blue-950/20 rounded-lg">
              <p className="text-2xl font-bold text-blue-500">
                KES {data.totalFees?.toLocaleString() || 0}
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
                KES {data.highestTransaction?.toLocaleString() || 0}
              </span>
              <span className="text-xs text-muted-foreground ml-2">
                {data.highestTransactionDate
                  ? new Date(data.highestTransactionDate).toLocaleDateString()
                  : ""}
              </span>
            </div>
            <div className="text-sm">
              <span className="text-muted-foreground">Top Category:</span>
              <span className="font-medium ml-2">
                {data.topCategory || "N/A"}
              </span>
              <span className="text-xs text-muted-foreground ml-2">
                ({data.topCategoryPercent || 0}% of expenses)
              </span>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
