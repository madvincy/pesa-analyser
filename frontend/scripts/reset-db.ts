import { PrismaClient } from "@prisma/client";

const prisma = new PrismaClient();

async function main() {

  // Wait for user input
  await new Promise((resolve) => process.stdin.once("data", resolve));

  try {

    // Delete all data in correct order (respecting foreign keys)
    await prisma.$transaction([
      prisma.paymentLog.deleteMany(),
      prisma.payment.deleteMany(),
      prisma.contactMessage.deleteMany(),
      prisma.notification.deleteMany(),
      prisma.tokenUsage.deleteMany(),
      prisma.chatHistory.deleteMany(),
      prisma.passwordReset.deleteMany(),
      prisma.analysis.deleteMany(),
      prisma.verificationToken.deleteMany(),
      prisma.session.deleteMany(),
      prisma.account.deleteMany(),
      prisma.user.deleteMany(),
    ]);

  } catch (error) {
    console.error("❌ Failed to reset database:", error);
    process.exit(1);
  } finally {
    await prisma.$disconnect();
  }
}

main();
