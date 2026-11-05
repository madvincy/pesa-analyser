import { authOptions } from "@/lib/auth";
import { getServerSession } from "next-auth";
import { NextRequest, NextResponse } from "next/server";

export const runtime = "nodejs";

const FASTAPI_URL = process.env.FASTAPI_URL ?? "http://localhost:8000";

export async function POST(request: NextRequest) {
  try {
    const session = await getServerSession(authOptions);
    if (!session?.user) {
      return NextResponse.json({ error: "Unauthorised" }, { status: 401 });
    }

    const contentType = request.headers.get("content-type");
    if (!contentType?.toLowerCase().includes("multipart/form-data")) {
      return NextResponse.json(
        { error: "Upload must use multipart form data." },
        { status: 400 },
      );
    }

    const headers = new Headers({ "content-type": contentType });
    if (session.accessToken) {
      headers.set("Authorization", `Bearer ${session.accessToken}`);
    }
    if (
      session.user.id &&
      /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(
        session.user.id,
      )
    ) {
      headers.set("X-User-ID", session.user.id);
    }
    if (session.user.email) {
      headers.set("X-User-Email", session.user.email);
    }
    if (session.user.name) {
      headers.set("X-User-Name", session.user.name);
    }

    let response: Response;
    try {
      response = await fetch(`${FASTAPI_URL}/api/v1/upload`, {
        method: "POST",
        headers,
        body: request.body,
        duplex: "half",
      } as RequestInit & { duplex: "half" });
    } catch (error) {
      console.error("[/api/upload] cannot reach FastAPI:", error);
      return NextResponse.json(
        { error: "Analysis service is unavailable. Please try again later." },
        { status: 503 },
      );
    }

    const responseText = await response.text();
    let data: Record<string, unknown> = {};
    if (responseText) {
      try {
        data = JSON.parse(responseText) as Record<string, unknown>;
      } catch (error) {
        console.error("[/api/upload] invalid FastAPI response:", error);
        return NextResponse.json(
          { error: "Invalid response from analysis service." },
          { status: 502 },
        );
      }
    }

    if (!response.ok) {
      const error =
        data.detail ??
        data.message ??
        `Upload failed (${response.status})`;
      return NextResponse.json(
        { error },
        { status: response.status },
      );
    }

    return NextResponse.json(
      {
        fileId: data.file_id,
        message: data.message ?? "File uploaded successfully.",
        fileSize: data.file_size,
        status: data.status ?? "queued",
      },
      { status: response.status },
    );
  } catch (error) {
    console.error("[/api/upload] unhandled error:", error);
    return NextResponse.json(
      { error: "Upload failed. Please try again." },
      { status: 500 },
    );
  }
}
