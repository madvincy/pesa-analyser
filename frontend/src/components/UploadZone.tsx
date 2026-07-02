"use client";

import { cn } from "@/lib/utils";
import Dexie, { type Table } from "dexie";
import { AnimatePresence, motion } from "framer-motion";
import {
  ArrowRight,
  CheckCircle2,
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
import { useCallback, useState } from "react";
import { useDropzone } from "react-dropzone";
import { toast } from "sonner";
import { Badge } from "./ui/badge";
import { Button } from "./ui/button";
import { Card } from "./ui/card";
import { Input } from "./ui/input";
import { Label } from "./ui/label";
import { Progress } from "./ui/progress";

// ─── Dexie DB ─────────────────────────────────────────────────────────────────
interface FileRecord {
  fileId: string;
  fileName: string;
  uploadedAt: string;
}

class PesaDB extends Dexie {
  files!: Table<FileRecord>;
  constructor() {
    super("PesaAnalyserDB");
    this.version(1).stores({ files: "fileId" });
  }
}

const db = new PesaDB();

// ─── Constants ────────────────────────────────────────────────────────────────
const MAX_FILE_SIZE = 50 * 1024 * 1024;

const FILE_TYPES = {
  pdf: { icon: FileText, color: "text-red-500", label: "PDF" },
  csv: { icon: FileJson, color: "text-blue-500", label: "CSV" },
  xls: { icon: FileSpreadsheet, color: "text-green-500", label: "Excel" },
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

async function storeFileInDB(fileId: string, fileName: string): Promise<void> {
  await db.files.put({
    fileId,
    fileName,
    uploadedAt: new Date().toISOString(),
  });
}

// ─── PDF Encryption Check ────────────────────────────────────────────────────
async function isPdfEncrypted(file: File): Promise<boolean> {
  try {
    const { PDFDocument } = await import("pdf-lib");
    const buffer = await file.arrayBuffer();
    await PDFDocument.load(buffer, { ignoreEncryption: false });
    return false;
  } catch (e) {
    const msg = e instanceof Error ? e.message.toLowerCase() : "";

    if (
      msg.includes("encrypt") ||
      msg.includes("password") ||
      msg.includes("decrypt")
    ) {
      return true;
    }
    return false;
  }
}

// ─── Types ────────────────────────────────────────────────────────────────────
interface UploadZoneProps {
  onUploadComplete: (fileId: string) => void;
}

// ─── Component ────────────────────────────────────────────────────────────────
export function UploadZone({ onUploadComplete }: UploadZoneProps) {
  const { data: session, status } = useSession();
  const router = useRouter();

  const [file, setFile] = useState<File | null>(null);
  const [isUploading, setIsUploading] = useState(false);
  const [isPasswordProtected, setIsPasswordProtected] = useState(false);
  const [password, setPassword] = useState("");
  const [uploadProgress, setUploadProgress] = useState(0);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [isCheckingEncryption, setIsCheckingEncryption] = useState(false);
  const [passwordAttempts, setPasswordAttempts] = useState(0);

  // ── Dropzone ─────────────────────────────────────────────────────────────
  const onDrop = useCallback(
    async (acceptedFiles: File[]) => {
      if (!session) {
        toast.error("Please sign in to upload and analyse statements.");
        router.push("/auth/signin");
        return;
      }

      const selected = acceptedFiles[0];
      if (!selected) return;

      const validationError = validateFile(selected);
      if (validationError) {
        toast.error(validationError);
        return;
      }

      setFile(selected);
      setPassword("");
      setUploadError(null);
      setUploadProgress(0);
      setIsUploading(false);
      setIsPasswordProtected(false);
      setPasswordAttempts(0);

      if (getFileExtension(selected.name) === ".pdf") {
        setIsCheckingEncryption(true);
        try {
          const encrypted = await isPdfEncrypted(selected);
          setIsPasswordProtected(encrypted);

          if (encrypted) {
            toast.warning(
              "🔒 This PDF is password protected. Enter the password below.",
            );
          } else {
            toast.success("📄 PDF ready — click Analyse to continue.");
          }
        } catch (err) {
          console.error("Encryption check failed:", err);
        } finally {
          setIsCheckingEncryption(false);
        }
      }
    },
    [session, router],
  );

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      "application/pdf": [".pdf"],
      "text/csv": [".csv"],
      "application/vnd.ms-excel": [".xls", ".xlsx"],
      "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": [
        ".xlsx",
      ],
    },
    maxFiles: 1,
    maxSize: MAX_FILE_SIZE,
  });

  // ── Reset ────────────────────────────────────────────────────────────────
  const removeFile = () => {
    setFile(null);
    setPassword("");
    setUploadProgress(0);
    setUploadError(null);
    setIsPasswordProtected(false);
    setIsUploading(false);
    setPasswordAttempts(0);
    setIsCheckingEncryption(false);
  };

  // ── Get token from session ───────────────────────────────────────────────
  const getAuthToken = useCallback(() => {
    // ✅ Get token from session.accessToken (created in auth.ts)
    if (session?.accessToken) {
      return session.accessToken;
    }

    // ✅ Fallback: Try to get from localStorage
    if (typeof window !== "undefined") {
      const localToken = localStorage.getItem("accessToken");
      if (localToken) {
        return localToken;
      }
    }
    return null;
  }, [session]);

  // ── Upload ────────────────────────────────────────────────────────────────
  const handleUpload = async () => {
    if (!file) {
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
      formData.append("file", file);
      if (password) formData.append("password", password);

      // ✅ Get the token from session
      const token = getAuthToken();

      // ✅ Build headers with Authorization
      const headers: HeadersInit = {};
      if (token) {
        headers["Authorization"] = `Bearer ${token}`;
      } else {
        console.warn("⚠️ No token available - request may fail with 401");
      }

      const response = await fetch("/api/upload", {
        method: "POST",
        headers,
        body: formData,
        credentials: "include",
      });

      const data = await response.json();
      clearInterval(interval);

      // ── Handle 401 (Unauthorized) ──────────────────────────────────────
      if (response.status === 401) {
        setUploadProgress(0);
        setUploadError("Authentication required. Please sign in again.");
        toast.error("Your session has expired. Please sign in again.");

        setTimeout(() => {
          router.push("/auth/signin");
        }, 2000);
        return;
      }

      // ── Password-protected PDF ────────────────────────────────────────
      if (
        response.status === 401 &&
        data.detail ===
          "PDF is password protected. Please provide the password."
      ) {
        const attempts = passwordAttempts + 1;
        setPasswordAttempts(attempts);
        setIsPasswordProtected(true);
        setUploadProgress(0);
        setPassword("");

        const errMsg =
          attempts > 1
            ? `Incorrect password (attempt ${attempts}). Please try again.`
            : "This PDF is password protected. Enter the password below.";

        setUploadError(errMsg);
        toast.error(errMsg);
        return;
      }

      // ── Other API errors ────────────────────────────────────────────────
      if (!response.ok) {
        throw new Error(
          data?.error ?? data?.message ?? `Upload failed (${response.status})`,
        );
      }

      // ── Success ─────────────────────────────────────────────────────────
      setUploadProgress(100);
      toast.success("Statement uploaded! Analysis is underway 🎉");

      await storeFileInDB(data.fileId, file.name);

      setTimeout(() => {
        removeFile();
        onUploadComplete(data.fileId);
      }, 1500);
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

  // ── Derived ───────────────────────────────────────────────────────────────
  const fileType = file ? getFileType(file.name) : null;
  const FileIcon = fileType ? FILE_TYPES[fileType].icon : File;

  const progressLabel =
    uploadProgress < 30
      ? "📄 Parsing your document..."
      : uploadProgress < 60
        ? "🧠 AI is analysing transactions..."
        : uploadProgress < 90
          ? "📊 Generating insights..."
          : "✨ Almost done...";

  // ── Unauthenticated ───────────────────────────────────────────────────────
  if (!session && status !== "loading") {
    return (
      <Card className="p-8 text-center border-2 border-dashed border-primary/30">
        <div className="flex flex-col items-center gap-4">
          <div className="p-4 rounded-full bg-primary/10">
            <Sparkles className="h-8 w-8 text-primary" />
          </div>
          <div>
            <h3 className="text-lg font-semibold">Sign In to Upload</h3>
            <p className="text-sm text-muted-foreground">
              Create an account or sign in to analyse your statements.
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

  // ── Loading ──────────────────────────────────────────────────────────────
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

  // ── Main ──────────────────────────────────────────────────────────────────
  return (
    <div className="w-full max-w-4xl mx-auto">
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5 }}
      >
        {/* ── Drop zone ── */}
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
              file && "border-green-500 bg-green-50/50 dark:bg-green-950/10",
            )}
          >
            <input {...getInputProps()} />

            <AnimatePresence mode="wait">
              {!file ? (
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
                        ? "Drop your statement here"
                        : "Upload your statement"}
                    </h3>
                    <p className="text-sm text-muted-foreground">
                      Drag & drop or click to select PDF, CSV, or Excel files
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
                    <span>Max size: 50 MB</span>
                    <span>•</span>
                    <span>Free basic analysis</span>
                    <span>•</span>
                    <span>Secure & private</span>
                  </div>
                </motion.div>
              ) : (
                /* ── File selected state ── */
                <motion.div
                  key="selected"
                  initial={{ opacity: 0, scale: 0.9 }}
                  animate={{ opacity: 1, scale: 1 }}
                  exit={{ opacity: 0, scale: 0.9 }}
                  className="flex flex-col items-center justify-center space-y-4 text-center"
                >
                  <div className="p-4 rounded-full bg-green-500/10">
                    <CheckCircle2 className="w-8 h-8 text-green-500" />
                  </div>

                  <div>
                    <h3 className="text-lg font-semibold text-green-500">
                      File Selected
                    </h3>

                    <div className="flex items-center gap-2 text-sm bg-muted px-3 py-1 rounded mt-2">
                      <FileIcon className="h-4 w-4 text-muted-foreground" />
                      <span className="font-medium">{file.name}</span>
                      <span className="text-muted-foreground">
                        ({(file.size / 1024 / 1024).toFixed(2)} MB)
                      </span>
                      <button
                        type="button"
                        onClick={(e) => {
                          e.stopPropagation();
                          removeFile();
                        }}
                        className="ml-2 p-0.5 hover:bg-destructive/10 rounded-full"
                        aria-label="Remove file"
                      >
                        <X className="h-4 w-4 text-muted-foreground hover:text-destructive" />
                      </button>
                    </div>

                    {isCheckingEncryption && (
                      <p className="text-sm text-muted-foreground mt-2 flex items-center justify-center gap-1">
                        <Loader2 className="h-3 w-3 animate-spin" />
                        Checking PDF security…
                      </p>
                    )}

                    {!isCheckingEncryption && isPasswordProtected && (
                      <p className="text-sm text-yellow-600 dark:text-yellow-400 mt-2 flex items-center justify-center gap-1">
                        <Lock className="h-4 w-4" />
                        Password protected — enter password below
                      </p>
                    )}

                    {!isCheckingEncryption &&
                      !isPasswordProtected &&
                      getFileExtension(file.name) === ".pdf" && (
                        <p className="text-sm text-green-600 dark:text-green-400 mt-2">
                          ✅ PDF is unlocked and ready to upload
                        </p>
                      )}
                  </div>
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        </Card>

        {/* ── Controls ── */}
        <AnimatePresence>
          {file && !isCheckingEncryption && (
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
                      <Badge variant="destructive" className="text-xs ml-auto">
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
                          handleUpload();
                        }
                      }}
                      autoFocus
                    />
                    <Button
                      onClick={handleUpload}
                      disabled={!password.trim() || isUploading}
                    >
                      {isUploading ? (
                        <Loader2 className="h-4 w-4 animate-spin" />
                      ) : (
                        "Unlock & Upload"
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
                <div className="flex justify-center gap-3">
                  <Button
                    onClick={handleUpload}
                    disabled={isUploading}
                    className="min-w-[200px] gap-2 group"
                  >
                    {isUploading ? (
                      <span className="flex items-center gap-2">
                        <Loader2 className="h-4 w-4 animate-spin" />
                        Uploading… {uploadProgress}%
                      </span>
                    ) : (
                      <>
                        <Zap className="h-4 w-4 group-hover:rotate-12 transition-transform" />
                        Analyse Statement
                      </>
                    )}
                  </Button>
                  <Button
                    variant="outline"
                    onClick={removeFile}
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
    </div>
  );
}
