# Production Setup & Multi-Tenant Authentication

To deploy AgentLens to production or run it with multi-tenant user authentication, you must configure **Clerk**.

## 1. Create a Clerk Account

1. Sign up for a free account at [clerk.com](https://clerk.com).
2. Create a new application (e.g., "AgentLens").
3. Choose the authentication providers you want (email, Google, GitHub, etc.).

## 2. Obtain Credentials

From your Clerk dashboard under **API Keys**, copy the following keys into your `.env` file:

```env
# Disable local auth bypass
LOCAL_MODE=false
NEXT_PUBLIC_LOCAL_MODE=false

# Clerk backend credentials
CLERK_SECRET_KEY=sk_test_...
CLERK_PUBLISHABLE_KEY=pk_test_...
CLERK_JWKS_URL=https://your-clerk-instance.clerk.accounts.dev/.well-known/jwks.json

# Clerk frontend credentials
NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=pk_test_...
```

## 3. Deployment

Ensure that your database URL and CORS origins are configured for your production domains:

```env
DATABASE_URL=postgresql+asyncpg://user:password@prod-db-host/agentlens
CORS_ORIGINS=["https://app.yourdomain.com"]
```
