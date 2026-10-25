import { NextResponse, type NextRequest } from "next/server";

// Must match SESSION_COOKIE in backend/app/api/deps.py
const SESSION_COOKIE = "careerlens_session";

const PUBLIC_PATHS = ["/login", "/register"];

/**
 * Optimistic check only: sends visitors without a session cookie to /login
 * before the page loads. It can't tell whether the cookie is still valid;
 * the backend decides that on every API call (401 → the page redirects).
 */
export function proxy(request: NextRequest) {
  const { pathname, search } = request.nextUrl;
  if (PUBLIC_PATHS.includes(pathname) || request.cookies.has(SESSION_COOKIE)) {
    return NextResponse.next();
  }
  const loginUrl = new URL("/login", request.url);
  if (pathname !== "/") loginUrl.searchParams.set("next", pathname + search);
  return NextResponse.redirect(loginUrl);
}

export const config = {
  // Skip the API (the backend does its own auth), Next internals and static files.
  matcher: ["/((?!api/|_next/|favicon.ico|.*\\.[a-zA-Z0-9]+$).*)"],
};
