import { NextResponse } from "next/server";
import { API_BASE_URL } from "@/lib/constants";
import { getAuthToken, clearAuthCookie } from "@/lib/auth";

export async function GET() {
  const token = await getAuthToken();

  if (!token) {
    return NextResponse.json(
      { detail: "Not authenticated" },
      { status: 401 }
    );
  }

  const res = await fetch(`${API_BASE_URL}/api/auth/session`, {
    headers: { Authorization: `Bearer ${token}` },
  });

  if (!res.ok) {
    // Token is invalid/expired — clear cookie
    await clearAuthCookie();
    return NextResponse.json(
      { detail: "Session expired" },
      { status: 401 }
    );
  }

  const data = await res.json();
  return NextResponse.json(data);
}
