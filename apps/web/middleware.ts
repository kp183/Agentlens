import { NextResponse } from "next/server";

export default function middleware() {
  // In local mode, all routes are public — no auth middleware needed.
  // When deploying with Clerk, replace this with clerkMiddleware.
  return NextResponse.next();
}

export const config = {
  matcher: [
    // Skip Next.js internals and static files
    "/((?!_next|[^?]*\\.[\\w]+$|_next/image|_next/static|favicon.ico|sitemap.xml|robots.txt).*)",
    // Always run for API routes
    "/(api|trpc)(.*)",
  ],
};
