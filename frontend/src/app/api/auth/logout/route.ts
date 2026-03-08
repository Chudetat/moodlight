import { NextResponse } from "next/server";
import { API_BASE_URL } from "@/lib/constants";
import { getAuthToken, clearAuthCookie } from "@/lib/auth";

export async function POST() {
  const token = await getAuthToken();

  if (token) {
    // Tell backend to invalidate session
    await fetch(`${API_BASE_URL}/api/auth/logout`, {
      method: "POST",
      headers: { Authorization: `Bearer ${token}` },
    }).catch(() => {
      // Ignore errors — we clear the cookie regardless
    });
  }

  await clearAuthCookie();
  return NextResponse.json({ status: "ok" });
}
