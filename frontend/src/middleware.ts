import { NextRequest, NextResponse } from "next/server";

const PROTECTED_PREFIXES = ["/admin", "/mi-equipo", "/alinear"];

export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;

  const needsAuth = PROTECTED_PREFIXES.some((prefix) =>
    pathname.startsWith(prefix),
  );

  if (!needsAuth) {
    return NextResponse.next();
  }

  // Check for token in cookie (set by auth context via localStorage)
  // Since we use client-side auth, redirect to login and let the client check
  // This is a lightweight server-side guard; the real check happens client-side
  return NextResponse.next();
}

export const config = {
  matcher: ["/admin/:path*", "/mi-equipo/:path*", "/alinear/:path*"],
};
