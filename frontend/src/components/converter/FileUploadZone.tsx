"use client";

import { cn } from "@/lib/utils";
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
import { FileRejection, useDropzone } from "react-dropzone";
import { toast } from "sonner";
import { Badge } from "../ui/badge";
import { Button } from "../ui/button";
import { Card } from "../ui/card";
import { Input } from "../ui/input";
import { Label } from "../ui/label";
import { Progress } from "../ui/progress";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "../ui/tabs";

// ─── Import Conversion Service ──────────────────────────────────────────────
import {
  conversionService,
  type ConversionHistoryItem,
  type ConversionResponse,
} from "@/services/conversionService";

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
interface FileUploadZoneProps {
  onFilesUploaded?: (files: File[]) => void;
  onConvert?: (format: string, result: ConversionResponse) => void;
  isConverting?: boolean;
  progress?: number;
  multiple?: boolean;
  maxFiles?: number;
  accept?: Record<string, string[]>;
}

// ─── Component ────────────────────────────────────────────────────────────────
export function FileUploadZone({
  onFilesUploaded,
  onConvert,
  isConverting = false,
  progress = 0,
  multiple = true,
  maxFiles = 10,
  accept = {
    "application/pdf": [".pdf"],
    "text/csv": [".csv"],
    "application/vnd.ms-excel": [".xls", ".xlsx"],
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": [
      ".xlsx",
    ],
  },
}: FileUploadZoneProps) {
  const { data: session, status } = useSession();
  const router = useRouter();

  const [files, setFiles] = useState<File[]>([]);
  const [isUploading, setIsUploading] = useState(false);
  const [isPasswordProtected, setIsPasswordProtected] = useState(false);
  const [password, setPassword] = useState("");
  const [uploadProgress, setUploadProgress] = useState(0);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [isCheckingEncryption, setIsCheckingEncryption] = useState(false);
  const [passwordAttempts, setPasswordAttempts] = useState(0);
  const [conversionFormat, setConversionFormat] = useState<"csv" | "excel">(
    "csv",
  );
  const [conversionHistory, setConversionHistory] = useState<
    ConversionHistoryItem[]
  >([]);
  const [conversionResult, setConversionResult] =
    useState<ConversionResponse | null>(null);

  // ─── Load conversion history ──────────────────────────────────────────────
  useEffect(() => {
    loadConversionHistory();
  }, []);

  const loadConversionHistory = async () => {
    try {
      // Try to get from API first, falls back to localStorage
      const response = await conversionService.getHistory(0, 20);
      setConversionHistory(response.conversions);
    } catch (error) {
      console.error("Failed to load conversion history:", error);
      // Fallback to local history
      const localHistory = conversionService.getLocalHistory();
      const historyItems: ConversionHistoryItem[] = localHistory.map(
        (record) => ({
          id: record.fileId,
          file_name: record.fileName,
          file_count: 1,
          transaction_count: record.transactionCount || 0,
          total_amount: record.totalAmount || 0,
          payment_amount: 0, // Default value for local history
          status: "completed",
          created_at: record.uploadedAt,
        }),
      );
      setConversionHistory(historyItems);
    }
  };

  // ─── Dropzone ─────────────────────────────────────────────────────────────
  const onDrop = useCallback(
    async (acceptedFiles: File[], rejectedFiles: FileRejection[]) => {
      if (!session) {
        toast.error("Please sign in to convert statements.");
        router.push("/auth/signin");
        return;
      }

      // Handle rejected files
      if (rejectedFiles.length > 0) {
        rejectedFiles.forEach(({ file, errors }) => {
          errors.forEach((error) => {
            toast.error(`${file.name}: ${error.message}`);
          });
        });
      }

      if (!multiple && acceptedFiles.length > 1) {
        toast.error("Only one file allowed. Please select a single file.");
        return;
      }

      if (acceptedFiles.length > maxFiles) {
        toast.error(`Maximum ${maxFiles} files allowed.`);
        return;
      }

      // Validate files using the service
      const { valid, invalid } = conversionService.validateFiles(acceptedFiles);

      if (invalid.length > 0) {
        invalid.forEach(({ file, error }) => {
          toast.error(`${file.name}: ${error}`);
        });
      }

      if (valid.length === 0) return;

      setFiles(valid);
      setPassword("");
      setUploadError(null);
      setUploadProgress(0);
      setIsUploading(false);
      setIsPasswordProtected(false);
      setPasswordAttempts(0);

      // Call the callback with valid files
      if (onFilesUploaded) {
        onFilesUploaded(valid);
      }

      // Check encryption for PDFs using the service
      const pdfFiles = valid.filter((f) => getFileExtension(f.name) === ".pdf");
      if (pdfFiles.length > 0 && pdfFiles.length === valid.length) {
        setIsCheckingEncryption(true);
        try {
          const encrypted = await conversionService.isPdfEncrypted(pdfFiles[0]);
          setIsPasswordProtected(encrypted);
          if (encrypted) {
            toast.warning(
              "🔒 PDF is password protected. Enter the password below.",
            );
          } else {
            toast.success(`${valid.length} file(s) ready for conversion.`);
          }
        } catch (err) {
          console.error("Encryption check failed:", err);
          toast.error("Failed to check PDF encryption. Please try again.");
        } finally {
          setIsCheckingEncryption(false);
        }
      } else {
        toast.success(`${valid.length} file(s) ready for conversion.`);
      }
    },
    [session, router, multiple, maxFiles, onFilesUploaded],
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
    setIsCheckingEncryption(false);
  };

  const clearAll = () => {
    setFiles([]);
    setPassword("");
    setUploadProgress(0);
    setUploadError(null);
    setIsPasswordProtected(false);
    setIsUploading(false);
    setPasswordAttempts(0);
    setIsCheckingEncryption(false);
  };

  // ── Handle Convert ──────────────────────────────────────────────────────
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

    // Simulate progress
    const interval = setInterval(() => {
      setUploadProgress((prev) => (prev >= 90 ? prev : prev + 5));
    }, 300);

    try {
      // Use the conversion service
      const result = await conversionService.convertFiles(
        files,
        conversionFormat,
        password || undefined,
      );

      clearInterval(interval);
      setUploadProgress(100);
      setConversionResult(result);

      toast.success(
        `Conversion complete! ${files.length} file(s) converted to ${conversionFormat.toUpperCase()}`,
      );

      // Reload history
      await loadConversionHistory();

      // Call the onConvert callback with result
      if (onConvert) {
        onConvert(conversionFormat, result);
      }

      // Auto-download if single file
      if (files.length === 1 && result.conversion_id) {
        try {
          const { blob, filename } =
            await conversionService.downloadConversionWithFilename(
              result.conversion_id,
            );

          // Create download link
          const url = URL.createObjectURL(blob);
          const link = document.createElement("a");
          link.href = url;
          link.download = filename;
          document.body.appendChild(link);
          link.click();
          document.body.removeChild(link);
          URL.revokeObjectURL(url);

          toast.success("File downloaded automatically!");
        } catch (downloadError) {
          console.error("Auto-download failed:", downloadError);
          toast.warning(
            "Conversion complete. Click download button to get your file.",
          );
        }
      }

      setTimeout(() => {
        clearAll();
      }, 3000);
    } catch (error: any) {
      clearInterval(interval);
      const message = error?.message || "Conversion failed. Please try again.";
      setUploadError(message);
      setUploadProgress(0);

      // Handle specific error codes
      if (error?.code === "UNAUTHORIZED") {
        toast.error("Your session has expired. Please sign in again.");
        setTimeout(() => router.push("/auth/signin"), 2000);
      } else if (error?.code === "EXPIRED") {
        toast.error("This conversion has expired. Please try again.");
      } else {
        toast.error(message);
      }
    } finally {
      setIsUploading(false);
    }
  };

  // ── Handle Download ─────────────────────────────────────────────────────
  const handleDownload = async (conversionId: string, fileName: string) => {
    try {
      const { blob, filename } =
        await conversionService.downloadConversionWithFilename(conversionId);

      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = filename || fileName;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      URL.revokeObjectURL(url);

      toast.success("File downloaded successfully!");
    } catch (error: any) {
      const message = error?.message || "Download failed. Please try again.";
      toast.error(message);
      console.error("Download error:", error);
    }
  };

  // ── Get file icon ──────────────────────────────────────────────────────
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
    uploadProgress < 30
      ? "📄 Parsing your document(s)..."
      : uploadProgress < 60
        ? "🔄 Extracting transactions..."
        : uploadProgress < 90
          ? "📊 Formatting output..."
          : "✨ Almost done...";

  // ─── Unauthenticated ───────────────────────────────────────────────────────
  if (!session && status !== "loading") {
    return (
      <Card className="p-8 text-center border-2 border-dashed border-primary/30">
        <div className="flex flex-col items-center gap-4">
          <div className="p-4 rounded-full bg-primary/10">
            <Sparkles className="h-8 w-8 text-primary" />
          </div>
          <div>
            <h3 className="text-lg font-semibold">Sign In to Convert</h3>
            <p className="text-sm text-muted-foreground">
              Create an account or sign in to convert your statements.
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
      <Tabs defaultValue="upload" className="space-y-4">
        <TabsList className="grid w-full grid-cols-2">
          <TabsTrigger value="upload" className="flex items-center gap-2">
            <Upload className="h-4 w-4" />
            Upload & Convert
          </TabsTrigger>
          <TabsTrigger value="history" className="flex items-center gap-2">
            <Clock className="h-4 w-4" />
            History ({conversionHistory.length})
          </TabsTrigger>
        </TabsList>

        <TabsContent value="upload">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5 }}
          >
            {/* ─── Drop zone ── */}
            <Card className="overflow-hidden">
              <div
                {...getRootProps()}
                className={cn(
                  "p-8 border-2 border-dashed transition-all duration-300 cursor-pointer relative",
                  isDragActive
                    ? "border-primary bg-primary/5 scale-[1.02]"
                    : "border-muted-foreground/25 hover:border-primary/50",
                  (isUploading || isCheckingEncryption) &&
                    "pointer-events-none opacity-50",
                  files.length > 0 &&
                    "border-green-500 bg-green-50/50 dark:bg-green-950/10",
                )}
              >
                <input {...getInputProps()} />

                <AnimatePresence mode="wait">
                  {files.length === 0 ? (
                    /* ── Empty state ── */
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
                            : "Drop your statements here"}
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
                    /* ── Files selected state ── */
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

                      {isCheckingEncryption && (
                        <p className="text-sm text-muted-foreground flex items-center justify-center gap-1">
                          <Loader2 className="h-3 w-3 animate-spin" />
                          Checking PDF security…
                        </p>
                      )}

                      {!isCheckingEncryption && isPasswordProtected && (
                        <p className="text-sm text-yellow-600 dark:text-yellow-400 flex items-center justify-center gap-1">
                          <Lock className="h-4 w-4" />
                          Password protected — enter password below
                        </p>
                      )}

                      {!isCheckingEncryption &&
                        !isPasswordProtected &&
                        files.some(
                          (f) => getFileExtension(f.name) === ".pdf",
                        ) && (
                          <p className="text-sm text-green-600 dark:text-green-400 text-center">
                            ✅ PDFs are unlocked and ready to convert
                          </p>
                        )}
                    </motion.div>
                  )}
                </AnimatePresence>
              </div>
            </Card>

            {/* ─── Controls ── */}
            <AnimatePresence>
              {files.length > 0 && !isCheckingEncryption && (
                <motion.div
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: 10 }}
                  className="mt-4 space-y-4"
                >
                  {/* Password input for encrypted PDFs */}
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
                              handleConvert();
                            }
                          }}
                          autoFocus
                        />
                        <Button
                          onClick={handleConvert}
                          disabled={!password.trim() || isUploading}
                        >
                          {isUploading ? (
                            <Loader2 className="h-4 w-4 animate-spin" />
                          ) : (
                            "Unlock & Convert"
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

                  {/* Format selection and convert button */}
                  {!isPasswordProtected && (
                    <div className="flex flex-wrap items-center justify-center gap-3">
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

                      <Button
                        onClick={handleConvert}
                        disabled={isUploading || files.length === 0}
                        className="min-w-[200px] gap-2 group"
                      >
                        {isUploading ? (
                          <span className="flex items-center gap-2">
                            <Loader2 className="h-4 w-4 animate-spin" />
                            Converting… {uploadProgress}%
                          </span>
                        ) : (
                          <>
                            <Zap className="h-4 w-4 group-hover:rotate-12 transition-transform" />
                            Convert {files.length} File
                            {files.length > 1 ? "s" : ""}
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

                  {/* Progress bar */}
                  {isUploading && (
                    <div className="max-w-md mx-auto">
                      <Progress value={uploadProgress} className="h-2" />
                      <p className="text-xs text-muted-foreground text-center mt-2">
                        {progressLabel}
                      </p>
                    </div>
                  )}

                  {/* Error message */}
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

        {/* ─── History Tab ────────────────────────────────────────────────── */}
        <TabsContent value="history">
          <Card>
            <Card className="p-4">
              <div className="flex items-center justify-between mb-4">
                <h3 className="font-semibold">Conversion History</h3>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={loadConversionHistory}
                >
                  <Clock className="h-4 w-4 mr-2" />
                  Refresh
                </Button>
              </div>

              {conversionHistory.length === 0 ? (
                <div className="text-center py-8 text-muted-foreground">
                  <FileText className="h-12 w-12 mx-auto opacity-50 mb-2" />
                  <p>No conversion history yet</p>
                  <p className="text-sm">
                    Convert your first statement to see history here
                  </p>
                </div>
              ) : (
                <div className="space-y-2 max-h-96 overflow-y-auto">
                  {conversionHistory.map((record) => (
                    <div
                      key={record.id}
                      className="flex items-center justify-between p-3 hover:bg-muted rounded-lg transition-colors border"
                    >
                      <div className="flex items-center gap-3 min-w-0">
                        <div className="p-2 rounded-lg bg-primary/5">
                          <FileText className="h-4 w-4 text-primary" />
                        </div>
                        <div className="min-w-0">
                          <p className="text-sm font-medium truncate">
                            {record.file_name}
                          </p>
                          <div className="flex items-center gap-2 text-xs text-muted-foreground">
                            <span>
                              {formatDate(
                                record.created_at || new Date().toISOString(),
                              )}
                            </span>
                            <span>•</span>
                            <Badge variant="outline" className="text-xs">
                              {record.status}
                            </Badge>
                            {record.transaction_count > 0 && (
                              <>
                                <span>•</span>
                                <span>
                                  {record.transaction_count} transactions
                                </span>
                              </>
                            )}
                            {record.total_amount !== 0 && (
                              <>
                                <span>•</span>
                                <span>
                                  KES {record.total_amount.toFixed(2)}
                                </span>
                              </>
                            )}
                            {record.payment_amount !== undefined &&
                              record.payment_amount > 0 && (
                                <>
                                  <span>•</span>
                                  <span className="text-primary">
                                    Paid: KES {record.payment_amount.toFixed(2)}
                                  </span>
                                </>
                              )}
                          </div>
                        </div>
                      </div>
                      <Button
                        variant="ghost"
                        size="sm"
                        className="text-primary"
                        onClick={() =>
                          handleDownload(record.id, record.file_name)
                        }
                        disabled={record.status !== "completed"}
                      >
                        <Download className="h-4 w-4" />
                      </Button>
                    </div>
                  ))}
                </div>
              )}
            </Card>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}
