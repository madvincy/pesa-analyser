import { PrismaClient } from "@prisma/client";

const prisma = new PrismaClient();

async function main() {
  const email = process.argv[2];

  if (!email) {
    console.error(
      "❌ Please provide an email: npx tsx scripts/delete-user.ts user@example.com",
    );
    process.exit(1);
  }

  try {
    const user = await prisma.user.delete({
      where: { email },
    });

  } catch (error) {
    console.error(`❌ Failed to delete user: ${error}`);
    process.exit(1);
  } finally {
    await prisma.$disconnect();
  }
}

main();
