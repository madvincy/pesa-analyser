// frontend/src/types/next-auth.d.ts
import { DefaultSession } from "next-auth";
import { JWT } from "next-auth/jwt";

declare module "next-auth" {
  interface User {
    role?: string;
    createdAt?: string | Date;
  }

  interface Session {
    user: {
      id: string;
      name?: string | null;
      email?: string | null;
      image?: string | null;
      role?: string;
      createdAt?: string | Date;
    } & DefaultSession["user"];
    accessToken?: string;
    jwt?: JWT;
    provider?: string;
  }
}

declare module "next-auth/jwt" {
  interface JWT {
    id?: string;
    role?: string;
    provider?: string;
    accessToken?: string;
    refreshToken?: string;
    picture?: string | null;
    createdAt?: string | Date;
  }
}
