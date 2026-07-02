import { getToken } from "next-auth/jwt";
import { NextResponse } from "next/server";

// This route accesses request cookies and must be server-rendered
export const dynamic = "force-dynamic";

export async function GET(request: Request) {
  try {
    const token = await getToken({ req: request as any });

    if (!token) {
      return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
    }

    const exportData = {
      user: {
        id: token.id,
        email: token.email,
        name: token.name,
        createdAt: new Date().toISOString(),
      },
      analyses: [
        -{
          id: "1",
          fileName: "M-PESA Statement Jan 2024.pdf",
          totalIncome: 125000,
          totalExpenses: 98000,
          netCashFlow: 27000,
          status: "completed",
          createdAt: new Date().toISOString(),
        },
      ],
      chatHistory: [
        {
          id: "1",
          message: "What are my biggest expenses?",
          response:
            "Your biggest expenses are: Rent (30%), Food (25%), Transport (15%)",
          createdAt: new Date().toISOString(),
        },
      ],
      payments: [
        {
          id: "1",
          amount: 150,
          currency: "KES",
          status: "completed",
          createdAt: new Date().toISOString(),
        },
      ],
      exportedAt: new Date().toISOString(),
    };

    return NextResponse.json(exportData);
  } catch (error) {
    console.error("Export error:", error);
    return NextResponse.json(
      { error: "Failed to export data" },
      { status: 500 },
    );
  }
}
