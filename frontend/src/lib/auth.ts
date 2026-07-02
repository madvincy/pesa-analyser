import { PrismaAdapter } from "@auth/prisma-adapter";
import { PrismaClient } from "@prisma/client";
import bcrypt from "bcryptjs";
import jwt from "jsonwebtoken";
import { NextAuthOptions } from "next-auth";
import { JWT } from "next-auth/jwt";
import CredentialsProvider from "next-auth/providers/credentials";
import FacebookProvider from "next-auth/providers/facebook";
import GoogleProvider from "next-auth/providers/google";

const prisma = new PrismaClient();

// ============================================================
// EXTEND TYPES - Add createdAt to User and Session
// ============================================================
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
    };
    accessToken?: string; // ✅ This is the JWT token for your backend
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

// ============================================================
// NEXT AUTH CONFIGURATION
// ============================================================
export const authOptions: NextAuthOptions = {
  adapter: PrismaAdapter(prisma),
  session: {
    strategy: "jwt",
  },
  providers: [
    GoogleProvider({
      clientId: process.env.GOOGLE_CLIENT_ID || "",
      clientSecret: process.env.GOOGLE_CLIENT_SECRET || "",
      authorization: {
        params: {
          prompt: "consent",
          access_type: "offline",
          response_type: "code",
        },
      },
    }),
    FacebookProvider({
      clientId: process.env.FACEBOOK_CLIENT_ID || "",
      clientSecret: process.env.FACEBOOK_CLIENT_SECRET || "",
    }),
    CredentialsProvider({
      name: "credentials",
      credentials: {
        email: { label: "Email", type: "email" },
        password: { label: "Password", type: "password" },
      },
      async authorize(credentials) {
        if (!credentials?.email || !credentials?.password) {
          throw new Error("Invalid credentials");
        }

        const user = await prisma.user.findUnique({
          where: { email: credentials.email },
        });

        if (!user || !user.password) {
          throw new Error("Invalid credentials");
        }

        const isCorrectPassword = await bcrypt.compare(
          credentials.password,
          user.password,
        );

        if (!isCorrectPassword) {
          throw new Error("Invalid credentials");
        }

        return {
          id: user.id,
          email: user.email,
          name: user.name,
          image: user.image,
          role: user.role,
          createdAt: user.createdAt,
        };
      },
    }),
  ],
  callbacks: {
    async jwt({ token, user, account }) {
      // Initial sign in - add user data to token
      if (user) {
        token.id = user.id;
        token.sub = user.id;
        token.role = user.role;
        token.email = user.email;
        token.name = user.name;
        token.picture = user.image ?? null;
        token.createdAt = user.createdAt ?? new Date().toISOString();
      }

      // If using OAuth, add provider info and access token
      if (account) {
        token.provider = account.provider;
        token.accessToken = account.access_token;
        token.refreshToken = account.refresh_token;
      }

      return token;
    },
    async session({ session, token }) {
      // ✅ Create a proper JWT token for your backend
      // This token will be used to authenticate with your FastAPI backend
      const customJwt = jwt.sign(
        {
          sub: token.id,
          user_id: token.id, // ✅ Use 'user_id' to match your backend's expected field
          email: token.email,
          name: token.name,
          role: token.role || "user",
          createdAt: token.createdAt || new Date().toISOString(),
        },
        process.env.NEXTAUTH_SECRET!,
        { expiresIn: "7d" },
      );

      // ✅ Add user info to session with proper typing
      session.user = {
        id: token.id as string,
        name: (token.name as string) || null,
        email: (token.email as string) || null,
        image: (token.picture as string) || null,
        role: (token.role as string) || "user",
        createdAt: (token.createdAt as string) || new Date().toISOString(),
      };

      // ✅ Add the JWT token to the session for API client
      session.accessToken = customJwt;

      // Add provider info if available
      if (token.provider) {
        session.provider = token.provider as string;
      }

      return session;
    },
  },
  pages: {
    signIn: "/auth/signin",
    error: "/auth/error",
  },
  secret: process.env.NEXTAUTH_SECRET,
  debug: process.env.NODE_ENV === "development",
};
