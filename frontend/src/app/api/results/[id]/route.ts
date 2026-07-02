import { authOptions } from "@/lib/auth";
import { getServerSession } from "next-auth";
import { NextRequest, NextResponse } from "next/server";

export const dynamic = "force-dynamic";

const FASTAPI_URL = process.env.FASTAPI_URL ?? process.env.BACKEND_URL ?? "http://localhost:8000";

export async function GET(
  request: NextRequest,
  { params }: { params: { id: string } },
) {
  const analysisId = params.id;

  if (!analysisId) {
    return NextResponse.json({ error: "Missing analysis id" }, { status: 400 });
  }

  try {
    const session = await getServerSession(authOptions);

    if (!session?.user) {
      return NextResponse.json({ error: "Unauthorised" }, { status: 401 });
    }

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

    let fastapiResponse: Response;
    try {
      fastapiResponse = await fetch(`${FASTAPI_URL}/api/v1/results/${analysisId}`, {
        method: "GET",
        headers,
        credentials: "include",
        cache: "no-store",
      });
    } catch (fetchError) {
      console.error("🔴 [/api/results] cannot reach FastAPI:", fetchError);
      return NextResponse.json(
        { error: "Results service is unavailable. Please try again later." },
        { status: 503 },
      );
    }

    let data: any = {};
    try {
      const text = await fastapiResponse.text();
      data = text ? JSON.parse(text) : {};
    } catch (parseError) {
      console.error("🔴 [/api/results] failed to parse FastAPI response:", parseError);
      return NextResponse.json(
        { error: "Invalid response from results service." },
        { status: 502 },
      );
    }

    if (fastapiResponse.status === 401) {
      return NextResponse.json(
        { error: "Your session has expired. Please sign in again." },
        { status: 401 },
      );
    }

    if (fastapiResponse.status === 403) {
      return NextResponse.json(
        { error: "You don't have access to this analysis." },
        { status: 403 },
      );
    }

    if (fastapiResponse.status === 404) {
      return NextResponse.json({ error: "Analysis not found." }, { status: 404 });
    }

    if (!fastapiResponse.ok) {
      return NextResponse.json(
        { error: data?.detail ?? data?.error ?? `Request failed (${fastapiResponse.status})` },
        { status: fastapiResponse.status },
      );
    }

    return NextResponse.json(data);
  } catch (error) {
    console.error("🔴 [/api/results] unhandled error:", error);
    return NextResponse.json(
      { error: "Failed to fetch results. Please try again." },
      { status: 500 },
    );
  }
}
