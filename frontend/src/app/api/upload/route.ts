import { authOptions } from "@/lib/auth";
import { getServerSession } from "next-auth";
import { NextRequest, NextResponse } from "next/server";

const FASTAPI_URL = process.env.FASTAPI_URL ?? "http://localhost:8000";

export async function POST(request: NextRequest) {

  try {
    // ── Auth ────────────────────────────────────────────────────────────────
    const session = await getServerSession(authOptions);

    if (!session?.user) {
      return NextResponse.json({ error: "Unauthorised" }, { status: 401 });
    }

    // ── Parse form data ─────────────────────────────────────────────────────
    const formData = await request.formData();
    const file = formData.get("file") as File | null;
    const password = formData.get("password") as string | null;


    if (!file) {
      return NextResponse.json({ error: "No file provided" }, { status: 400 });
    }

    // ── MIME / size guard ───────────────────────────────────────────────────
    const validTypes = [
      "application/pdf",
      "text/csv",
      "application/vnd.ms-excel",
      "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ];

    // Also check file extension for cases where MIME type is not set correctly
    const fileExtension = file.name.split(".").pop()?.toLowerCase();
    const validExtensions = ["pdf", "csv", "xls", "xlsx"];

    const isValidType =
      validTypes.includes(file.type) ||
      (fileExtension && validExtensions.includes(fileExtension));

    if (!isValidType) {
      return NextResponse.json(
        { error: `Invalid file type. Upload a PDF, CSV, or Excel file.` },
        { status: 415 },
      );
    }

    if (file.size > 50 * 1024 * 1024) {
      return NextResponse.json(
        { error: "File exceeds the 50 MB limit." },
        { status: 413 },
      );
    }

    // ── PDF encryption check ONLY if password is provided ──────────────────
    // The backend will handle the actual validation and return 401 if needed
    // This client-side check is just to provide early feedback
    let isEncrypted = false;
    if (file.type === "application/pdf" || fileExtension === "pdf") {
      const encryptionStatus = await checkPdfEncryption(
        file,
        password ?? undefined,
      );

      if (encryptionStatus === "encrypted_no_password") {
        // Return 401 to trigger password prompt in the frontend
        return NextResponse.json(
          { error: "PDF is password protected. Please provide the password." },
          { status: 401 },
        );
      }

      if (encryptionStatus === "wrong_password") {
        return NextResponse.json(
          { error: "Incorrect PDF password. Please try again." },
          { status: 401 },
        );
      }

      isEncrypted = encryptionStatus === "ok" && password !== null;
    }

    // ── Forward to FastAPI ──────────────────────────────────────────────────
    // Use /api/v1/upload to match your backend route
    const backendUrl = `${FASTAPI_URL}/api/v1/upload`;

    const upstream = new FormData();
    upstream.append("file", file);
    if (password && isEncrypted) {
      upstream.append("password", password);
    }

    const headers = new Headers();
    if (session?.accessToken) {
      headers.set("Authorization", `Bearer ${session.accessToken}`);
    }
    if (
      session?.user?.id &&
      /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(
        session.user.id,
      )
    ) {
      headers.set("X-User-ID", session.user.id);
    }
    if (session?.user?.email) {
      headers.set("X-User-Email", session.user.email);
    }
    if (session?.user?.name) {
      headers.set("X-User-Name", session.user.name);
    }

    let fastapiResponse: Response;
    try {
      fastapiResponse = await fetch(backendUrl, {
        method: "POST",
        headers,
        body: upstream,
        credentials: "include",
      });
    } catch (fetchError) {
      console.error("🔴 [/api/upload] cannot reach FastAPI:", fetchError);
      return NextResponse.json(
        { error: "Analysis service is unavailable. Please try again later." },
        { status: 503 },
      );
    }

    // Read response body
    let data: any = {};
    try {
      const text = await fastapiResponse.text();
      if (text) {
        data = JSON.parse(text);
      }
    } catch (parseError) {
      console.error(
        "🔴 [/api/upload] failed to parse FastAPI response:",
        parseError,
      );
      return NextResponse.json(
        { error: "Invalid response from analysis service." },
        { status: 502 },
      );
    }


    // ── Handle FastAPI errors ──────────────────────────────────────────────
    if (fastapiResponse.status === 401) {
      return NextResponse.json(
        { error: data?.detail ?? "PDF requires a password." },
        { status: 401 },
      );
    }

    if (fastapiResponse.status === 400) {
      return NextResponse.json(
        { error: data?.detail ?? data?.message ?? "Invalid file format." },
        { status: 400 },
      );
    }

    if (fastapiResponse.status === 413) {
      return NextResponse.json(
        { error: "File too large. Maximum size is 50MB." },
        { status: 413 },
      );
    }

    if (fastapiResponse.status === 415) {
      return NextResponse.json(
        {
          error:
            "Unsupported file format. Please upload a PDF, CSV, or Excel file.",
        },
        { status: 415 },
      );
    }

    if (!fastapiResponse.ok) {
      return NextResponse.json(
        {
          error:
            data?.detail ??
            data?.message ??
            `Processing failed (${fastapiResponse.status})`,
        },
        { status: fastapiResponse.status },
      );
    }

    // ── Success ─────────────────────────────────────────────────────────────
    return NextResponse.json({
      fileId: data.file_id,
      message: data.message ?? "File uploaded successfully.",
      fileSize: file.size,
      estimatedCost: data.estimated_cost ?? 50,
      status: data.status ?? "processing",
    });
  } catch (error) {
    console.error("🔴 [/api/upload] unhandled error:", error);
    return NextResponse.json(
      { error: "Upload failed. Please try again." },
      { status: 500 },
    );
  }
}

// ─── PDF encryption helper ────────────────────────────────────────────────────
type EncryptionResult = "ok" | "encrypted_no_password" | "wrong_password";

async function checkPdfEncryption(
  file: File,
  password?: string,
): Promise<EncryptionResult> {
  // Fast byte-scan: every encrypted PDF has /Encrypt in its cross-reference
  // table which always sits in the first few KB — no need to load the whole file
  const slice = file.slice(0, 4096);
  const buffer = await slice.arrayBuffer();
  const text = new TextDecoder("latin1").decode(buffer);
  const isEncrypted = text.includes("/Encrypt");


  if (!isEncrypted) return "ok";
  if (!password) return "encrypted_no_password";

  // Encrypted + password supplied — verify the password with pdf-lib
  try {
    const { PDFDocument } = await import("pdf-lib");
    const fullBuffer = await file.arrayBuffer();
    await PDFDocument.load(fullBuffer, { password } as any);
    return "ok";
  } catch (e) {
    return "wrong_password";
  }
}
