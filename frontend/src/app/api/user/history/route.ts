import { authOptions } from "@/lib/auth";
import { getServerSession } from "next-auth";
import { NextRequest, NextResponse } from "next/server";

// This route uses request cookies/session and must be server-rendered.
export const dynamic = "force-dynamic";

const FASTAPI_URL =
  process.env.FASTAPI_URL ?? process.env.BACKEND_URL ?? "http://localhost:8000";

export async function GET(request: NextRequest) {
  try {
    // ── Auth: same pattern as /api/upload and /api/analysis/[id] ────────────
    // Deliberately using getServerSession (not getToken) here. getToken()
    // returns the raw JWT payload shaped by the jwt() callback in your
    // NextAuth config, which is NOT guaranteed to have the same field names
    // as the `session` object shaped by the session() callback. Mixing the
    // two APIs across different routes is exactly what caused this route to
    // silently send an empty/garbage Bearer token and fall back to a
    // different resolved user than /api/upload.
    const session = await getServerSession(authOptions);

    if (!session?.user) {
      return NextResponse.json({ error: "Unauthorised" }, { status: 401 });
    }

    const { searchParams } = new URL(request.url);
    const qs = searchParams.toString();

    // ── Build headers to forward, identical to /api/upload and /api/analysis/[id] ──
    const headers = new Headers();
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

    // ── Forward to FastAPI ────────────────────────────────────────────────
    let fastapiResponse: Response;
    try {
      fastapiResponse = await fetch(
        `${FASTAPI_URL}/api/v1/user/history?${qs}`,
        {
          method: "GET",
          headers,
          credentials: "include",
          cache: "no-store",
        },
      );
    } catch (fetchError) {
      console.error("🔴 [/api/user/history] cannot reach FastAPI:", fetchError);
      return NextResponse.json(
        { error: "History service is unavailable. Please try again later." },
        { status: 503 },
      );
    }

    let data: any = {};
    try {
      const text = await fastapiResponse.text();
      data = text ? JSON.parse(text) : {};
    } catch (parseError) {
      console.error(
        "🔴 [/api/user/history] failed to parse FastAPI response:",
        parseError,
      );
      return NextResponse.json(
        { error: "Invalid response from history service." },
        { status: 502 },
      );
    }

    if (fastapiResponse.status === 401) {
      return NextResponse.json(
        { error: "Your session has expired. Please sign in again." },
        { status: 401 },
      );
    }

    if (!fastapiResponse.ok) {
      return NextResponse.json(
        {
          error:
            data?.detail ??
            data?.error ??
            `Request failed (${fastapiResponse.status})`,
        },
        { status: fastapiResponse.status },
      );
    }

    return NextResponse.json(data);
  } catch (error) {
    console.error("🔴 [/api/user/history] unhandled error:", error);
    return NextResponse.json(
      { error: "Failed to fetch history. Please try again." },
      { status: 500 },
    );
  }
}
