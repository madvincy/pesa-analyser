"use client";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { useToast } from "@/components/ui/use-toast";
import { Clock, Download, Eye } from "lucide-react";
import { useEffect, useState } from "react";

interface ConversionHistory {
  id: string;
  file_name: string;
  file_count: number;
  transaction_count: number;
  total_amount: number;
  payment_reference: string | null;
  payment_amount: number;
  status: string;
  expires_at: string | null;
  created_at: string;
}

export function HistoryList() {
  const [history, setHistory] = useState<ConversionHistory[]>([]);
  const [loading, setLoading] = useState(true);
  const [total, setTotal] = useState(0);
  const [skip, setSkip] = useState(0);
  const [limit] = useState(20);
  const { toast } = useToast();

  useEffect(() => {
    fetchHistory();
  }, [skip]);

  const fetchHistory = async () => {
    try {
      const response = await fetch(
        `/api/converter/history?skip=${skip}&limit=${limit}`,
      );
      if (!response.ok) throw new Error("Failed to fetch history");
      const data = await response.json();
      setHistory(data.conversions || []);
      setTotal(data.total || 0);
    } catch (error) {
      console.error("Failed to fetch history:", error);
      toast({
        title: "Error",
        description: "Failed to load conversion history",
        variant: "destructive",
      });
    } finally {
      setLoading(false);
    }
  };

  const handleDownload = async (conversionId: string) => {
    try {
      const response = await fetch(`/api/converter/download/${conversionId}`);
      if (!response.ok) throw new Error("Download failed");

      const blob = await response.blob();
      const contentDisposition = response.headers.get("Content-Disposition");
      let filename = `statement_${conversionId}.csv`;
      if (contentDisposition) {
        const match = contentDisposition.match(/filename="(.+)"/);
        if (match) filename = match[1];
      }

      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      window.URL.revokeObjectURL(url);

      toast({
        title: "Success",
        description: "File downloaded successfully",
      });
    } catch (error) {
      console.error("Download failed:", error);
      toast({
        title: "Error",
        description: "Failed to download file",
        variant: "destructive",
      });
    }
  };

  const handleViewAnalytics = (conversionId: string) => {
    // Navigate to analytics page
    window.location.href = `/analytics/${conversionId}`;
  };

  const formatDate = (dateStr: string) => {
    if (!dateStr) return "";
    const date = new Date(dateStr);
    return date.toLocaleDateString() + " " + date.toLocaleTimeString();
  };

  const getStatusBadge = (status: string) => {
    switch (status) {
      case "completed":
        return <Badge className="bg-green-500">Completed</Badge>;
      case "processing":
        return <Badge className="bg-blue-500">Processing</Badge>;
      case "failed":
        return <Badge className="bg-red-500">Failed</Badge>;
      case "expired":
        return <Badge className="bg-gray-500">Expired</Badge>;
      default:
        return <Badge>{status}</Badge>;
    }
  };

  if (loading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="text-sm font-medium">
            Conversion History
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            {[...Array(5)].map((_, i) => (
              <Skeleton key={i} className="h-12 w-full" />
            ))}
          </div>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader>
        <div className="flex justify-between items-center">
          <CardTitle className="text-sm font-medium">
            Conversion History ({total} records)
          </CardTitle>
          <Button variant="outline" size="sm" onClick={fetchHistory}>
            <Clock className="h-4 w-4 mr-2" />
            Refresh
          </Button>
        </div>
      </CardHeader>
      <CardContent>
        {history.length === 0 ? (
          <div className="text-center py-8 text-muted-foreground">
            No conversion history found
          </div>
        ) : (
          <>
            <div className="rounded-md border overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>File Name</TableHead>
                    <TableHead>Files</TableHead>
                    <TableHead>Transactions</TableHead>
                    <TableHead>Total Amount</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead>Created</TableHead>
                    <TableHead>Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {history.map((item) => (
                    <TableRow key={item.id}>
                      <TableCell className="font-medium">
                        {item.file_name}
                      </TableCell>
                      <TableCell>{item.file_count}</TableCell>
                      <TableCell>{item.transaction_count}</TableCell>
                      <TableCell>
                        KES {item.total_amount.toLocaleString()}
                      </TableCell>
                      <TableCell>{getStatusBadge(item.status)}</TableCell>
                      <TableCell className="text-sm">
                        {formatDate(item.created_at)}
                      </TableCell>
                      <TableCell>
                        <div className="flex gap-1">
                          <Button
                            variant="ghost"
                            size="icon"
                            className="h-8 w-8"
                            onClick={() => handleViewAnalytics(item.id)}
                            title="View Analytics"
                          >
                            <Eye className="h-4 w-4" />
                          </Button>
                          {item.status === "completed" && (
                            <Button
                              variant="ghost"
                              size="icon"
                              className="h-8 w-8"
                              onClick={() => handleDownload(item.id)}
                              title="Download"
                            >
                              <Download className="h-4 w-4" />
                            </Button>
                          )}
                        </div>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>

            {/* Pagination */}
            {total > limit && (
              <div className="flex justify-center mt-4 gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setSkip(Math.max(0, skip - limit))}
                  disabled={skip === 0}
                >
                  Previous
                </Button>
                <span className="flex items-center px-4 text-sm">
                  {Math.floor(skip / limit) + 1} of {Math.ceil(total / limit)}
                </span>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setSkip(skip + limit)}
                  disabled={skip + limit >= total}
                >
                  Next
                </Button>
              </div>
            )}
          </>
        )}
      </CardContent>
    </Card>
  );
}
