import { PrismaClient } from "@prisma/client";

const prisma = new PrismaClient();

async function main() {
  try {
    const users = await prisma.user.findMany({
      select: {
        id: true,
        email: true,
        name: true,
        role: true,
        isActive: true,
        createdAt: true,
        lastLogin: true,
      },
      orderBy: {
        createdAt: "desc",
      },
    });


    if (users.length === 0) {
      return;
    }

    users.forEach((user, index) => {
    });
  } catch (error) {
    console.error("❌ Failed to list users:", error);
    process.exit(1);
  } finally {
    await prisma.$disconnect();
  }
}

main();
