import { PrismaClient } from "@prisma/client";
import bcrypt from "bcryptjs";

const prisma = new PrismaClient();

async function main() {
  const email = process.argv[2] || "test@example.com";
  const password = process.argv[3] || "Test123!";
  const name = process.argv[4] || "Test User";

  try {
    const hashedPassword = await bcrypt.hash(password, 10);

    const user = await prisma.user.upsert({
      where: { email },
      update: {
        password: hashedPassword,
        name: name,
        isActive: true,
        emailVerified: new Date(),
      },
      create: {
        email,
        name: name,
        password: hashedPassword,
        role: "user",
        isActive: true,
        emailVerified: new Date(),
      },
    });

  } catch (error) {
    console.error("❌ Failed to create test user:", error);
    process.exit(1);
  } finally {
    await prisma.$disconnect();
  }
}

main();
