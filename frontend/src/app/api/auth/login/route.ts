import { NextRequest, NextResponse } from "next/server";
import { API_BASE_URL } from "@/lib/constants";
import { setAuthCookie } from "@/lib/auth";

export async function POST(req: NextRequest) {
  const body = await req.json();

  const res = await fetch(`${API_BASE_URL}/api/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });

  const data = await res.json();

  if (!res.ok) {
    return NextResponse.json(
      { detail: data.detail || "Login failed" },
      { status: res.status }
    );
  }

  // Set JWT in httpOnly cookie
  await setAuthCookie(data.access_token);

  // Return session info (not the token itself)
  return NextResponse.json({
    username: data.username,
    email: data.email,
    tier: data.tier,
    is_admin: data.is_admin,
  });
}
