import { authOptions } from "@/lib/auth";
import { getServerSession } from "next-auth";
import { NextRequest, NextResponse } from "next/server";

const FASTAPI_URL = process.env.FASTAPI_URL ?? "http://localhost:8000";

export async function GET(
  _request: NextRequest,
  { params }: { params: { id: string } },
) {
  const session = await getServerSession(authOptions);
  if (!session?.user) {
    return NextResponse.json({ error: "Unauthorised" }, { status: 401 });
  }

  const headers = new Headers();
  if (session.accessToken) {
    headers.set("Authorization", `Bearer ${session.accessToken}`);
  }
  if (session.user.id) {
    headers.set("X-User-ID", session.user.id);
  }

  try {
    const response = await fetch(
      `${FASTAPI_URL}/api/v1/status/${encodeURIComponent(params.id)}`,
      { headers, cache: "no-store" },
    );
    const body = await response.text();
    let data: Record<string, unknown> = {};
    if (body) {
      try {
        data = JSON.parse(body) as Record<string, unknown>;
      } catch (error) {
        console.error("[/api/analysis/status] invalid backend response:", error);
        return NextResponse.json(
          { error: "Invalid response from analysis service." },
          { status: 502 },
        );
      }
    }

    return NextResponse.json(data, {
      status: response.status,
      headers: { "Cache-Control": "no-store" },
    });
  } catch (error) {
    console.error("[/api/analysis/status] cannot reach FastAPI:", error);
    return NextResponse.json(
      { error: "Analysis service is unavailable. Please try again later." },
      { status: 503 },
    );
  }
}
