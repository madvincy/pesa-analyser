"use client";

import { cn } from "@/lib/utils";
import Dexie, { type Table } from "dexie";
import { AnimatePresence, motion } from "framer-motion";
import {
  ArrowRight,
  CheckCircle2,
  Clock,
  Download,
  File,
  FileJson,
  FileSpreadsheet,
  FileText,
  Loader2,
  Lock,
  Sparkles,
  Upload,
  X,
  Zap,
} from "lucide-react";
import { useSession } from "next-auth/react";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { useDropzone } from "react-dropzone";
import { toast } from "sonner";
import { Badge } from "./ui/badge";
import { Button } from "./ui/button";
import { Card } from "./ui/card";
import { Input } from "./ui/input";
import { Label } from "./ui/label";
import { Progress } from "./ui/progress";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "./ui/tabs";

// ─── Dexie DB ─────────────────────────────────────────────────────────────────
interface FileRecord {
  fileId: string;
  fileName: string;
  uploadedAt: string;
  mode?: "analysis" | "conversion";
  conversionFormat?: string;
  transactionCount?: number;
  totalAmount?: number;
  status?: string;
}

class PesaDB extends Dexie {
  files!: Table<FileRecord>;
  conversions!: Table<FileRecord>;
  constructor() {
    super("PesaAnalyserDB");
    this.version(2).stores({
      files: "fileId, uploadedAt, mode",
      conversions: "fileId, uploadedAt, mode, conversionFormat",
    });
  }
}

const db = new PesaDB();

// ─── Constants ────────────────────────────────────────────────────────────────
const MAX_FILE_SIZE = 50 * 1024 * 1024;

const FILE_TYPES = {
  pdf: {
    icon: FileText,
    color: "text-red-500",
    label: "PDF",
    bg: "bg-red-50 dark:bg-red-950/20",
  },
  csv: {
    icon: FileJson,
    color: "text-blue-500",
    label: "CSV",
    bg: "bg-blue-50 dark:bg-blue-950/20",
  },
  xls: {
    icon: FileSpreadsheet,
    color: "text-green-500",
    label: "Excel",
    bg: "bg-green-50 dark:bg-green-950/20",
  },
} as const;

const VALID_EXTENSIONS = [".pdf", ".csv", ".xls", ".xlsx"];

// ─── Helpers ──────────────────────────────────────────────────────────────────
function getFileExtension(filename: string): string {
  return "." + (filename.split(".").pop()?.toLowerCase() ?? "");
}

function getFileType(filename: string): keyof typeof FILE_TYPES | null {
  const ext = getFileExtension(filename);
  if (ext === ".pdf") return "pdf";
  if (ext === ".csv") return "csv";
  if ([".xls", ".xlsx"].includes(ext)) return "xls";
  return null;
}

function validateFile(file: File): string | null {
  if (!VALID_EXTENSIONS.includes(getFileExtension(file.name)))
    return "Invalid file type. Please upload a PDF, CSV, or Excel file.";
  if (file.size > MAX_FILE_SIZE)
    return "File is too large. Maximum size is 50 MB.";
  return null;
}

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function formatDate(dateString: string): string {
  return new Date(dateString).toLocaleDateString("en-KE", {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

// ─── Types ────────────────────────────────────────────────────────────────────
type UploadMode = "analysis" | "conversion" | "both";

interface UploadZoneProps {
  mode?: UploadMode;
  onUploadComplete?: (fileId: string) => void;
  onConvertComplete?: (fileId: string, format: string) => void;
  multiple?: boolean;
  maxFiles?: number;
  showHistory?: boolean;
  title?: string;
  description?: string;
  accept?: Record<string, string[]>;
}

// ─── Component ────────────────────────────────────────────────────────────────
export function UploadZone({
  mode = "analysis",
  onUploadComplete,
  onConvertComplete,
  multiple = false,
  maxFiles = 1,
  showHistory = true,
  title,
  description,
  accept = {
    "application/pdf": [".pdf"],
    "text/csv": [".csv"],
    "application/vnd.ms-excel": [".xls", ".xlsx"],
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": [
      ".xlsx",
    ],
  },
}: UploadZoneProps) {
  const { data: session, status } = useSession();
  const router = useRouter();

  const [files, setFiles] = useState<File[]>([]);
  const [isUploading, setIsUploading] = useState(false);
  const [isPasswordProtected, setIsPasswordProtected] = useState(false);
  const [password, setPassword] = useState("");
  const [uploadProgress, setUploadProgress] = useState(0);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [passwordAttempts, setPasswordAttempts] = useState(0);
  const [conversionFormat, setConversionFormat] = useState<"csv" | "excel">(
    "csv",
  );
  const [conversionHistory, setConversionHistory] = useState<any[]>([]);
  const [analysisHistory, setAnalysisHistory] = useState<any[]>([]);
  const [activeTab, setActiveTab] = useState<"upload" | "history">("upload");

  // ─── Load history ──────────────────────────────────────────────────────────
  useEffect(() => {
    if (showHistory) {
      loadHistory();
    }
  }, [mode]);

  const loadHistory = async () => {
    try {
      if (mode === "conversion" || mode === "both") {
        const conversions = await db.conversions
          .where("mode")
          .equals("conversion")
          .toArray();
        setConversionHistory(conversions.reverse().slice(0, 20));
      }
      if (mode === "analysis" || mode === "both") {
        const analyses = await db.files
          .where("mode")
          .equals("analysis")
          .toArray();
        setAnalysisHistory(analyses.reverse().slice(0, 20));
      }
    } catch (error) {
      console.error("Failed to load history:", error);
    }
  };

  // ─── Dropzone ─────────────────────────────────────────────────────────────
  const onDrop = useCallback(
    async (acceptedFiles: File[]) => {
      if (!session) {
        toast.error("Please sign in to upload statements.");
        router.push("/auth/signin");
        return;
      }

      if (!multiple && acceptedFiles.length > 1) {
        toast.error("Only one file allowed. Please select a single file.");
        return;
      }

      if (acceptedFiles.length > maxFiles) {
        toast.error(`Maximum ${maxFiles} files allowed.`);
        return;
      }

      const validFiles: File[] = [];
      const errors: string[] = [];

      for (const file of acceptedFiles) {
        const validationError = validateFile(file);
        if (validationError) {
          errors.push(`${file.name}: ${validationError}`);
        } else {
          validFiles.push(file);
        }
      }

      if (errors.length > 0) {
        toast.error(errors.join("\n"));
      }

      if (validFiles.length === 0) return;

      setFiles(validFiles);
      setPassword("");
      setUploadError(null);
      setUploadProgress(0);
      setIsUploading(false);
      setIsPasswordProtected(false);
      setPasswordAttempts(0);

      toast.success(`${validFiles.length} file(s) ready.`);
    },
    [session, router, multiple, maxFiles],
  );

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept,
    maxFiles: multiple ? maxFiles : 1,
    maxSize: MAX_FILE_SIZE,
    multiple,
  });

  // ── Reset ────────────────────────────────────────────────────────────────
  const removeFile = (index?: number) => {
    if (index !== undefined) {
      setFiles((prev) => prev.filter((_, i) => i !== index));
    } else {
      setFiles([]);
    }
    setPassword("");
    setUploadProgress(0);
    setUploadError(null);
    setIsPasswordProtected(false);
    setIsUploading(false);
    setPasswordAttempts(0);
  };

  const clearAll = () => {
    setFiles([]);
    setPassword("");
    setUploadProgress(0);
    setUploadError(null);
    setIsPasswordProtected(false);
    setIsUploading(false);
    setPasswordAttempts(0);
  };

  // ── Get token from session ───────────────────────────────────────────────
  const getAuthToken = useCallback(() => {
    if (session?.accessToken) {
      return session.accessToken;
    }
    if (typeof window !== "undefined") {
      const localToken = localStorage.getItem("accessToken");
      if (localToken) return localToken;
    }
    return null;
  }, [session]);

  // ── Handle Upload (Analysis mode) ──────────────────────────────────────
  const handleUpload = async () => {
    if (files.length === 0) {
      toast.error("Please select a file to upload.");
      return;
    }

    if (isPasswordProtected && !password.trim()) {
      toast.error("Please enter the PDF password to continue.");
      return;
    }

    setIsUploading(true);
    setUploadError(null);
    setUploadProgress(0);

    const interval = setInterval(() => {
      setUploadProgress((prev) => (prev >= 90 ? prev : prev + 5));
    }, 500);

    try {
      const formData = new FormData();
      files.forEach((file) => {
        formData.append("file", file);
      });
      if (password) formData.append("password", password);
      formData.append("mode", mode);

      const token = getAuthToken();
      const headers: HeadersInit = {};
      if (token) {
        headers["Authorization"] = `Bearer ${token}`;
      }

      const response = await fetch("/api/upload", {
        method: "POST",
        headers,
        body: formData,
        credentials: "include",
      });

      const data = await response.json();
      clearInterval(interval);

      if (response.status === 401) {
        const message = data?.error ?? "Authentication required.";
        if (/password|protected|encrypted/i.test(message)) {
          setIsPasswordProtected(true);
          setUploadError(message);
          setUploadProgress(0);
          toast.warning(message);
          return;
        }
        setUploadProgress(0);
        setUploadError("Authentication required. Please sign in again.");
        toast.error("Your session has expired. Please sign in again.");
        setTimeout(() => router.push("/auth/signin"), 2000);
        return;
      }

      if (!response.ok) {
        throw new Error(
          data?.error ?? data?.message ?? `Upload failed (${response.status})`,
        );
      }

      setUploadProgress(100);
      toast.success(
        data.message ?? `Upload complete! ${files.length} file(s) uploaded.`,
      );

      // Store in DB
      for (const file of files) {
        await db.files.put({
          fileId: data.fileId || `file_${Date.now()}`,
          fileName: file.name,
          uploadedAt: new Date().toISOString(),
          mode: "analysis",
          status: data.status ?? "queued",
        });
      }
      await loadHistory();

      if (onUploadComplete) {
        setTimeout(() => {
          onUploadComplete(data.fileId);
        }, 500);
      }

      setTimeout(() => {
        clearAll();
      }, 2000);
    } catch (error) {
      clearInterval(interval);
      const message =
        error instanceof Error
          ? error.message
          : "Upload failed. Please try again.";
      setUploadError(message);
      setUploadProgress(0);
      toast.error(message);
    } finally {
      setIsUploading(false);
    }
  };

  // ─── Handle Convert (Conversion mode) ──────────────────────────────────
  const handleConvert = async () => {
    if (files.length === 0) {
      toast.error("Please select a file to convert.");
      return;
    }

    if (isPasswordProtected && !password.trim()) {
      toast.error("Please enter the PDF password to continue.");
      return;
    }

    setIsUploading(true);
    setUploadError(null);
    setUploadProgress(0);

    const interval = setInterval(() => {
      setUploadProgress((prev) => (prev >= 90 ? prev : prev + 5));
    }, 300);

    try {
      const formData = new FormData();
      files.forEach((file) => {
        formData.append("files", file);
      });
      formData.append("format", conversionFormat);
      if (password) formData.append("password", password);
      formData.append("mode", "conversion");

      const token = getAuthToken();
      const headers: HeadersInit = {};
      if (token) {
        headers["Authorization"] = `Bearer ${token}`;
      }

      const response = await fetch("/api/converter/convert", {
        method: "POST",
        headers,
        body: formData,
        credentials: "include",
      });

      const data = await response.json();
      clearInterval(interval);

      if (response.status === 401) {
        setUploadProgress(0);
        setUploadError("Authentication required. Please sign in again.");
        toast.error("Your session has expired. Please sign in again.");
        setTimeout(() => router.push("/auth/signin"), 2000);
        return;
      }

      if (!response.ok) {
        throw new Error(
          data?.error ??
            data?.message ??
            `Conversion failed (${response.status})`,
        );
      }

      setUploadProgress(100);
      toast.success(
        `Conversion complete! ${files.length} file(s) converted to ${conversionFormat.toUpperCase()}`,
      );

      // Store in DB
      for (const file of files) {
        await db.conversions.put({
          fileId: data.conversion_id || `conv_${Date.now()}`,
          fileName: file.name,
          uploadedAt: new Date().toISOString(),
          mode: "conversion",
          conversionFormat: conversionFormat,
          transactionCount: data.transactionCount || 0,
          totalAmount: data.totalAmount || 0,
          status: "completed",
        });
      }
      await loadHistory();

      if (onConvertComplete) {
        setTimeout(() => {
          onConvertComplete(data.conversion_id, conversionFormat);
        }, 500);
      }

      setTimeout(() => {
        clearAll();
      }, 2000);
    } catch (error) {
      clearInterval(interval);
      const message =
        error instanceof Error
          ? error.message
          : "Conversion failed. Please try again.";
      setUploadError(message);
      setUploadProgress(0);
      toast.error(message);
    } finally {
      setIsUploading(false);
    }
  };

  // ─── Get file icon ──────────────────────────────────────────────────────
  const getFileIcon = (fileName: string) => {
    const type = getFileType(fileName);
    if (type) return FILE_TYPES[type].icon;
    return File;
  };

  const getFileColor = (fileName: string) => {
    const type = getFileType(fileName);
    if (type) return FILE_TYPES[type].color;
    return "text-muted-foreground";
  };

  const getFileBg = (fileName: string) => {
    const type = getFileType(fileName);
    if (type) return FILE_TYPES[type].bg;
    return "bg-muted/30";
  };

  // ─── Progress label ─────────────────────────────────────────────────────
  const progressLabel =
    mode === "conversion"
      ? uploadProgress < 30
        ? "📄 Parsing your document(s)..."
        : uploadProgress < 60
          ? "🔄 Extracting transactions..."
          : uploadProgress < 90
            ? "📊 Formatting output..."
            : "✨ Almost done..."
      : uploadProgress < 30
        ? "📄 Parsing your document..."
        : uploadProgress < 60
          ? "🧠 AI is analysing transactions..."
          : uploadProgress < 90
            ? "📊 Generating insights..."
            : "✨ Almost done...";

  const isConversionMode = mode === "conversion" || mode === "both";

  // ─── Unauthenticated ───────────────────────────────────────────────────────
  if (!session && status !== "loading") {
    return (
      <Card className="p-8 text-center border-2 border-dashed border-primary/30">
        <div className="flex flex-col items-center gap-4">
          <div className="p-4 rounded-full bg-primary/10">
            <Sparkles className="h-8 w-8 text-primary" />
          </div>
          <div>
            <h3 className="text-lg font-semibold">
              Sign In to {isConversionMode ? "Convert" : "Upload"}
            </h3>
            <p className="text-sm text-muted-foreground">
              Create an account or sign in to{" "}
              {isConversionMode
                ? "convert your statements"
                : "analyse your statements"}
              .
            </p>
          </div>
          <Button onClick={() => router.push("/auth/signin")} className="gap-2">
            Get Started
            <ArrowRight className="h-4 w-4" />
          </Button>
        </div>
      </Card>
    );
  }

  if (status === "loading") {
    return (
      <Card className="p-8 text-center border-2 border-dashed">
        <div className="flex flex-col items-center gap-4">
          <Loader2 className="h-8 w-8 animate-spin text-primary" />
          <p className="text-sm text-muted-foreground">Loading...</p>
        </div>
      </Card>
    );
  }

  // ─── Main ──────────────────────────────────────────────────────────────────
  return (
    <div className="w-full max-w-4xl mx-auto">
      <Tabs
        value={activeTab}
        onValueChange={(v) => setActiveTab(v as "upload" | "history")}
        className="space-y-4"
      >
        <div className="flex items-center justify-between">
          <TabsList>
            <TabsTrigger value="upload" className="flex items-center gap-2">
              <Upload className="h-4 w-4" />
              {isConversionMode ? "Upload & Convert" : "Upload"}
            </TabsTrigger>
            {showHistory && (
              <TabsTrigger value="history" className="flex items-center gap-2">
                <Clock className="h-4 w-4" />
                History (
                {isConversionMode
                  ? conversionHistory.length
                  : analysisHistory.length}
                )
              </TabsTrigger>
            )}
          </TabsList>

          {title && <h2 className="text-xl font-semibold">{title}</h2>}
        </div>

        <TabsContent value="upload">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5 }}
          >
            <Card className="overflow-hidden">
              <div
                {...getRootProps()}
                className={cn(
                  "p-8 border-2 border-dashed transition-all duration-300 cursor-pointer relative",
                  isDragActive
                    ? "border-primary bg-primary/5 scale-[1.02]"
                    : "border-muted-foreground/25 hover:border-primary/50",
                  isUploading &&
                    "pointer-events-none opacity-50",
                  files.length > 0 &&
                    "border-green-500 bg-green-50/50 dark:bg-green-950/10",
                )}
              >
                <input {...getInputProps()} />

                <AnimatePresence mode="wait">
                  {files.length === 0 ? (
                    <motion.div
                      key="empty"
                      initial={{ opacity: 0 }}
                      animate={{ opacity: 1 }}
                      exit={{ opacity: 0 }}
                      className="flex flex-col items-center justify-center space-y-4 text-center"
                    >
                      <motion.div
                        animate={{ y: [0, -10, 0] }}
                        transition={{ duration: 2, repeat: Infinity }}
                        className="p-4 rounded-full bg-primary/10"
                      >
                        <Upload className="w-8 h-8 text-primary" />
                      </motion.div>

                      <div>
                        <h3 className="text-lg font-semibold">
                          {isDragActive
                            ? "Drop your files here"
                            : description ||
                              (isConversionMode
                                ? "Drop your statements here"
                                : "Upload your statement")}
                        </h3>
                        <p className="text-sm text-muted-foreground">
                          Drag & drop or click to select PDF, CSV, or Excel
                          files
                        </p>
                        <div className="flex items-center justify-center gap-3 mt-2">
                          {Object.entries(FILE_TYPES).map(
                            ([key, { icon: Icon, color, label }]) => (
                              <div
                                key={key}
                                className="flex items-center gap-1 text-xs text-muted-foreground"
                              >
                                <Icon className={cn("h-4 w-4", color)} />
                                <span>{label}</span>
                              </div>
                            ),
                          )}
                        </div>
                      </div>

                      <div className="flex items-center gap-2 text-xs text-muted-foreground">
                        <span>Max size: 50 MB each</span>
                        <span>•</span>
                        <span>Max files: {maxFiles}</span>
                        <span>•</span>
                        <span>Secure & private</span>
                      </div>
                    </motion.div>
                  ) : (
                    <motion.div
                      key="selected"
                      initial={{ opacity: 0, scale: 0.9 }}
                      animate={{ opacity: 1, scale: 1 }}
                      exit={{ opacity: 0, scale: 0.9 }}
                      className="space-y-4"
                    >
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-3">
                          <div className="p-2 rounded-full bg-green-500/10">
                            <CheckCircle2 className="w-6 h-6 text-green-500" />
                          </div>
                          <div>
                            <h3 className="text-lg font-semibold text-green-500">
                              {files.length} File(s) Selected
                            </h3>
                            <p className="text-sm text-muted-foreground">
                              Total:{" "}
                              {formatFileSize(
                                files.reduce((acc, f) => acc + f.size, 0),
                              )}
                            </p>
                          </div>
                        </div>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={(e) => {
                            e.stopPropagation();
                            clearAll();
                          }}
                          className="text-red-500 hover:text-red-700 hover:bg-red-50"
                        >
                          <X className="h-4 w-4 mr-1" />
                          Clear All
                        </Button>
                      </div>

                      <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 max-h-40 overflow-y-auto">
                        {files.map((file, index) => (
                          <div
                            key={index}
                            className="flex items-center gap-2 p-2 rounded-lg bg-muted/30 hover:bg-muted/50 transition-colors group"
                          >
                            <div
                              className={cn(
                                "p-1.5 rounded",
                                getFileBg(file.name),
                              )}
                            >
                              {(() => {
                                const Icon = getFileIcon(file.name);
                                return (
                                  <Icon
                                    className={cn(
                                      "h-4 w-4",
                                      getFileColor(file.name),
                                    )}
                                  />
                                );
                              })()}
                            </div>
                            <div className="flex-1 min-w-0">
                              <p className="text-xs font-medium truncate">
                                {file.name}
                              </p>
                              <p className="text-xs text-muted-foreground">
                                {formatFileSize(file.size)}
                              </p>
                            </div>
                            <Button
                              variant="ghost"
                              size="icon"
                              className="h-6 w-6 opacity-0 group-hover:opacity-100 transition-opacity hover:bg-red-50 hover:text-red-500"
                              onClick={(e) => {
                                e.stopPropagation();
                                removeFile(index);
                              }}
                              disabled={isUploading}
                            >
                              <X className="h-3 w-3" />
                            </Button>
                          </div>
                        ))}
                      </div>

                      {isPasswordProtected && (
                        <p className="text-sm text-yellow-600 dark:text-yellow-400 flex items-center justify-center gap-1">
                          <Lock className="h-4 w-4" />
                          Password protected — enter password below
                        </p>
                      )}

                      {!isPasswordProtected &&
                        files.some(
                          (f) => getFileExtension(f.name) === ".pdf",
                        ) && (
                          <p className="text-sm text-green-600 dark:text-green-400 text-center">
                            ✅ PDFs are ready to{" "}
                            {isConversionMode ? "convert" : "upload"}
                          </p>
                        )}
                    </motion.div>
                  )}
                </AnimatePresence>
              </div>
            </Card>

            <AnimatePresence>
              {files.length > 0 && (
                <motion.div
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: 10 }}
                  className="mt-4 space-y-4"
                >
                  {isPasswordProtected && (
                    <div className="flex flex-col gap-2 max-w-md mx-auto">
                      <div className="flex items-center gap-2">
                        <Lock className="h-4 w-4 text-yellow-600 flex-shrink-0" />
                        <Label
                          htmlFor="pdf-password"
                          className="text-sm font-medium"
                        >
                          PDF Password Required
                        </Label>
                        {passwordAttempts > 0 && (
                          <Badge
                            variant="destructive"
                            className="text-xs ml-auto"
                          >
                            {passwordAttempts} failed{" "}
                            {passwordAttempts === 1 ? "attempt" : "attempts"}
                          </Badge>
                        )}
                      </div>

                      <div className="flex gap-2">
                        <Input
                          id="pdf-password"
                          type="password"
                          placeholder="Enter PDF password"
                          value={password}
                          onChange={(e) => {
                            setPassword(e.target.value);
                            setUploadError(null);
                          }}
                          className={cn(
                            "flex-1",
                            passwordAttempts > 0 && "border-red-400",
                          )}
                          disabled={isUploading}
                          onKeyDown={(e) => {
                            if (
                              e.key === "Enter" &&
                              password.trim() &&
                              !isUploading
                            ) {
                              isConversionMode
                                ? handleConvert()
                                : handleUpload();
                            }
                          }}
                          autoFocus
                        />
                        <Button
                          onClick={
                            isConversionMode ? handleConvert : handleUpload
                          }
                          disabled={!password.trim() || isUploading}
                        >
                          {isUploading ? (
                            <Loader2 className="h-4 w-4 animate-spin" />
                          ) : (
                            "Unlock & Continue"
                          )}
                        </Button>
                      </div>

                      {uploadError && (
                        <p className="text-sm text-red-500">{uploadError}</p>
                      )}
                      <p className="text-xs text-muted-foreground">
                        Enter the password used to protect this PDF.
                      </p>
                    </div>
                  )}

                  {!isPasswordProtected && (
                    <div className="flex flex-wrap items-center justify-center gap-3">
                      {isConversionMode && (
                        <div className="flex gap-1 bg-muted p-1 rounded-md">
                          <Button
                            onClick={() => setConversionFormat("csv")}
                            variant={
                              conversionFormat === "csv" ? "default" : "ghost"
                            }
                            size="sm"
                            disabled={isUploading}
                            className="transition-all"
                          >
                            <FileJson className="h-4 w-4 mr-1" />
                            CSV
                          </Button>
                          <Button
                            onClick={() => setConversionFormat("excel")}
                            variant={
                              conversionFormat === "excel" ? "default" : "ghost"
                            }
                            size="sm"
                            disabled={isUploading}
                            className="transition-all"
                          >
                            <FileSpreadsheet className="h-4 w-4 mr-1" />
                            Excel
                          </Button>
                        </div>
                      )}

                      <Button
                        onClick={
                          isConversionMode ? handleConvert : handleUpload
                        }
                        disabled={isUploading || files.length === 0}
                        className="min-w-[200px] gap-2 group"
                      >
                        {isUploading ? (
                          <span className="flex items-center gap-2">
                            <Loader2 className="h-4 w-4 animate-spin" />
                            {isConversionMode
                              ? "Converting…"
                              : "Uploading…"}{" "}
                            {uploadProgress}%
                          </span>
                        ) : (
                          <>
                            <Zap className="h-4 w-4 group-hover:rotate-12 transition-transform" />
                            {isConversionMode
                              ? `Convert ${files.length} File${files.length > 1 ? "s" : ""}`
                              : `Analyse ${files.length} File${files.length > 1 ? "s" : ""}`}
                          </>
                        )}
                      </Button>

                      <Button
                        variant="outline"
                        onClick={clearAll}
                        disabled={isUploading}
                      >
                        Cancel
                      </Button>
                    </div>
                  )}

                  {isUploading && (
                    <div className="max-w-md mx-auto">
                      <Progress value={uploadProgress} className="h-2" />
                      <p className="text-xs text-muted-foreground text-center mt-2">
                        {progressLabel}
                      </p>
                    </div>
                  )}

                  {uploadError && !isPasswordProtected && (
                    <p className="text-sm text-red-500 text-center">
                      {uploadError}
                    </p>
                  )}
                </motion.div>
              )}
            </AnimatePresence>
          </motion.div>
        </TabsContent>

        {showHistory && (
          <TabsContent value="history">
            <Card>
              <Card className="p-4">
                <div className="flex items-center justify-between mb-4">
                  <h3 className="font-semibold">
                    {isConversionMode
                      ? "Conversion History"
                      : "Analysis History"}
                  </h3>
                  <Button variant="ghost" size="sm" onClick={loadHistory}>
                    <Clock className="h-4 w-4 mr-2" />
                    Refresh
                  </Button>
                </div>

                {(() => {
                  const history = isConversionMode
                    ? conversionHistory
                    : analysisHistory;
                  if (history.length === 0) {
                    return (
                      <div className="text-center py-8 text-muted-foreground">
                        <FileText className="h-12 w-12 mx-auto opacity-50 mb-2" />
                        <p>
                          No {isConversionMode ? "conversion" : "analysis"}{" "}
                          history yet
                        </p>
                        <p className="text-sm">
                          {isConversionMode ? "Convert" : "Upload"} your first
                          statement to see history here
                        </p>
                      </div>
                    );
                  }
                  return (
                    <div className="space-y-2 max-h-96 overflow-y-auto">
                      {history.map((record) => (
                        <div
                          key={record.fileId}
                          className="flex items-center justify-between p-3 hover:bg-muted rounded-lg transition-colors border"
                        >
                          <div className="flex items-center gap-3 min-w-0">
                            <div className="p-2 rounded-lg bg-primary/5">
                              <FileText className="h-4 w-4 text-primary" />
                            </div>
                            <div className="min-w-0">
                              <p className="text-sm font-medium truncate">
                                {record.fileName}
                              </p>
                              <div className="flex items-center gap-2 text-xs text-muted-foreground">
                                <span>{formatDate(record.uploadedAt)}</span>
                                {isConversionMode &&
                                  record.conversionFormat && (
                                    <>
                                      <span>•</span>
                                      <Badge
                                        variant="outline"
                                        className="text-xs"
                                      >
                                        {record.conversionFormat?.toUpperCase()}
                                      </Badge>
                                    </>
                                  )}
                                {record.transactionCount && (
                                  <>
                                    <span>•</span>
                                    <span>
                                      {record.transactionCount} transactions
                                    </span>
                                  </>
                                )}
                                {record.status && (
                                  <>
                                    <span>•</span>
                                    <Badge
                                      className={cn(
                                        "text-xs",
                                        record.status === "completed"
                                          ? "bg-green-500/10 text-green-600"
                                          : "bg-yellow-500/10 text-yellow-600",
                                      )}
                                    >
                                      {record.status}
                                    </Badge>
                                  </>
                                )}
                              </div>
                            </div>
                          </div>
                          <Button
                            variant="ghost"
                            size="sm"
                            className="text-primary"
                          >
                            <Download className="h-4 w-4" />
                          </Button>
                        </div>
                      ))}
                    </div>
                  );
                })()}
              </Card>
            </Card>
          </TabsContent>
        )}
      </Tabs>
    </div>
  );
}

// ─── Export both as UploadZone and default ──────────────────────────────────
export default UploadZone;
