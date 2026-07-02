import { PrismaClient } from "@prisma/client";
import bcrypt from "bcryptjs";

const prisma = new PrismaClient();

async function main() {
  const email = process.argv[2] || "admin@pesaanalyser.com";
  const password = process.argv[3] || "Admin123!";
  const name = process.argv[4] || "Admin User";

  try {
    // Check if user already exists
    const existingUser = await prisma.user.findUnique({
      where: { email },
    });

    if (existingUser) {

      // Update existing user to admin
      const hashedPassword = await bcrypt.hash(password, 10);
      const user = await prisma.user.update({
        where: { email },
        data: {
          password: hashedPassword,
          role: "admin",
          isActive: true,
          name: name,
          emailVerified: new Date(),
        },
      });

      return;
    }

    // Create new admin user
    const hashedPassword = await bcrypt.hash(password, 10);

    const user = await prisma.user.create({
      data: {
        email,
        name: name,
        password: hashedPassword,
        role: "admin",
        isActive: true,
        emailVerified: new Date(),
      },
    });

  } catch (error) {
    console.error("❌ Failed to create admin user:", error);
    process.exit(1);
  } finally {
    await prisma.$disconnect();
  }
}

main();
