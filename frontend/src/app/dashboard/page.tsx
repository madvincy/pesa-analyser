"use client";

import { FileUploadZone } from "@/components/converter/FileUploadZone";
import { SearchResults } from "@/components/converter/SearchResults";
import { Dashboard as DashboardComponent } from "@/components/Dashboard";
import { Footer } from "@/components/Footer";
import { Navigation } from "@/components/Navigation";
import TopCounterpartiesTable from "@/components/TopCounterpartiesTable";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import {
  Pagination,
  PaginationContent,
  PaginationEllipsis,
  PaginationItem,
  PaginationLink,
  PaginationNext,
  PaginationPrevious,
} from "@/components/ui/pagination";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { toast } from "@/components/ui/use-toast";
import { UploadZone } from "@/components/UploadZone";
import { useDeleteUserData, useExportUserData } from "@/hooks/api/useUser";
import { useHistoryData } from "@/hooks/useHistoryData";
import { getErrorMessage } from "@/lib/error.utils";
import {
  AlertTriangle,
  BarChart3,
  Clock,
  CreditCard,
  Download,
  Eye,
  FileText,
  Loader2,
  Search,
  Trash2,
  TrendingUp,
  Upload,
  User,
  Wallet,
} from "lucide-react";
import { useSession } from "next-auth/react";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";

export default function DashboardPage() {
  const { data: session, status } = useSession();
  const router = useRouter();
  const [analysisId, setAnalysisId] = useState<string | null>(null);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [isConverting, setIsConverting] = useState(false);
  const [conversionProgress, setConversionProgress] = useState(0);

  // ─── History Data ──────────────────────────────────────────────────────
  const {
    history,
    loading: historyLoading,
    refetch,
  } = useHistoryData({
    type: "all",
    limit: 10,
  });

  const analyses = history.analyses || [];
  const pagination = history.pagination || {
    page: 1,
    limit: 10,
    total: 0,
    pages: 0,
  };
  const [latestAnalysisResult, setLatestAnalysisResult] = useState<any | null>(
    null,
  );
  const [latestLoading, setLatestLoading] = useState(false);

  const hasCompletedAnalysis = analyses.some(
    (analysis: any) => analysis?.status === "completed",
  );

  const { mutate: deleteData, loading: deleting } = useDeleteUserData();
  const { loading: exporting, mutate: exportDataFn } = useExportUserData();
  const [searchQuery, setSearchQuery] = useState("");
  const [currentPage, setCurrentPage] = useState(1);
  const [itemsPerPage] = useState(10);

  // ─── Fetch latest analysis ────────────────────────────────────────────
  useEffect(() => {
    const fetchLatest = async () => {
      if (!analyses || analyses.length === 0) return;
      const latest = analyses[0];
      if (!latest || latest.status !== "completed") return;
      setLatestLoading(true);
      try {
        const res = await fetch(`/api/results/${latest.id}`, {
          credentials: "include",
        });
        if (!res.ok) {
          setLatestAnalysisResult(null);
          setLatestLoading(false);
          return;
        }
        const json = await res.json();
        setLatestAnalysisResult(json);
      } catch (e) {
        console.error("Failed to fetch latest analysis result", e);
        setLatestAnalysisResult(null);
      } finally {
        setLatestLoading(false);
      }
    };

    fetchLatest();
  }, [analyses]);

  useEffect(() => {
    if (status === "unauthenticated") {
      router.push("/auth/signin");
      return;
    }
  }, [status, router]);

  // ─── Filter Analyses ──────────────────────────────────────────────────
  const filteredAnalyses = useMemo(() => {
    const q = searchQuery.trim().toLowerCase();
    if (!q) return analyses;
    return analyses.filter((a: any) => {
      const fileName = (a.file_name || a.fileName || "").toLowerCase();
      const status = (a.status || "").toLowerCase();
      return fileName.includes(q) || status.includes(q);
    });
  }, [analyses, searchQuery]);

  const totalPages =
    pagination.pages || Math.ceil(pagination.total / itemsPerPage);

  // ─── Handle Page Change ──────────────────────────────────────────────
  const handlePageChange = (page: number) => {
    setCurrentPage(page);
    refetch();
  };

  const handleExport = async () => {
    try {
      const result = await exportDataFn();
      if (result?.error) {
        toast.error(getErrorMessage(result.error));
        return;
      }
      if (result?.data) {
        const blob = new Blob([JSON.stringify(result.data, null, 2)], {
          type: "application/json",
        });
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = `pesa_analyser_export_${new Date().toISOString().split("T")[0]}.json`;
        a.click();
        URL.revokeObjectURL(url);
        toast.success("Your data has been exported successfully!");
      } else {
        toast.error("No data available to export");
      }
    } catch (error) {
      console.error("Export error:", error);
      toast.error("Failed to export data. Please try again.");
    }
  };

  const handleDeleteData = async () => {
    try {
      const result = await deleteData();
      if (result?.error) {
        toast.error(getErrorMessage(result.error));
        return;
      }
      toast.success(
        result?.data?.message || "All your data has been deleted successfully!",
      );
      setDeleteDialogOpen(false);
      refetch();
    } catch (error) {
      console.error("Delete error:", error);
      toast.error("Failed to delete data. Please try again.");
    }
  };

  const handleConvert = async (format: string) => {
    setIsConverting(true);
    setConversionProgress(0);
    const interval = setInterval(() => {
      setConversionProgress((prev) => {
        if (prev >= 90) {
          clearInterval(interval);
          return 90;
        }
        return prev + 10;
      });
    }, 500);

    setTimeout(() => {
      clearInterval(interval);
      setConversionProgress(100);
      setIsConverting(false);
      toast.success(
        `Conversion completed! File downloaded as ${format.toUpperCase()}`,
      );
    }, 3000);
  };

  const handleViewAnalysis = (analysis: any) => {
    if (analysis?.id) {
      router.push(`/analytics/${analysis.id}`);
    }
  };

  // ─── Render Pagination ──────────────────────────────────────────────────
  const renderPagination = () => {
    if (totalPages <= 1) return null;

    const items = [];
    const maxVisible = 5;
    let startPage = Math.max(1, currentPage - Math.floor(maxVisible / 2));
    let endPage = Math.min(totalPages, startPage + maxVisible - 1);

    if (endPage - startPage + 1 < maxVisible) {
      startPage = Math.max(1, endPage - maxVisible + 1);
    }

    items.push(
      <PaginationItem key="prev">
        <PaginationPrevious
          onClick={() => handlePageChange(Math.max(1, currentPage - 1))}
          className={
            currentPage === 1
              ? "pointer-events-none opacity-50"
              : "cursor-pointer"
          }
        />
      </PaginationItem>,
    );

    if (startPage > 1) {
      items.push(
        <PaginationItem key="1">
          <PaginationLink onClick={() => handlePageChange(1)}>1</PaginationLink>
        </PaginationItem>,
      );
      if (startPage > 2) {
        items.push(
          <PaginationItem key="ellipsis1">
            <PaginationEllipsis />
          </PaginationItem>,
        );
      }
    }

    for (let i = startPage; i <= endPage; i++) {
      items.push(
        <PaginationItem key={i}>
          <PaginationLink
            isActive={i === currentPage}
            onClick={() => handlePageChange(i)}
          >
            {i}
          </PaginationLink>
        </PaginationItem>,
      );
    }

    if (endPage < totalPages) {
      if (endPage < totalPages - 1) {
        items.push(
          <PaginationItem key="ellipsis2">
            <PaginationEllipsis />
          </PaginationItem>,
        );
      }
      items.push(
        <PaginationItem key={totalPages}>
          <PaginationLink onClick={() => handlePageChange(totalPages)}>
            {totalPages}
          </PaginationLink>
        </PaginationItem>,
      );
    }

    items.push(
      <PaginationItem key="next">
        <PaginationNext
          onClick={() =>
            handlePageChange(Math.min(totalPages, currentPage + 1))
          }
          className={
            currentPage === totalPages
              ? "pointer-events-none opacity-50"
              : "cursor-pointer"
          }
        />
      </PaginationItem>,
    );

    return (
      <Pagination>
        <PaginationContent>{items}</PaginationContent>
      </Pagination>
    );
  };

  // ─── Render Status Badge ───────────────────────────────────────────────
  const renderStatusBadge = (status: string) => {
    const variants: Record<string, string> = {
      completed: "bg-green-500/10 text-green-600 border-green-500/20",
      processing: "bg-blue-500/10 text-blue-600 border-blue-500/20",
      pending: "bg-yellow-500/10 text-yellow-600 border-yellow-500/20",
      failed: "bg-red-500/10 text-red-600 border-red-500/20",
    };
    return (
      <Badge className={variants[status] || "bg-muted text-muted-foreground"}>
        {status}
      </Badge>
    );
  };

  // ─── Format Date ──────────────────────────────────────────────────────
  const formatDate = (dateString: string) => {
    if (!dateString) return "N/A";
    return new Date(dateString).toLocaleDateString("en-KE", {
      year: "numeric",
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  };

  if (status === "loading") {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center">
          <Loader2 className="h-8 w-8 animate-spin text-primary mx-auto" />
          <p className="mt-2 text-muted-foreground">Loading...</p>
        </div>
      </div>
    );
  }

  if (!session) return null;

  return (
    <div className="min-h-screen bg-background pt-16">
      <Navigation />

      <div className="container py-8">
        <div className="mb-8">
          <h1 className="text-3xl font-bold font-playfair">
            Welcome back, {session.user?.name || "User"}! 👋
          </h1>
          <p className="text-muted-foreground">
            Here&apos;s your financial overview
          </p>
        </div>

        <Tabs defaultValue="overview" className="space-y-6">
          <TabsList className="flex flex-wrap gap-1">
            <TabsTrigger value="overview" className="flex items-center gap-2">
              <BarChart3 className="h-4 w-4" />
              Overview
            </TabsTrigger>
            <TabsTrigger value="converter" className="flex items-center gap-2">
              <Upload className="h-4 w-4" />
              Converter
            </TabsTrigger>
            <TabsTrigger value="search" className="flex items-center gap-2">
              <Search className="h-4 w-4" />
              Search
            </TabsTrigger>
            <TabsTrigger value="history" className="flex items-center gap-2">
              <Clock className="h-4 w-4" />
              History
            </TabsTrigger>
            <TabsTrigger value="profile" className="flex items-center gap-2">
              <User className="h-4 w-4" />
              Profile
            </TabsTrigger>
          </TabsList>

          {/* ─── Overview Tab ─────────────────────────────────────────────── */}
          <TabsContent value="overview">
            <div className="grid gap-4 md:grid-cols-4 mb-8">
              <Card>
                <CardContent className="p-4 flex items-center gap-4">
                  <div className="p-3 rounded-full bg-green-500/10">
                    <TrendingUp className="h-6 w-6 text-green-500" />
                  </div>
                  <div>
                    <p className="text-sm text-muted-foreground">
                      Total Income
                    </p>
                    <p className="text-xl font-bold">KES 0</p>
                  </div>
                </CardContent>
              </Card>
              <Card>
                <CardContent className="p-4 flex items-center gap-4">
                  <div className="p-3 rounded-full bg-red-500/10">
                    <Wallet className="h-6 w-6 text-red-500" />
                  </div>
                  <div>
                    <p className="text-sm text-muted-foreground">
                      Total Expenses
                    </p>
                    <p className="text-xl font-bold">KES 0</p>
                  </div>
                </CardContent>
              </Card>
              <Card>
                <CardContent className="p-4 flex items-center gap-4">
                  <div className="p-3 rounded-full bg-blue-500/10">
                    <CreditCard className="h-6 w-6 text-blue-500" />
                  </div>
                  <div>
                    <p className="text-sm text-muted-foreground">Net Flow</p>
                    <p className="text-xl font-bold">KES 0</p>
                  </div>
                </CardContent>
              </Card>
              <Card>
                <CardContent className="p-4 flex items-center gap-4">
                  <div className="p-3 rounded-full bg-purple-500/10">
                    <BarChart3 className="h-6 w-6 text-purple-500" />
                  </div>
                  <div>
                    <p className="text-sm text-muted-foreground">Analyses</p>
                    <p className="text-xl font-bold">{pagination.total || 0}</p>
                  </div>
                </CardContent>
              </Card>
            </div>

            <div className="mb-8">
              <h2 className="text-2xl font-semibold font-playfair mb-4">
                Upload New Statement
              </h2>
              <UploadZone onUploadComplete={(id) => setAnalysisId(id)} />
            </div>

            {analysisId && <DashboardComponent analysisId={analysisId} />}
            {!analysisId && latestAnalysisResult && (
              <DashboardComponent analysisId={latestAnalysisResult.id} />
            )}

            <div className="mt-8">
              <h2 className="text-2xl font-semibold font-playfair mb-4">
                Recent Analysis Insights
              </h2>
              {hasCompletedAnalysis ? (
                <div>
                  {latestLoading ? (
                    <div className="text-center py-6">
                      <Loader2 className="h-6 w-6 animate-spin mx-auto" />
                    </div>
                  ) : (
                    <div className="grid md:grid-cols-2 gap-6">
                      <TopCounterpartiesTable
                        title="Top Depositors"
                        items={latestAnalysisResult?.top_depositors || []}
                      />
                      <TopCounterpartiesTable
                        title="Top Creditors"
                        items={latestAnalysisResult?.top_creditors || []}
                      />
                    </div>
                  )}
                </div>
              ) : (
                <p className="text-sm text-muted-foreground">
                  No recent completed analyses.
                </p>
              )}
            </div>
          </TabsContent>

          {/* ─── Converter Tab ────────────────────────────────────────────── */}
          <TabsContent value="converter">
            <div className="space-y-6">
              <div>
                <h2 className="text-2xl font-semibold font-playfair">
                  Convert M-PESA Statements
                </h2>
                <p className="text-muted-foreground">
                  Convert your M-PESA PDF statements to CSV or Excel format
                </p>
              </div>

              <FileUploadZone
                onFilesUploaded={(files) => {
                  console.log("Files uploaded:", files.length);
                }}
                onConvert={handleConvert}
                isConverting={isConverting}
                progress={conversionProgress}
              />
            </div>
          </TabsContent>

          {/* ─── Search Tab ────────────────────────────────────────────────── */}
          <TabsContent value="search">
            <div className="space-y-6">
              <div>
                <h2 className="text-2xl font-semibold font-playfair">
                  Search Statements
                </h2>
                <p className="text-muted-foreground">
                  Search through your converted statements using Elasticsearch
                </p>
              </div>
              <SearchResults />
            </div>
          </TabsContent>

          {/* ─── History Tab ───────────────────────────────────────────────── */}
          <TabsContent value="history">
            <div className="space-y-6">
              <div className="flex items-center justify-between">
                <h2 className="text-2xl font-semibold font-playfair">
                  Your Analysis History
                </h2>
                <div className="flex gap-2">
                  <div className="text-sm text-muted-foreground flex items-center">
                    {pagination.total || 0} total analyses
                  </div>
                  <Button variant="outline" size="sm" onClick={refetch}>
                    <Clock className="h-4 w-4 mr-2" />
                    Refresh
                  </Button>
                </div>
              </div>

              <Card>
                <CardContent className="p-6">
                  <div className="flex items-center gap-4 mb-4">
                    <div className="flex-1">
                      <Input
                        placeholder="Search analyses by file name or status..."
                        value={searchQuery}
                        onChange={(e) => {
                          setSearchQuery(e.target.value);
                        }}
                        className="w-full"
                      />
                    </div>
                    <div className="text-sm text-muted-foreground whitespace-nowrap">
                      {filteredAnalyses.length} result(s)
                    </div>
                  </div>

                  {historyLoading ? (
                    <div className="text-center py-12">
                      <Loader2 className="h-8 w-8 animate-spin mx-auto text-muted-foreground" />
                      <p className="text-sm text-muted-foreground mt-2">
                        Loading analyses...
                      </p>
                    </div>
                  ) : filteredAnalyses.length === 0 ? (
                    <div className="text-center py-12">
                      <FileText className="h-12 w-12 mx-auto text-muted-foreground opacity-50" />
                      <p className="text-muted-foreground mt-4">
                        {searchQuery
                          ? "No analyses match your search."
                          : "No analyses yet. Upload your first statement!"}
                      </p>
                    </div>
                  ) : (
                    <div className="space-y-3">
                      {filteredAnalyses.map((analysis: any) => (
                        <div
                          key={analysis.id}
                          className="flex items-center justify-between p-4 hover:bg-muted rounded-lg transition-colors border hover:border-primary/50 group"
                        >
                          <div className="flex items-center gap-4 min-w-0 flex-1">
                            <div className="p-2 rounded-lg bg-primary/5 group-hover:bg-primary/10 transition-colors">
                              <FileText className="h-5 w-5 text-primary" />
                            </div>
                            <div className="min-w-0 flex-1">
                              <p className="font-medium truncate">
                                {analysis.file_name ||
                                  analysis.fileName ||
                                  "Untitled"}
                              </p>
                              <div className="flex flex-wrap items-center gap-3 text-sm text-muted-foreground">
                                <span>
                                  {formatDate(
                                    analysis.created_at || analysis.createdAt,
                                  )}
                                </span>
                                <span>•</span>
                                <span>
                                  {analysis.total_transactions ||
                                    analysis.transactionCount ||
                                    0}{" "}
                                  transactions
                                </span>
                                <span>•</span>
                                <span className="text-green-600">
                                  KES{" "}
                                  {analysis.total_income?.toLocaleString() || 0}
                                </span>
                                <span>•</span>
                                <span className="text-red-600">
                                  KES{" "}
                                  {analysis.total_expenses?.toLocaleString() ||
                                    0}
                                </span>
                              </div>
                            </div>
                          </div>
                          <div className="flex items-center gap-3">
                            {renderStatusBadge(analysis.status || "pending")}
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => handleViewAnalysis(analysis)}
                              className="text-primary hover:text-primary/80 hover:bg-primary/10 gap-1"
                              disabled={analysis.status !== "completed"}
                            >
                              <Eye className="h-4 w-4" />
                              View
                            </Button>
                          </div>
                        </div>
                      ))}

                      {totalPages > 1 && (
                        <div className="mt-6">{renderPagination()}</div>
                      )}
                    </div>
                  )}
                </CardContent>
              </Card>

              {/* Data Management */}
              <Card className="border-red-200 bg-red-50/30 dark:bg-red-950/10">
                <CardContent className="p-6 space-y-4">
                  <h3 className="font-semibold text-red-600">
                    Data Management
                  </h3>
                  <div className="flex flex-wrap gap-3">
                    <Button
                      variant="outline"
                      onClick={handleExport}
                      disabled={exporting}
                    >
                      <Download className="h-4 w-4 mr-2" />
                      {exporting ? "Exporting..." : "Export All Data"}
                    </Button>
                    <Button
                      variant="destructive"
                      onClick={() => setDeleteDialogOpen(true)}
                      disabled={deleting}
                    >
                      <Trash2 className="h-4 w-4 mr-2" />
                      {deleting ? "Deleting..." : "Delete All Data"}
                    </Button>
                  </div>
                  <p className="text-xs text-muted-foreground">
                    Export your data as JSON or permanently delete all your
                    data. This action cannot be undone.
                  </p>
                </CardContent>
              </Card>
            </div>
          </TabsContent>

          {/* ─── Profile Tab ───────────────────────────────────────────────── */}
          <TabsContent value="profile">
            <Card>
              <CardContent className="p-6 space-y-4">
                <div className="flex items-center gap-4">
                  <div className="w-16 h-16 rounded-full bg-primary/10 flex items-center justify-center">
                    <User className="h-8 w-8 text-primary" />
                  </div>
                  <div>
                    <h3 className="font-semibold">
                      {session.user?.name || "User"}
                    </h3>
                    <p className="text-sm text-muted-foreground">
                      {session.user?.email}
                    </p>
                    <Badge variant="secondary" className="mt-1">
                      {session.user?.role || "user"}
                    </Badge>
                  </div>
                </div>
                <div className="border-t pt-4">
                  <p className="text-sm text-muted-foreground">
                    Member since{" "}
                    {session.user?.createdAt
                      ? new Date(session.user.createdAt).toLocaleDateString()
                      : "Today"}
                  </p>
                </div>
                <Button variant="outline">Edit Profile</Button>
              </CardContent>
            </Card>
          </TabsContent>
        </Tabs>
      </div>

      <Footer />

      <AlertDialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle className="flex items-center gap-2 text-red-600">
              <AlertTriangle className="h-5 w-5" />
              Delete All Data?
            </AlertDialogTitle>
            <AlertDialogDescription>
              This action is <strong>permanent</strong> and cannot be undone.
              All your analyses, chat history, and payment records will be
              deleted.
              <br />
              <br />
              <span className="text-red-600 font-medium">
                This will not delete your account, only your data.
              </span>
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={handleDeleteData}
              className="bg-red-600 hover:bg-red-700"
            >
              Yes, Delete All Data
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
