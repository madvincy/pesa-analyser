"use client";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { useToast } from "@/components/ui/use-toast";
import {
  conversionService,
  type SearchResponse,
} from "@/services/conversionService";
import {
  Download,
  FileSpreadsheet,
  FileText,
  Loader2,
  Search,
  X,
} from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

// ─── Types ──────────────────────────────────────────────────────────────────

interface CategoryAggregation {
  name: string;
  count: number;
}

interface MerchantAggregation {
  name: string;
  count: number;
}

interface Transaction {
  receipt: string;
  date: string;
  time: string;
  description: string;
  amount: number;
  balance: number;
  direction: string;
  category: string;
  merchant_name: string;
  fuliza_used: boolean;
  fuliza_amount: number;
  customer_name: string | null;
  status: string;
  transaction_type: string;
}

interface TransactionStats {
  total_transactions: number;
  total_in: number;
  total_out: number;
  net_flow: number;
}

// ─── Component ──────────────────────────────────────────────────────────────

export function SearchResults() {
  const [query, setQuery] = useState<string>("");
  const [results, setResults] = useState<SearchResponse | null>(null);
  const [loading, setLoading] = useState<boolean>(false);
  const [page, setPage] = useState<number>(1);
  const [sortBy, setSortBy] = useState<string>("upload_date");
  const [sortOrder, setSortOrder] = useState<"asc" | "desc">("desc");
  const [selectedTransactions, setSelectedTransactions] = useState<
    Transaction[]
  >([]);
  const [hasSearched, setHasSearched] = useState<boolean>(false);
  const [transactionStats, setTransactionStats] = useState<TransactionStats>({
    total_transactions: 0,
    total_in: 0,
    total_out: 0,
    net_flow: 0,
  });
  const [chartData, setChartData] = useState<any[]>([]);
  const [fileList, setFileList] = useState<string[]>([]);
  const { toast } = useToast();
  const searchIdRef = useRef<number>(0);

  // Flatten all matching transactions from all results
  const getAllMatchingTransactions = useCallback((): Transaction[] => {
    if (!results) return [];
    const allTx: Transaction[] = [];
    for (const result of results.results) {
      if (
        result.matching_transactions &&
        Array.isArray(result.matching_transactions)
      ) {
        allTx.push(...result.matching_transactions);
      }
    }
    return allTx;
  }, [results]);

  // Prepare chart data from transactions
  const prepareChartData = useCallback((transactions: Transaction[]) => {
    if (!transactions || transactions.length === 0) return [];

    // Group by date
    const grouped: {
      [key: string]: { date: string; amount: number; count: number };
    } = {};

    // Get date range to determine grouping
    const dates = transactions.map((t) => t.date).filter((d) => d);
    if (dates.length === 0) return [];

    const sortedDates = [...dates].sort();
    const firstDate = new Date(sortedDates[0]);
    const lastDate = new Date(sortedDates[sortedDates.length - 1]);
    const diffDays = Math.ceil(
      (lastDate.getTime() - firstDate.getTime()) / (1000 * 60 * 60 * 24),
    );

    let groupKey = (date: string) => date;

    // If more than 30 days, group by month
    if (diffDays > 30) {
      groupKey = (date: string) => {
        const d = new Date(date);
        return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
      };
    } else if (diffDays > 7) {
      // If more than 7 days, group by week
      groupKey = (date: string) => {
        const d = new Date(date);
        const weekNum = Math.ceil(d.getDate() / 7);
        return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-W${weekNum}`;
      };
    }

    transactions.forEach((tx) => {
      if (!tx.date) return;
      const key = groupKey(tx.date);
      if (!grouped[key]) {
        grouped[key] = { date: key, amount: 0, count: 0 };
      }
      grouped[key].amount += tx.amount || 0;
      grouped[key].count += 1;
    });

    return Object.values(grouped).sort((a, b) => a.date.localeCompare(b.date));
  }, []);

  const handleSearch = useCallback(
    async (newPage: number = 1, newQuery?: string) => {
      const searchQuery = newQuery !== undefined ? newQuery : query;

      if (!searchQuery.trim()) {
        toast({
          title: "Info",
          description: "Please enter a search query",
        });
        return;
      }

      const currentSearchId = ++searchIdRef.current;

      setLoading(true);
      setPage(newPage);
      if (newPage === 1) {
        setResults(null);
        setSelectedTransactions([]);
        setFileList([]);
      }

      try {
        const response = await conversionService.searchTransactions({
          query: searchQuery,
          page: newPage,
          size: 20,
          sort_by: sortBy,
          sort_order: sortOrder,
        });

        if (currentSearchId === searchIdRef.current) {
          setResults(response);
          setHasSearched(true);

          // Auto-select all matching transactions
          if (response.results) {
            const allTx: Transaction[] = [];
            const files: string[] = [];

            for (const result of response.results) {
              if (result.file_name) {
                files.push(result.file_name);
              }
              if (
                result.matching_transactions &&
                Array.isArray(result.matching_transactions)
              ) {
                allTx.push(...result.matching_transactions);
              }
            }

            setSelectedTransactions(allTx);
            setFileList(files);

            // Set transaction stats from response
            if (response.transaction_stats) {
              setTransactionStats(response.transaction_stats);
            }

            // Prepare chart data
            const chartData = prepareChartData(allTx);
            setChartData(chartData);
          }
        }
      } catch (error: unknown) {
        if (currentSearchId === searchIdRef.current) {
          console.error("Search failed:", error);
          const errorMessage =
            error instanceof Error ? error.message : "Failed to search";
          toast({
            title: "Error",
            description: errorMessage,
            variant: "destructive",
          });
          setResults(null);
          setSelectedTransactions([]);
          setFileList([]);
        }
      } finally {
        if (currentSearchId === searchIdRef.current) {
          setLoading(false);
        }
      }
    },
    [query, sortBy, sortOrder, toast, prepareChartData],
  );

  // Auto-search when sort changes
  useEffect(() => {
    if (hasSearched && query.trim()) {
      handleSearch(1);
    }
  }, [sortBy, sortOrder, hasSearched, query, handleSearch]);

  const generatePDFContent = (transactions: Transaction[]) => {
    const headers = [
      "Receipt",
      "Date",
      "Time",
      "Description",
      "Amount",
      "Balance",
      "Direction",
      "Category",
      "Merchant",
      "Fuliza Used",
      "Fuliza Amount",
      "Customer",
      "Status",
      "Type",
    ];

    // Build HTML content for PDF
    let html = `
      <html>
      <head>
        <meta charset="UTF-8">
        <style>
          body { font-family: Arial, sans-serif; padding: 20px; }
          h1 { color: #1a1a2e; border-bottom: 2px solid #e2e8f0; padding-bottom: 10px; }
          h2 { color: #1a1a2e; margin-top: 20px; }
          .summary { display: flex; gap: 20px; margin: 20px 0; flex-wrap: wrap; }
          .summary-card { 
            background: #f8fafc; 
            padding: 15px 20px; 
            border-radius: 8px; 
            border: 1px solid #e2e8f0;
            min-width: 150px;
          }
          .summary-card .label { font-size: 12px; color: #64748b; }
          .summary-card .value { font-size: 18px; font-weight: bold; color: #1a1a2e; }
          .summary-card .value.green { color: #22c55e; }
          .summary-card .value.red { color: #ef4444; }
          table { 
            width: 100%; 
            border-collapse: collapse; 
            margin: 20px 0;
            font-size: 11px;
          }
          th { 
            background: #1a1a2e; 
            color: white; 
            padding: 8px; 
            text-align: left;
            border: 1px solid #1a1a2e;
          }
          td { 
            padding: 6px 8px; 
            border: 1px solid #e2e8f0;
          }
          tr:nth-child(even) { background: #f8fafc; }
          .footer { 
            margin-top: 30px; 
            padding-top: 20px;
            border-top: 1px solid #e2e8f0;
            font-size: 12px;
            color: #64748b;
            text-align: center;
          }
          .files-list {
            display: flex;
            flex-wrap: wrap;
            gap: 8px;
            margin: 10px 0;
          }
          .file-badge {
            background: #e2e8f0;
            padding: 4px 12px;
            border-radius: 12px;
            font-size: 12px;
          }
          .chart-placeholder {
            background: #f8fafc;
            padding: 20px;
            border-radius: 8px;
            border: 1px solid #e2e8f0;
            margin: 20px 0;
            text-align: center;
          }
        </style>
      </head>
      <body>
        <h1>📊 Transactions Report</h1>
        <p><strong>Generated:</strong> ${new Date().toLocaleString()}</p>
        <p><strong>Search Query:</strong> "${query}"</p>
    `;

    // Summary Section
    html += `
      <h2>📈 Summary</h2>
      <div class="summary">
        <div class="summary-card">
          <div class="label">Total Transactions</div>
          <div class="value">${transactionStats.total_transactions}</div>
        </div>
        <div class="summary-card">
          <div class="label">Total In</div>
          <div class="value green">KES ${transactionStats.total_in.toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2})}</div>
        </div>
        <div class="summary-card">
          <div class="label">Total Out</div>
          <div class="value red">KES ${transactionStats.total_out.toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2})}</div>
        </div>
        <div class="summary-card">
          <div class="label">Net Flow</div>
          <div class="value ${transactionStats.net_flow >= 0 ? 'green' : 'red'}">KES ${transactionStats.net_flow.toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2})}</div>
        </div>
      </div>
    `;

    // Files Section
    if (fileList.length > 0) {
      html += `
        <h2>📁 Files Retrieved (${fileList.length})</h2>
        <div class="files-list">
          ${fileList.map(file => `<span class="file-badge">${file}</span>`).join('')}
        </div>
      `;
    }

    // Chart Section
    if (chartData.length > 0) {
      html += `
        <h2>📊 Transaction Timeline</h2>
        <div class="chart-placeholder">
          <p><strong>Transaction Amounts Over Time</strong></p>
          <table style="margin: 10px auto; width: auto;">
            <thead>
              <tr>
                <th>Period</th>
                <th>Amount (KES)</th>
                <th>Count</th>
              </tr>
            </thead>
            <tbody>
              ${chartData.map(item => `
                <tr>
                  <td>${item.date}</td>
                  <td>${item.amount.toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2})}</td>
                  <td>${item.count}</td>
                </tr>
              `).join('')}
            </tbody>
          </table>
        </div>
      `;
    }

    // Transactions Table
    html += `
      <h2>📋 Transactions (${transactions.length})</h2>
      <table>
        <thead>
          <tr>
            ${headers.map(h => `<th>${h}</th>`).join('')}
          </tr>
        </thead>
        <tbody>
          ${transactions.map(tx => `
            <tr>
              <td>${tx.receipt || ''}</td>
              <td>${tx.date || ''}</td>
              <td>${tx.time || ''}</td>
              <td>${(tx.description || '').substring(0, 50)}${(tx.description || '').length > 50 ? '...' : ''}</td>
              <td>${(tx.amount || 0).toFixed(2)}</td>
              <td>${(tx.balance || 0).toFixed(2)}</td>
              <td>${tx.direction || ''}</td>
              <td>${tx.category || ''}</td>
              <td>${(tx.merchant_name || '').substring(0, 30)}${(tx.merchant_name || '').length > 30 ? '...' : ''}</td>
              <td>${tx.fuliza_used ? 'Yes' : 'No'}</td>
              <td>${(tx.fuliza_amount || 0).toFixed(2)}</td>
              <td>${tx.customer_name || 'N/A'}</td>
              <td>${tx.status || ''}</td>
              <td>${tx.transaction_type || ''}</td>
            </tr>
          `).join('')}
        </tbody>
      </table>
    `;

    // Footer
    html += `
        <div class="footer">
          <p>Generated by Pesa Analyzer | support@pesa-analyzer.com</p>
          <p>${new Date().toLocaleString()}</p>
        </div>
      </body>
      </html>
    `;

    return html;
  };

  const handleExportTransactions = async (format: "csv" | "excel" | "pdf") => {
    const transactions = getAllMatchingTransactions();

    if (transactions.length === 0) {
      toast({
        title: "Info",
        description: "No transactions to export",
      });
      return;
    }

    try {
      let content: string | Blob;
      let mimeType: string;
      let extension: string;

      if (format === "pdf") {
        // Generate PDF with proper HTML content
        const htmlContent = generatePDFContent(transactions);
        
        // Create a Blob with HTML content
        const blob = new Blob([htmlContent], { 
          type: "application/pdf" 
        });
        
        // For PDF, we need to use a different approach - create a proper PDF
        // Using a simple approach with HTML to PDF conversion
        // Since we can't use external libraries, we'll use the HTML content
        // and let the browser handle it with print-to-PDF
        const win = window.open('', '_blank');
        if (win) {
          win.document.write(htmlContent);
          win.document.close();
          win.print();
          return;
        }
        
        // Fallback: download as HTML that can be converted to PDF
        const htmlBlob = new Blob([htmlContent], { type: 'text/html' });
        const url = window.URL.createObjectURL(htmlBlob);
        const a = document.createElement("a");
        a.href = url;
        a.download = `transactions_report.html`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        window.URL.revokeObjectURL(url);
        
        toast({
          title: "Success",
          description: "HTML report generated. Use 'Save as PDF' in your browser.",
        });
        return;
      } else {
        // CSV and Excel formats
        const headers = [
          "Receipt",
          "Date",
          "Time",
          "Description",
          "Amount",
          "Balance",
          "Direction",
          "Category",
          "Merchant",
          "Fuliza Used",
          "Fuliza Amount",
          "Customer",
          "Status",
          "Type",
        ];

        const rows = transactions.map((tx) => [
          tx.receipt || "",
          tx.date || "",
          tx.time || "",
          tx.description || "",
          (tx.amount || 0).toFixed(2),
          (tx.balance || 0).toFixed(2),
          tx.direction || "",
          tx.category || "",
          tx.merchant_name || "",
          tx.fuliza_used ? "Yes" : "No",
          (tx.fuliza_amount || 0).toFixed(2),
          tx.customer_name || "N/A",
          tx.status || "",
          tx.transaction_type || "",
        ]);

        if (format === "csv") {
          content = [headers.join(","), ...rows.map((row) => row.join(","))].join(
            "\n",
          );
          mimeType = "text/csv";
          extension = "csv";
        } else {
          // Excel format - HTML table
          const tableHtml = `
            <html xmlns:o="urn:schemas-microsoft-com:office:office" 
                  xmlns:x="urn:schemas-microsoft-com:office:excel" 
                  xmlns="http://www.w3.org/TR/REC-html40">
            <head><meta charset="UTF-8">
            <!--[if gte mso 9]>
            <xml>
            <x:ExcelWorkbook>
            <x:ExcelWorksheets>
            <x:ExcelWorksheet>
            <x:Name>Transactions</x:Name>
            <x:WorksheetOptions>
            <x:DisplayGridlines/>
            </x:WorksheetOptions>
            </x:ExcelWorksheet>
            </x:ExcelWorksheets>
            </x:ExcelWorkbook>
            </xml>
            <![endif]-->
            </head>
            <body>
            <table>
            <thead>
            <tr>${headers.map((h) => `<th>${h}</th>`).join("")}</tr>
            </thead>
            <tbody>
            ${rows
              .map(
                (row) =>
                  `<tr>${row.map((cell) => `<td>${cell}</td>`).join("")}</tr>`,
              )
              .join("")}
            </tbody>
            </table>
            </body>
            </html>
          `;
          content = tableHtml;
          mimeType =
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet";
          extension = "xlsx";
        }

        // Create download for CSV/Excel
        const blob = new Blob([content], { type: mimeType });
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = `transactions_report.${extension}`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        window.URL.revokeObjectURL(url);
      }

      toast({
        title: "Success",
        description: `Exported ${transactions.length} transactions (${format.toUpperCase()})`,
      });
    } catch (error: unknown) {
      console.error("Export failed:", error);
      const errorMessage =
        error instanceof Error ? error.message : "Failed to export";
      toast({
        title: "Error",
        description: errorMessage,
        variant: "destructive",
      });
    }
  };

  const toggleSort = (field: string) => {
    if (sortBy === field) {
      setSortOrder(sortOrder === "asc" ? "desc" : "asc");
    } else {
      setSortBy(field);
      setSortOrder("asc");
    }
  };

  const formatDate = (dateStr: string) => {
    if (!dateStr) return "";
    try {
      const date = new Date(dateStr);
      return date.toLocaleDateString() + " " + date.toLocaleTimeString();
    } catch {
      return dateStr;
    }
  };

  const formatCurrency = (amount: number | undefined | null) => {
    if (amount === undefined || amount === null || isNaN(amount)) {
      return "KES 0.00";
    }
    return `KES ${amount.toLocaleString(undefined, {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    })}`;
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter") {
      handleSearch(1);
    }
  };

  const clearSearch = () => {
    setQuery("");
    setResults(null);
    setHasSearched(false);
    setSelectedTransactions([]);
    setFileList([]);
    setChartData([]);
    setTransactionStats({
      total_transactions: 0,
      total_in: 0,
      total_out: 0,
      net_flow: 0,
    });
    searchIdRef.current = 0;
  };

  const matchingTransactions = getAllMatchingTransactions();

  return (
    <div className="space-y-4">
      {/* Search Bar */}
      <Card>
        <CardContent className="p-4">
          <div className="flex gap-4">
            <div className="flex-1 relative">
              <Input
                placeholder="Search by merchant, category, description..."
                value={query}
                onChange={(e: React.ChangeEvent<HTMLInputElement>) =>
                  setQuery(e.target.value)
                }
                onKeyDown={handleKeyDown}
                className="w-full pr-8"
              />
              {query && (
                <Button
                  variant="ghost"
                  size="icon"
                  className="absolute right-1 top-1/2 -translate-y-1/2 h-7 w-7"
                  onClick={clearSearch}
                  type="button"
                >
                  <X className="h-4 w-4" />
                </Button>
              )}
            </div>
            <Button onClick={() => handleSearch(1)} disabled={loading}>
              {loading ? (
                <Loader2 className="h-4 w-4 mr-2 animate-spin" />
              ) : (
                <Search className="h-4 w-4 mr-2" />
              )}
              Search
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Stats Summary - Updated */}
      {results && matchingTransactions.length > 0 && (
        <div className="grid gap-4 md:grid-cols-4">
          <Card>
            <CardContent className="p-4">
              <p className="text-sm text-muted-foreground">
                Total Transactions
              </p>
              <p className="text-xl font-bold text-primary">
                {transactionStats.total_transactions}
              </p>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="p-4">
              <p className="text-sm text-muted-foreground">Total In</p>
              <p className="text-xl font-bold text-green-600">
                {formatCurrency(transactionStats.total_in)}
              </p>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="p-4">
              <p className="text-sm text-muted-foreground">Total Out</p>
              <p className="text-xl font-bold text-red-600">
                {formatCurrency(transactionStats.total_out)}
              </p>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="p-4">
              <p className="text-sm text-muted-foreground">Net Flow</p>
              <p
                className={`text-xl font-bold ${
                  (transactionStats.net_flow || 0) >= 0
                    ? "text-green-600"
                    : "text-red-600"
                }`}
              >
                {formatCurrency(transactionStats.net_flow)}
              </p>
            </CardContent>
          </Card>
        </div>
      )}

      {/* Chart Section */}
      {chartData.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-sm font-medium">
              Transaction Timeline
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="h-[300px] w-full">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={chartData}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="date" />
                  <YAxis />
                  <Tooltip
                    formatter={(value: any) => formatCurrency(value)}
                    labelFormatter={(label: any) => `Date: ${label}`}
                  />
                  <Legend />
                  <Bar dataKey="amount" fill="#8884d8" name="Amount (KES)" />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Files List */}
      {fileList.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-sm font-medium">
              Files Retrieved ({fileList.length})
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex flex-wrap gap-2">
              {fileList.map((file, index) => (
                <Badge key={index} variant="outline" className="text-xs">
                  {file}
                </Badge>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Matching Transactions Table */}
      <Card>
        <CardHeader>
          <div className="flex flex-wrap justify-between items-center gap-2">
            <CardTitle className="text-sm font-medium">
              {loading
                ? "Searching..."
                : matchingTransactions.length > 0
                  ? `${matchingTransactions.length} matching transaction(s) found`
                  : hasSearched
                    ? "No matching transactions found"
                    : "Search for transactions"}
            </CardTitle>
            {matchingTransactions.length > 0 && (
              <div className="flex gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => handleExportTransactions("csv")}
                >
                  <FileText className="h-4 w-4 mr-1" />
                  CSV
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => handleExportTransactions("excel")}
                >
                  <FileSpreadsheet className="h-4 w-4 mr-1" />
                  Excel
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => handleExportTransactions("pdf")}
                >
                  <FileText className="h-4 w-4 mr-1" />
                  PDF
                </Button>
              </div>
            )}
          </div>
        </CardHeader>
        <CardContent>
          {loading ? (
            <div className="flex flex-col items-center justify-center py-8 gap-2">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
              <p className="text-sm text-muted-foreground">
                Searching for transactions...
              </p>
            </div>
          ) : matchingTransactions.length === 0 ? (
            <div className="text-center py-8 text-muted-foreground">
              {hasSearched ? (
                <>
                  <Search className="h-12 w-12 mx-auto opacity-50 mb-2" />
                  <p>No transactions found matching your search</p>
                  <p className="text-sm">Try adjusting your search terms</p>
                </>
              ) : (
                <>
                  <Search className="h-12 w-12 mx-auto opacity-50 mb-2" />
                  <p>Enter a search query to find transactions</p>
                </>
              )}
            </div>
          ) : (
            <>
              <div className="rounded-md border overflow-x-auto">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Date</TableHead>
                      <TableHead>Time</TableHead>
                      <TableHead>Description</TableHead>
                      <TableHead>Amount</TableHead>
                      <TableHead>Type</TableHead>
                      <TableHead>Category</TableHead>
                      <TableHead>Merchant</TableHead>
                      <TableHead>Receipt</TableHead>
                      <TableHead>Status</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {matchingTransactions.map(
                      (tx: Transaction, index: number) => (
                        <TableRow key={tx.receipt || index}>
                          <TableCell>{tx.date || "N/A"}</TableCell>
                          <TableCell>{tx.time || "N/A"}</TableCell>
                          <TableCell className="max-w-xs truncate">
                            {tx.description || "N/A"}
                          </TableCell>
                          <TableCell
                            className={
                              tx.direction === "in"
                                ? "text-green-600 font-medium"
                                : tx.direction === "out"
                                  ? "text-red-600 font-medium"
                                  : "text-gray-600"
                            }
                          >
                            {formatCurrency(tx.amount)}
                          </TableCell>
                          <TableCell>
                            <Badge
                              variant={
                                tx.direction === "in"
                                  ? "default"
                                  : "destructive"
                              }
                              className="text-xs"
                            >
                              {tx.transaction_type || tx.direction || "Unknown"}
                            </Badge>
                          </TableCell>
                          <TableCell>
                            <Badge variant="outline" className="text-xs">
                              {tx.category || "Other"}
                            </Badge>
                          </TableCell>
                          <TableCell className="max-w-xs truncate">
                            {tx.merchant_name || "N/A"}
                          </TableCell>
                          <TableCell className="font-mono text-xs">
                            {tx.receipt || "N/A"}
                          </TableCell>
                          <TableCell>
                            <Badge
                              variant={
                                tx.status === "Completed"
                                  ? "default"
                                  : tx.status === "Failed"
                                    ? "destructive"
                                    : "outline"
                              }
                              className="text-xs"
                            >
                              {tx.status || "Unknown"}
                            </Badge>
                          </TableCell>
                        </TableRow>
                      ),
                    )}
                  </TableBody>
                </Table>
              </div>

              {/* Export Summary */}
              <div className="flex justify-between items-center mt-4 text-sm text-muted-foreground">
                <span>
                  Showing {matchingTransactions.length} transaction(s)
                </span>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => handleExportTransactions("csv")}
                >
                  <Download className="h-4 w-4 mr-1" />
                  Export All
                </Button>
              </div>
            </>
          )}
        </CardContent>
      </Card>
    </div>
  );
}