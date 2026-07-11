"use client";

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
  FileText,
  Loader2,
  MessageSquare,
  Trash2,
  TrendingUp,
  User,
  Wallet,
} from "lucide-react";
import { useSession } from "next-auth/react";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

export default function DashboardPage() {
  const { data: session, status } = useSession();
  const router = useRouter();
  const [analysisId, setAnalysisId] = useState<string | null>(null);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);

  // ✅ Use the history hook with proper typing
  const {
    history,
    loading: historyLoading,
    refetch,
  } = useHistoryData({
    type: "all",
    limit: 5,
  });

  // History data helpers and latest analysis state
  const analyses = history.analyses || [];
  const chats = history.chats || [];
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
  const [analysisPage, setAnalysisPage] = useState(1);
  const [analysesPerPage] = useState(5);
  const [chatPage, setChatPage] = useState(1);
  const [chatsPerPage] = useState(5);

  // Fetch latest analysis result when analyses change
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
          <TabsList>
            <TabsTrigger value="overview">Overview</TabsTrigger>
            <TabsTrigger value="history">History</TabsTrigger>
            <TabsTrigger value="profile">Profile</TabsTrigger>
          </TabsList>

          <TabsContent value="overview">
            {/* Quick Stats */}
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
                    <p className="text-xl font-bold">{analyses.length || 0}</p>
                  </div>
                </CardContent>
              </Card>
            </div>

            {/* Upload Section */}
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

            {/* Top counterparties for latest completed analysis */}
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

          <TabsContent value="history">
            <div className="space-y-6">
              <div className="flex items-center justify-between">
                <h2 className="text-2xl font-semibold font-playfair">
                  Your History
                </h2>
                <Button variant="outline" size="sm" onClick={refetch}>
                  <Clock className="h-4 w-4 mr-2" />
                  Refresh
                </Button>
              </div>

              {/* Analyses History */}
              <Card>
                <CardContent className="p-6">
                  <h3 className="font-semibold mb-4">Analyses</h3>
                  {historyLoading ? (
                    <div className="text-center py-8">
                      <Loader2 className="h-6 w-6 animate-spin mx-auto" />
                      <p className="text-sm text-muted-foreground mt-2">
                        Loading...
                      </p>
                    </div>
                  ) : analyses.length === 0 ? (
                    <p className="text-center text-muted-foreground py-8">
                      No analyses yet. Upload your first statement!
                    </p>
                  ) : (
                    <div className="space-y-3">
                      <div className="flex items-center gap-2 mb-3">
                        <input
                          aria-label="Search analyses"
                          placeholder="Search analyses..."
                          value={searchQuery}
                          onChange={(e) => {
                            setSearchQuery(e.target.value);
                            setAnalysisPage(1);
                          }}
                          className="input input-sm flex-1 px-3 py-2 border rounded"
                        />
                      </div>
                      {(() => {
                        const filtered = analyses.filter((a: any) => {
                          const q = searchQuery.trim().toLowerCase();
                          if (!q) return true;
                          return (
                            (a.fileName || a.file_name || "")
                              .toLowerCase()
                              .includes(q) ||
                            (a.status || "").toLowerCase().includes(q)
                          );
                        });
                        const start = (analysisPage - 1) * analysesPerPage;
                        const pageItems = filtered.slice(
                          start,
                          start + analysesPerPage,
                        );

                        return (
                          <>
                            {pageItems.map((analysis: any) => (
                              <div
                                key={analysis.id}
                                className="flex items-center justify-between p-3 hover:bg-muted rounded-lg transition-colors"
                              >
                                <div className="flex items-center gap-3">
                                  <FileText className="h-5 w-5 text-muted-foreground" />
                                  <div>
                                    <p className="font-medium">
                                      {analysis.fileName}
                                    </p>
                                    <p className="text-sm text-muted-foreground">
                                      {analysis.status} •{" "}
                                      {new Date(
                                        analysis.createdAt,
                                      ).toLocaleDateString()}
                                    </p>
                                  </div>
                                </div>
                                <Badge
                                  variant={
                                    analysis.status === "completed"
                                      ? "success"
                                      : "secondary"
                                  }
                                >
                                  {analysis.status}
                                </Badge>
                              </div>
                            ))}

                            {/* Pagination */}
                            {filtered.length > analysesPerPage && (
                              <div className="flex items-center justify-center gap-2 mt-4">
                                <Button
                                  size="sm"
                                  variant="outline"
                                  onClick={() =>
                                    setAnalysisPage((p) => Math.max(1, p - 1))
                                  }
                                  disabled={analysisPage === 1}
                                >
                                  Prev
                                </Button>
                                <span className="text-sm text-muted-foreground">
                                  Page {analysisPage} of{" "}
                                  {Math.ceil(filtered.length / analysesPerPage)}
                                </span>
                                <Button
                                  size="sm"
                                  variant="outline"
                                  onClick={() =>
                                    setAnalysisPage((p) =>
                                      Math.min(
                                        Math.ceil(
                                          filtered.length / analysesPerPage,
                                        ),
                                        p + 1,
                                      ),
                                    )
                                  }
                                  disabled={
                                    analysisPage >=
                                    Math.ceil(filtered.length / analysesPerPage)
                                  }
                                >
                                  Next
                                </Button>
                              </div>
                            )}
                          </>
                        );
                      })()}
                    </div>
                  )}
                </CardContent>
              </Card>

              {/* Chat History */}
              <Card>
                <CardContent className="p-6">
                  <h3 className="font-semibold mb-4">Chat History</h3>
                  {historyLoading ? (
                    <div className="text-center py-8">
                      <Loader2 className="h-6 w-6 animate-spin mx-auto" />
                      <p className="text-sm text-muted-foreground mt-2">
                        Loading...
                      </p>
                    </div>
                  ) : chats.length === 0 ? (
                    <p className="text-center text-muted-foreground py-8">
                      No chat history yet.
                    </p>
                  ) : (
                    <div className="space-y-3">
                      <div className="flex items-center gap-2 mb-3">
                        <input
                          aria-label="Search chats"
                          placeholder="Search chat messages..."
                          value={searchQuery}
                          onChange={(e) => {
                            setSearchQuery(e.target.value);
                            setChatPage(1);
                          }}
                          className="input input-sm flex-1 px-3 py-2 border rounded"
                        />
                      </div>
                      {(() => {
                        const q = searchQuery.trim().toLowerCase();
                        const filteredChats = chats.filter((c: any) => {
                          if (!q) return true;
                          return (c.message || c.content || "")
                            .toLowerCase()
                            .includes(q);
                        });
                        const start = (chatPage - 1) * chatsPerPage;
                        const pageItems = filteredChats.slice(
                          start,
                          start + chatsPerPage,
                        );

                        return (
                          <>
                            {pageItems.map((chat: any) => (
                              <div
                                key={chat.id}
                                className="p-3 hover:bg-muted rounded-lg transition-colors"
                              >
                                <div className="flex items-start gap-3">
                                  <MessageSquare className="h-5 w-5 text-muted-foreground mt-1" />
                                  <div className="flex-1">
                                    <p className="text-sm font-medium line-clamp-2">
                                      {chat.message}
                                    </p>
                                    <p className="text-xs text-muted-foreground mt-1">
                                      {new Date(
                                        chat.createdAt,
                                      ).toLocaleString()}
                                    </p>
                                  </div>
                                </div>
                              </div>
                            ))}
                            {/* Chat pagination */}
                            {filteredChats &&
                              filteredChats.length > chatsPerPage && (
                                <div className="flex items-center justify-center gap-2 mt-4">
                                  <Button
                                    size="sm"
                                    variant="outline"
                                    onClick={() =>
                                      setChatPage((p) => Math.max(1, p - 1))
                                    }
                                    disabled={chatPage === 1}
                                  >
                                    Prev
                                  </Button>
                                  <span className="text-sm text-muted-foreground">
                                    Page {chatPage} of{" "}
                                    {Math.ceil(
                                      filteredChats.length / chatsPerPage,
                                    )}
                                  </span>
                                  <Button
                                    size="sm"
                                    variant="outline"
                                    onClick={() =>
                                      setChatPage((p) =>
                                        Math.min(
                                          Math.ceil(
                                            filteredChats.length / chatsPerPage,
                                          ),
                                          p + 1,
                                        ),
                                      )
                                    }
                                    disabled={
                                      chatPage >=
                                      Math.ceil(
                                        filteredChats.length / chatsPerPage,
                                      )
                                    }
                                  >
                                    Next
                                  </Button>
                                </div>
                              )}
                          </>
                        );
                      })()}
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

      {/* Delete Data Dialog */}
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
