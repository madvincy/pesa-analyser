#!/bin/bash

echo "🔑 Generating secure secret keys..."

# Generate NextAuth secret (32+ characters)
NEXTAUTH_SECRET=$(openssl rand -base64 32)
echo "NEXTAUTH_SECRET=$NEXTAUTH_SECRET"

# Generate JWT secret
JWT_SECRET=$(openssl rand -base64 32)
echo "JWT_SECRET=$JWT_SECRET"

# Generate general secret key
SECRET_KEY=$(openssl rand -base64 32)
echo "SECRET_KEY=$SECRET_KEY"

echo ""
echo "📝 Add these to your .env and .env.local files"
echo ""
echo "For frontend (.env.local):"
echo "NEXTAUTH_SECRET=$NEXTAUTH_SECRET"
echo ""
echo "For backend (.env):"
echo "SECRET_KEY=$SECRET_KEY"
echo "JWT_SECRET=$JWT_SECRET"
